import logging
import re
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.future import select
from sqlalchemy import delete as sql_delete, or_, and_, text

import db.session as db_session
from db.session import AsyncSessionLocal
from db.models import AgentMemory, Project, ProjectTechnology, GitMetadata
from core.embeddings import default_embedding_provider, ConfiguredEmbeddingProvider

logger = logging.getLogger(__name__)

# Valid Memory Categories for Phase 9 Knowledge Engine
VALID_MEMORY_TYPES = {
    "FACT", "DECISION", "PREFERENCE", "PROJECT_KNOWLEDGE",
    "RESEARCH_FINDING", "TASK_OUTCOME", "TECHNICAL_CONTEXT",
    "PROJECT", "RESEARCH", "USER_PREFERENCE"
}

# Provenance Source Reliability Weights
SOURCE_RELIABILITY_WEIGHTS = {
    "USER_CONFIRMED": 1.0,
    "VERIFIED_TASK": 0.95,
    "VERIFIED_RESEARCH": 0.90,
    "PROJECT_FILE": 0.85,
    "GIT_METADATA": 0.80,
    "AGENT_INFERENCE": 0.50
}

SECRET_PATTERNS = [
    re.compile(r"gsk_[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"tvly-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"(password|passwd|api_key|apikey|secret_key|access_token|auth_token)\s*[:=]\s*['\"]?[^\s'\"]{6,}", re.IGNORECASE),
]

def contains_secret(text: str) -> bool:
    """Checks if the content string contains sensitive credentials, API keys, or passwords."""
    if not text:
        return False
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return True
    return False

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

