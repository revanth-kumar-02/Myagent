"""
tests.test_rag_v5_memory — Comprehensive Test Suite for Kora's Long-Term Memory System (RAG V5)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from core.context_package import ContextPackageBuilder
from core.context_resolver import ContextResolver
from core.memory import Memory
from core.types import SourceType
from memory.conflict import MemoryConflictResolver, cosine_similarity
from memory.decay import calculate_recency_score, compute_memory_score, is_memory_expired
from memory.manager import MemoryManager
from memory.types import (
    MemoryRecord,
    MemoryRetrievalResult,
    MemorySource,
    MemoryStats,
    MemoryStatus,
    MemoryType,
)
from memory.validator import (
    MemoryValidationError,
    compute_content_hash,
    validate_candidate_memory,
)
from rag.embedder import BaseEmbedder


class MockEmbedder(BaseEmbedder):
    """
    Deterministic mock embedder for testing vector operations.
    """

    async def embed(self, chunks):
        return chunks

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._vectorize(t) for t in texts]

    async def embed_query(self, query: str) -> list[float]:
        return self._vectorize(query)

    def _vectorize(self, text: str) -> list[float]:
        # Generate 1024-dim pseudo vector
        v = [0.0] * 1024
        t_low = text.lower()
        words = t_low.split()
        for idx, word in enumerate(words):
            bucket = sum(ord(c) for c in word) % 1024
            v[bucket] += 1.0 / (idx + 1.0)
        # Normalize
        norm = sum(x * x for x in v) ** 0.5
        if norm > 0:
            v = [x / norm for x in v]
        return v


# ── 1. Validation, Secret Protection & Code Dump Prevention ───────────────────


class TestMemoryValidation:

    def test_memory_creation_and_hashing(self):
        content = "  User prefers dark theme and Dracula palette.  "
        clean, conf, imp, c_hash = validate_candidate_memory(
            content=content,
            memory_type=MemoryType.USER_PREFERENCE,
            confidence=0.9,
            importance=0.8,
        )
        assert clean == "User prefers dark theme and Dracula palette."
        assert conf == 0.9
        assert imp == 0.8
        assert len(c_hash) == 64  # SHA-256 hex string

    def test_secret_protection_rejects_credentials(self):
        # Private key
        rsa_secret = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----"
        with pytest.raises(MemoryValidationError, match="sensitive credentials"):
            validate_candidate_memory(rsa_secret, MemoryType.USER_PREFERENCE)

        # API token
        api_key_secret = "Here is my secret: api_key = 'sk-1234567890abcdef1234567890abcdef'"
        with pytest.raises(MemoryValidationError, match="sensitive credentials"):
            validate_candidate_memory(api_key_secret, MemoryType.USER_PREFERENCE)

        # GitHub token
        gh_secret = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        with pytest.raises(MemoryValidationError, match="sensitive credentials"):
            validate_candidate_memory(gh_secret, MemoryType.USER_PREFERENCE)

    def test_short_and_oversized_content_rejected(self):
        with pytest.raises(MemoryValidationError, match="too short"):
            validate_candidate_memory("hi", MemoryType.USER_PREFERENCE)

        with pytest.raises(MemoryValidationError, match="too long"):
            validate_candidate_memory("a" * 5000, MemoryType.USER_PREFERENCE)

    def test_code_dump_prevention(self):
        # Multi-line python class dump
        code_dump = "import os\nfrom typing import List\n\nclass DataPipeline:\n" + "\n".join([f"    def step_{i}(self): pass" for i in range(50)])
        with pytest.raises(MemoryValidationError, match="raw source code dump"):
            validate_candidate_memory(code_dump, MemoryType.PROJECT_CONTEXT)


# ── 2. Memory Manager CRUD, Duplication & Stats ───────────────────────────────


@pytest.mark.asyncio
class TestMemoryManagerCRUD:

    async def test_create_and_retrieve_memory(self):
        manager = MemoryManager(embedder=MockEmbedder())
        proj_id = uuid.uuid4()

        rec = await manager.create_memory(
            content="Always use pytest-asyncio for asynchronous testing.",
            type=MemoryType.WORKFLOW_PATTERN,
            project_id=proj_id,
            importance=0.9,
            confidence=1.0,
        )

        assert rec.memory_id is not None
        assert rec.status == MemoryStatus.ACTIVE
        assert rec.type == MemoryType.WORKFLOW_PATTERN
        assert rec.project_id == proj_id

        # Retrieve by query
        results = await manager.retrieve_memories(
            query="how should we test async functions?",
            project_id=proj_id,
            top_k=3,
        )

        assert len(results) >= 1
        assert "pytest-asyncio" in results[0].content
        assert results[0].score > 0.3

    async def test_duplicate_prevention(self):
        manager = MemoryManager(embedder=MockEmbedder())
        proj_id = uuid.uuid4()

        rec1 = await manager.create_memory(
            content="Database migrations must run before tests.",
            type=MemoryType.DECISION,
            project_id=proj_id,
        )

        # Duplicate with different whitespace / casing
        rec2 = await manager.create_memory(
            content="  database   migrations must run before tests.  ",
            type=MemoryType.DECISION,
            project_id=proj_id,
        )

        # Should return existing record with same ID
        assert rec1.memory_id == rec2.memory_id
        stats = await manager.get_memory_status(proj_id)
        assert stats.active_count == 1

    async def test_update_archive_and_delete(self):
        manager = MemoryManager(embedder=MockEmbedder())
        rec = await manager.create_memory(
            content="Initial workflow rule",
            type=MemoryType.WORKFLOW_PATTERN,
        )

        # Update
        updated = await manager.update_memory(
            memory_id=rec.memory_id,
            content="Updated workflow rule with extra details",
            importance=0.95,
        )
        assert updated is not None
        assert updated.content == "Updated workflow rule with extra details"
        assert updated.importance == 0.95

        # Archive
        archived = await manager.archive_memory(rec.memory_id)
        assert archived is True
        fetched = await manager.get_memory(rec.memory_id)
        assert fetched.status == MemoryStatus.ARCHIVED

        # Delete
        deleted = await manager.delete_memory(rec.memory_id)
        assert deleted is True
        assert await manager.get_memory(rec.memory_id) is None


# ── 3. Conflict Handling & Superseding ────────────────────────────────────────


@pytest.mark.asyncio
class TestConflictAndSuperseding:

    async def test_contradictory_memory_supersedes_older(self):
        manager = MemoryManager(embedder=MockEmbedder())
        proj_id = uuid.uuid4()

        # Step 1: User says 4 spaces
        m1 = await manager.create_memory(
            content="User prefers 4 spaces for Python code indentation.",
            type=MemoryType.USER_PREFERENCE,
            project_id=proj_id,
        )
        assert m1.status == MemoryStatus.ACTIVE

        # Step 2: User changes mind to 2 spaces (high semantic overlap & same type/project)
        m2 = await manager.create_memory(
            content="User prefers 2 spaces for Python code indentation.",
            type=MemoryType.USER_PREFERENCE,
            project_id=proj_id,
        )

        assert m2.status == MemoryStatus.ACTIVE
        assert m1.status == MemoryStatus.SUPERSEDED
        assert m1.metadata.get("superseded_by") == str(m2.memory_id)
        assert m2.metadata.get("supersedes_id") == str(m1.memory_id)

        # Retrieval should only yield active m2
        results = await manager.retrieve_memories(
            query="what indentation does user prefer for python?",
            project_id=proj_id,
        )
        assert len(results) == 1
        assert "2 spaces" in results[0].content


# ── 4. Recency Decay & Expiration ─────────────────────────────────────────────


class TestDecayAndExpiration:

    def test_recency_decay_calculation(self):
        now = datetime.now(timezone.utc)
        # Immediate access has factor 1.0
        score_fresh = calculate_recency_score(now, now, half_life_days=30.0)
        assert score_fresh == 1.0

        # 30 days ago has factor ~0.50
        thirty_days_ago = now - timedelta(days=30)
        score_30d = calculate_recency_score(thirty_days_ago, now, half_life_days=30.0)
        assert pytest.approx(score_30d, 0.05) == 0.50

        # 60 days ago has factor ~0.25
        sixty_days_ago = now - timedelta(days=60)
        score_60d = calculate_recency_score(sixty_days_ago, now, half_life_days=30.0)
        assert pytest.approx(score_60d, 0.05) == 0.25

    def test_expiration_lifecycle(self):
        now = datetime.now(timezone.utc)
        rec = MemoryRecord(
            content="Temporary sprint goal",
            expiration_at=now - timedelta(hours=1),
        )
        assert is_memory_expired(rec, now) is True

        future_rec = MemoryRecord(
            content="Ongoing goal",
            expiration_at=now + timedelta(days=5),
        )
        assert is_memory_expired(future_rec, now) is False


# ── 5. Project Isolation ──────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestProjectIsolation:

    async def test_project_memories_are_isolated(self):
        manager = MemoryManager(embedder=MockEmbedder())
        proj_a = uuid.uuid4()
        proj_b = uuid.uuid4()

        # Project A memory
        await manager.create_memory(
            content="Project A uses PostgreSQL with pgvector.",
            type=MemoryType.PROJECT_CONTEXT,
            project_id=proj_a,
        )

        # Project B memory
        await manager.create_memory(
            content="Project B uses MongoDB for document storage.",
            type=MemoryType.PROJECT_CONTEXT,
            project_id=proj_b,
        )

        # Query from Project A
        res_a = await manager.retrieve_memories(
            query="which database is configured?",
            project_id=proj_a,
            include_global=False,
        )
        assert len(res_a) == 1
        assert "PostgreSQL" in res_a[0].content
        assert "MongoDB" not in res_a[0].content

        # Query from Project B
        res_b = await manager.retrieve_memories(
            query="which database is configured?",
            project_id=proj_b,
            include_global=False,
        )
        assert len(res_b) == 1
        assert "MongoDB" in res_b[0].content


# ── 6. Context Resolver & Context Package Assembly Integration ────────────────


class TestContextResolverAndAssembly:

    def test_resolver_routes_all_memory_types(self):
        resolver = ContextResolver()

        # User preferences
        src1 = resolver.resolve("What is my preference for python formatting?")
        assert SourceType.MEMORY in src1

        # Profile context
        src2 = resolver.resolve("Do you remember my role and background?")
        assert SourceType.MEMORY in src2

        # Project conventions & decisions
        src3 = resolver.resolve("What was our project convention for commit messages?")
        assert SourceType.MEMORY in src3

        # Workflow pattern
        src4 = resolver.resolve("What is my preferred workflow for staging deployments?")
        assert SourceType.MEMORY in src4

    def test_context_package_assembly_with_memory(self):
        builder = ContextPackageBuilder()

        memories = [
            MemoryRetrievalResult(
                record=MemoryRecord(
                    content="User prefers typing annotations on all function signatures.",
                    type=MemoryType.USER_PREFERENCE,
                ),
                score=0.92,
            ),
            MemoryRetrievalResult(
                record=MemoryRecord(
                    content="Never use Groq in production deployments.",
                    type=MemoryType.DECISION,
                ),
                score=0.88,
            ),
        ]

        package = builder.assemble(memory_entries=memories)

        assert SourceType.MEMORY in package.resolved_sources
        assert len(package.items) == 2
        assert "=== [MEMORY] User Preferences & Persistent Context ===" in package.formatted_text
        assert "USER_PREFERENCE" in package.formatted_text
        assert "DECISION" in package.formatted_text
        assert package.token_count > 0


# ── 7. Core Memory Wrapper Session Integration ────────────────────────────────


@pytest.mark.asyncio
class TestCoreMemoryWrapper:

    async def test_core_memory_wrapper_operations(self):
        session_id = uuid.uuid4()
        project_id = uuid.uuid4()
        mem_manager = MemoryManager(embedder=MockEmbedder())

        session_memory = Memory(
            session_id=session_id,
            project_id=project_id,
            db=None,
            redis=None,
            memory_manager=mem_manager,
        )

        # Persist turn
        rec = await session_memory.persist(
            user_message="Please remember to always run pytest before git push",
            assistant_response="Understood, I will ensure tests run before committing.",
            memory_type=MemoryType.WORKFLOW_PATTERN,
        )
        assert rec is not None

        # Retrieve
        entries = await session_memory.retrieve("what should we do before git push?")
        assert len(entries) >= 1
        assert "pytest" in entries[0].content
