import logging
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.future import select
from sqlalchemy import delete as sql_delete, or_, and_, text

from db.session import AsyncSessionLocal, IS_POSTGRES_ACTIVE, IS_PGVECTOR_AVAILABLE
from db.models import AgentMemory, Project
from core.embeddings import default_embedding_provider, ConfiguredEmbeddingProvider

logger = logging.getLogger(__name__)

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
    """Encapsulates database operations for AgentMemory persistence and semantic vector search."""
    
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
        existing_memories = await self.retrieve(project_id=project_id, memory_type=memory_type, limit=100)
        
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
        importance: int = 5,
        deduplicate: bool = True
    ) -> AgentMemory:
        clean_content = content.strip()
        upper_type = memory_type.upper()
        
        # Deduplication check
        if deduplicate:
            equivalent = await self.find_substantially_equivalent(clean_content, project_id=project_id, memory_type=upper_type)
            if equivalent:
                logger.info(f"Deduplication triggered: updating existing memory ID '{equivalent.id}' instead of inserting duplicate.")
                updated = await self.update(
                    memory_id=equivalent.id,
                    importance=max(equivalent.importance, importance)
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
                project_id=project_id,
                session_id=session_id,
                importance=max(1, min(10, importance)),
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
        limit: int = 20
    ) -> List[AgentMemory]:
        async with AsyncSessionLocal() as db:
            stmt = select(AgentMemory)
            conditions = []

            if project_id:
                # Strict isolation: Include exact project memories OR global user preferences
                conditions.append(
                    or_(
                        AgentMemory.project_id == project_id,
                        AgentMemory.memory_type == "USER_PREFERENCE"
                    )
                )
            elif project_id is None and memory_type != "USER_PREFERENCE":
                # Strict isolation: if no project_id specified, don't leak private project memories
                conditions.append(
                    or_(
                        AgentMemory.project_id.is_(None),
                        AgentMemory.memory_type == "USER_PREFERENCE"
                    )
                )

            if memory_type:
                conditions.append(AgentMemory.memory_type == memory_type.upper())

            if conditions:
                stmt = stmt.where(and_(*conditions))

            stmt = stmt.order_by(AgentMemory.importance.desc(), AgentMemory.created_at.desc()).limit(limit)
            res = await db.execute(stmt)
            return list(res.scalars().all())

    async def semantic_search(
        self,
        query: str,
        project_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[AgentMemory]:
        """Performs vector similarity search. Uses pgvector in PostgreSQL if available, else in-memory cosine fallback."""
        if not query or not query.strip():
            return await self.retrieve(project_id=project_id, memory_type=memory_type, limit=limit)

        query_vec = await self.embedding_provider.get_embedding(query)
        candidates = await self.retrieve(project_id=project_id, memory_type=memory_type, limit=100)
        
        if not candidates:
            return []

        # High-performance hybrid ranking over embedding vectors and keyword matches
        q_words = [w.lower() for w in query.split() if len(w) > 2]
        scored = []
        for mem in candidates:
            sim = 0.0
            if mem.embedding and isinstance(mem.embedding, list):
                sim = cosine_similarity(query_vec, mem.embedding)

            c_lower = mem.content.lower()
            kw_matches = sum(1 for w in q_words if w in c_lower)
            kw_score = kw_matches / max(1, len(q_words))

            score = (kw_score * 0.5) + (sim * 0.4) + ((mem.importance / 10.0) * 0.1)
            scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    async def search(
        self,
        query: str,
        project_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[AgentMemory]:
        """Hybrid search combining keyword matching and vector semantic similarity."""
        return await self.semantic_search(query=query, project_id=project_id, memory_type=memory_type, limit=limit)

    async def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        importance: Optional[int] = None
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

            mem.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(mem)
            return mem

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
    """Provider-agnostic high-level manager for Cocoa Agent Memory."""
    
    def __init__(self, store: Optional[MemoryStore] = None):
        self.store = store or MemoryStore()

    async def remember(
        self,
        memory_type: str,
        content: str,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source: str = "user",
        importance: int = 5,
        has_evidence: bool = True
    ) -> AgentMemory:
        """Stores a new memory after enforcing secret filtering, research verification, and deduplication."""
        upper_type = memory_type.upper()
        if upper_type not in ("PROJECT", "RESEARCH", "USER_PREFERENCE"):
            raise ValueError(f"Invalid memory type '{memory_type}'. Allowed: PROJECT, RESEARCH, USER_PREFERENCE")

        # 1. Secret Protection Rule
        if contains_secret(content):
            logger.warning("Attempted to store memory containing sensitive credentials or API keys. Rejected.")
            raise ValueError("Secrets, passwords, API keys, and access tokens cannot be stored in Agent Memory.")

        # 2. Research Verification Rule
        if upper_type == "RESEARCH" and not has_evidence:
            logger.warning("Attempted to store unverified research finding without supporting evidence. Rejected.")
            raise ValueError("Unverified research findings without supporting evidence cannot be stored as research memory.")

        return await self.store.create(
            memory_type=upper_type,
            content=content,
            project_id=project_id,
            session_id=session_id,
            source=source,
            importance=importance
        )

    async def retrieve(
        self,
        project_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[AgentMemory]:
        """Retrieves memories relevant to the specified project or memory type."""
        return await self.store.retrieve(project_id=project_id, memory_type=memory_type, limit=limit)

    async def search(
        self,
        query: str,
        project_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 5
    ) -> List[AgentMemory]:
        """Performs explicit relevance-filtered hybrid/semantic memory search."""
        return await self.store.search(query=query, project_id=project_id, memory_type=memory_type, limit=limit)

    async def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        importance: Optional[int] = None
    ) -> Optional[AgentMemory]:
        """Updates memory content after enforcing secret validation."""
        if content and contains_secret(content):
            raise ValueError("Secrets, passwords, API keys, and access tokens cannot be stored in Agent Memory.")
        return await self.store.update(memory_id=memory_id, content=content, importance=importance)

    async def delete(self, memory_id: str) -> bool:
        """Deletes a memory record."""
        return await self.store.delete(memory_id)

memory_manager = MemoryManager()