class MemoryStore:
    """Encapsulates database operations for AgentMemory persistence, hybrid search, and lifecycle transitions."""

    def __init__(self, embedding_provider: Optional[ConfiguredEmbeddingProvider] = None):
        self.embedding_provider = embedding_provider or default_embedding_provider

    async def find_substantially_equivalent(
        self,
        content: str,
        project_id: Optional[str] = None,
        memory_type: Optional[str] = None
    ) -> Optional[AgentMemory]:
        """Deduplication check: find existing memory with identical or substantially equivalent content."""
        clean_content = content.strip().lower()
        existing_memories = await self.retrieve(project_id=project_id, memory_type=memory_type, limit=100, include_superseded=False)

        for mem in existing_memories:
            existing_clean = mem.content.strip().lower()
            if clean_content == existing_clean:
                return mem

        return None

    async def create(
        self,
        memory_type: str,
        content: str,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source: str = "user",
        source_reliability: str = "USER_CONFIRMED",
        importance: int = 5,
        confidence: float = 1.0,
        verification_status: str = "ACTIVE",
        supersedes_id: Optional[str] = None,
        deduplicate: bool = True
    ) -> AgentMemory:
        clean_content = content.strip()
        upper_type = memory_type.upper()
        if upper_type not in VALID_MEMORY_TYPES:
            upper_type = "PROJECT_KNOWLEDGE"

        # Deduplication check
        if deduplicate and not supersedes_id:
            equivalent = await self.find_substantially_equivalent(clean_content, project_id=project_id, memory_type=upper_type)
            if equivalent:
                logger.info(f"Deduplication triggered: updating existing memory ID '{equivalent.id}' instead of inserting duplicate.")
                updated = await self.update(
                    memory_id=equivalent.id,
                    importance=max(equivalent.importance, importance),
                    confidence=max(getattr(equivalent, 'confidence', 1.0), confidence)
                )
                return updated or equivalent

        # Generate vector embedding for semantic search
        embedding_vec = await self.embedding_provider.get_embedding(clean_content)

        async with AsyncSessionLocal() as db:
            if project_id:
                proj_check = await db.execute(select(Project).where(Project.id == project_id))
                if not proj_check.scalar_one_or_none():
                    db.add(Project(id=project_id, title=f"Project {project_id}"))
                    await db.flush()

            mem = AgentMemory(
                memory_type=upper_type,
                content=clean_content,
                source=source,
                source_reliability=source_reliability,
                project_id=project_id,
                session_id=session_id,
                importance=max(1, min(10, importance)),
                confidence=max(0.0, min(1.0, confidence)),
                verification_status=verification_status,
                supersedes_id=supersedes_id,
                embedding=embedding_vec
            )
            db.add(mem)
            await db.commit()
            await db.refresh(mem)
            return mem

    async def get_by_id(self, memory_id: str) -> Optional[AgentMemory]:
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(AgentMemory).where(AgentMemory.id == memory_id))
            return res.scalar_one_or_none()

    async def retrieve(
        self,
        project_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        verification_status: Optional[str] = None,
        include_superseded: bool = False,
        limit: int = 20
    ) -> List[AgentMemory]:
        """Retrieves memories enforcing project isolation and verification filtering."""
        async with AsyncSessionLocal() as db:
            stmt = select(AgentMemory)
            conditions = []

            if project_id:
                # Strict project isolation: exact project OR global user preferences
                conditions.append(
                    or_(
                        AgentMemory.project_id == project_id,
                        AgentMemory.memory_type == "USER_PREFERENCE"
                    )
                )
            elif project_id is None and memory_type != "USER_PREFERENCE":
                # Strict global isolation: project_id is NULL OR user preference
                conditions.append(
                    or_(
                        AgentMemory.project_id.is_(None),
                        AgentMemory.memory_type == "USER_PREFERENCE"
                    )
                )

            if memory_type:
                conditions.append(AgentMemory.memory_type == memory_type.upper())

            if verification_status:
                conditions.append(AgentMemory.verification_status == verification_status.upper())
            elif not include_superseded:
                conditions.append(AgentMemory.verification_status != "SUPERSEDED")
                conditions.append(AgentMemory.verification_status != "ARCHIVED")

            if conditions:
                stmt = stmt.where(and_(*conditions))

            stmt = stmt.order_by(AgentMemory.importance.desc(), AgentMemory.created_at.desc()).limit(limit)
            res = await db.execute(stmt)
            return list(res.scalars().all())

    def get_active_vector_backend(self) -> str:
        if db_session.IS_POSTGRES_ACTIVE and db_session.IS_PGVECTOR_AVAILABLE:
            return "NATIVE_PGVECTOR"
        elif db_session.IS_POSTGRES_ACTIVE:
            return "POSTGRES_PYTHON_FALLBACK"
        else:
            return "SQLITE_PYTHON_FALLBACK"

    async def hybrid_search(
        self,
        query: str,
        project_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[AgentMemory]:
        """
        Phase 9 Hybrid Retrieval Pipeline:
        Combines vector semantic similarity (pgvector or cosine), keyword matching,
        provenance reliability weights, importance, and confidence reranking.
        """
        if not query or not query.strip():
            return await self.retrieve(project_id=project_id, memory_type=memory_type, limit=limit)

        query_vec = await self.embedding_provider.get_embedding(query)

        # Retrieve candidates enforcing strict project isolation
        candidates = await self.retrieve(
            project_id=project_id,
            memory_type=memory_type,
            include_superseded=False,
            limit=100
        )

        if not candidates:
            return []

        q_words = [w.lower() for w in query.split() if len(w) > 2]
        scored: List[Tuple[float, AgentMemory]] = []

        for mem in candidates:
            # 1. Vector similarity (pgvector cosine or manual cosine)
            sim_score = 0.0
            if mem.embedding and isinstance(mem.embedding, list):
                sim_score = max(0.0, cosine_similarity(query_vec, mem.embedding))

            # 2. Keyword matching score
            c_lower = mem.content.lower()
            kw_matches = sum(1 for w in q_words if w in c_lower)
            kw_score = kw_matches / max(1, len(q_words)) if q_words else 0.0

            # 3. Source reliability weight
            rel_weight = SOURCE_RELIABILITY_WEIGHTS.get(getattr(mem, 'source_reliability', 'USER_CONFIRMED'), 0.8)

            # 4. Importance score (0.0 to 1.0)
            imp_score = getattr(mem, 'importance', 5) / 10.0

            # 5. Confidence score
            conf_score = getattr(mem, 'confidence', 1.0)

            # Combined weighted score
            final_score = (
                (0.45 * sim_score) +
                (0.25 * kw_score) +
                (0.15 * rel_weight) +
                (0.10 * imp_score) +
                (0.05 * conf_score)
            )
            scored.append((final_score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [item[1] for item in scored[:limit]]

        # Record access telemetry asynchronously
        async with AsyncSessionLocal() as db:
            for m in results:
                try:
                    res = await db.execute(select(AgentMemory).where(AgentMemory.id == m.id))
                    db_mem = res.scalar_one_or_none()
                    if db_mem:
                        db_mem.access_count = getattr(db_mem, 'access_count', 0) + 1
                        db_mem.last_accessed_at = datetime.utcnow()
                        await db.commit()
                except Exception:
                    pass

        return results

    async def search(
        self,
        query: str,
        project_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[AgentMemory]:
        return await self.hybrid_search(query=query, project_id=project_id, memory_type=memory_type, limit=limit)

    async def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        importance: Optional[int] = None,
        confidence: Optional[float] = None,
        verification_status: Optional[str] = None
    ) -> Optional[AgentMemory]:
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(AgentMemory).where(AgentMemory.id == memory_id))
            mem = res.scalar_one_or_none()
            if not mem:
                return None

            if content is not None:
                mem.content = content.strip()
                mem.embedding = await self.embedding_provider.get_embedding(mem.content)
            if importance is not None:
                mem.importance = max(1, min(10, importance))
            if confidence is not None:
                mem.confidence = max(0.0, min(1.0, confidence))
            if verification_status is not None:
                mem.verification_status = verification_status.upper()

            mem.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(mem)
            return mem

    async def supersede(
        self,
        old_memory_id: str,
        new_content: str,
        project_id: Optional[str] = None,
        source: str = "user",
        source_reliability: str = "USER_CONFIRMED"
    ) -> AgentMemory:
        """
        Phase 9 Knowledge Supersession Workflow:
        Marks old memory as SUPERSEDED and creates new ACTIVE memory linking via supersedes_id.
        """
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(AgentMemory).where(AgentMemory.id == old_memory_id))
            old_mem = res.scalar_one_or_none()
            if old_mem:
                old_mem.verification_status = "SUPERSEDED"
                old_mem.updated_at = datetime.utcnow()
                await db.commit()

        return await self.create(
            memory_type=old_mem.memory_type if old_mem else "PROJECT_KNOWLEDGE",
            content=new_content,
            project_id=project_id or (old_mem.project_id if old_mem else None),
            source=source,
            source_reliability=source_reliability,
            importance=old_mem.importance if old_mem else 7,
            verification_status="ACTIVE",
            supersedes_id=old_memory_id
        )

    async def archive(self, memory_id: str) -> Optional[AgentMemory]:
        return await self.update(memory_id=memory_id, verification_status="ARCHIVED")

    async def verify(self, memory_id: str) -> Optional[AgentMemory]:
        return await self.update(memory_id=memory_id, verification_status="VERIFIED")

    async def delete(self, memory_id: str) -> bool:
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(AgentMemory).where(AgentMemory.id == memory_id))
            mem = res.scalar_one_or_none()
            if not mem:
                return False
            await db.delete(mem)
            await db.commit()
            return True


class MemoryManager:
    """Provider-agnostic high-level manager for Cocoa Agent Memory & Knowledge Engine."""

    def __init__(self, store: Optional[MemoryStore] = None):
        self.store = store or MemoryStore()

    async def remember(
        self,
        memory_type: str,
        content: str,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source: str = "user",
        source_reliability: str = "USER_CONFIRMED",
        importance: int = 5,
        confidence: float = 1.0,
        verification_status: str = "ACTIVE",
        has_evidence: bool = True
    ) -> AgentMemory:
        """Stores a new memory after enforcing secret filtering, research verification, and deduplication."""
        upper_type = memory_type.upper()
        if upper_type not in VALID_MEMORY_TYPES:
            raise ValueError(f"Invalid memory type '{memory_type}'. Allowed: {', '.join(sorted(VALID_MEMORY_TYPES))}")

        # 1. Secret Protection Rule
        if contains_secret(content):
            logger.warning("Attempted to store memory containing sensitive credentials or API keys. Rejected.")
            raise ValueError("Secrets, passwords, API keys, and access tokens cannot be stored in Agent Memory.")

        # 2. Research Verification Rule
        if upper_type in ("RESEARCH", "RESEARCH_FINDING") and not has_evidence:
            logger.warning("Attempted to store unverified research finding without supporting evidence. Rejected.")
            raise ValueError("Unverified research findings without supporting evidence cannot be stored as research memory.")

        return await self.store.create(
            memory_type=upper_type,
            content=content,
            project_id=project_id,
            session_id=session_id,
            source=source,
            source_reliability=source_reliability,
            importance=importance,
            confidence=confidence,
            verification_status=verification_status
        )

    async def retrieve(
        self,
        project_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[AgentMemory]:
        return await self.store.retrieve(project_id=project_id, memory_type=memory_type, limit=limit)

    async def search(
        self,
        query: str,
        project_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 5
    ) -> List[AgentMemory]:
        return await self.store.search(query=query, project_id=project_id, memory_type=memory_type, limit=limit)

    async def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        importance: Optional[int] = None,
        confidence: Optional[float] = None,
        verification_status: Optional[str] = None
    ) -> Optional[AgentMemory]:
        if content and contains_secret(content):
            raise ValueError("Secrets, passwords, API keys, and access tokens cannot be stored in Agent Memory.")
        return await self.store.update(
            memory_id=memory_id,
            content=content,
            importance=importance,
            confidence=confidence,
            verification_status=verification_status
        )

    async def supersede(
        self,
        old_memory_id: str,
        new_content: str,
        project_id: Optional[str] = None,
        source: str = "user",
        source_reliability: str = "USER_CONFIRMED"
    ) -> AgentMemory:
        if contains_secret(new_content):
            raise ValueError("Secrets, passwords, API keys, and access tokens cannot be stored in Agent Memory.")
        return await self.store.supersede(
            old_memory_id=old_memory_id,
            new_content=new_content,
            project_id=project_id,
            source=source,
            source_reliability=source_reliability
        )

    async def archive(self, memory_id: str) -> Optional[AgentMemory]:
        return await self.store.archive(memory_id)

    async def verify(self, memory_id: str) -> Optional[AgentMemory]:
        return await self.store.verify(memory_id)

    async def delete(self, memory_id: str) -> bool:
        return await self.store.delete(memory_id)

    async def get_by_id(self, memory_id: str) -> Optional[AgentMemory]:
        return await self.store.get_by_id(memory_id)

    def get_active_vector_backend(self) -> str:
        return self.store.get_active_vector_backend()

    async def build_bounded_context(
        self,
        project_id: Optional[str],
        task_description: str,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Phase 9 Context Intelligence Builder for Planner:
        Constructs bounded context from Active Project, Project Technologies, Git State, and Relevant Memories.
        Prevents dumping entire DB into LLM context!
        """
        context_data = {
            "project_id": project_id,
            "technologies": [],
            "git_branch": None,
            "relevant_memories": []
        }

        if not project_id:
            return context_data

        async with AsyncSessionLocal() as db:
            # Fetch technologies
            tech_res = await db.execute(select(ProjectTechnology).where(ProjectTechnology.project_id == project_id))
            techs = tech_res.scalars().all()
            context_data["technologies"] = [f"{t.name} ({t.category})" for t in techs]

            # Fetch git info
            git_res = await db.execute(select(GitMetadata).where(GitMetadata.project_id == project_id))
            git_meta = git_res.scalar_one_or_none()
            if git_meta:
                context_data["git_branch"] = git_meta.branch

        # Relevant memories via hybrid search
        mems = await self.search(query=task_description, project_id=project_id, limit=5)
        context_data["relevant_memories"] = [m.content for m in mems]

        return context_data

memory_manager = MemoryManager()
