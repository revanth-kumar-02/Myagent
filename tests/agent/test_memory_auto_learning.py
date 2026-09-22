"""
tests.test_memory_auto_learning — Verification suite for Memory UX & Automatic Learning (V2)

Tests:
1. Explicit preference → memory candidate → stored memory
2. Temporary conversation → no permanent memory
3. Duplicate memory → merged/ignored
4. Contradicting memory → resolved & superseded
5. Project memory → isolated to project scope
6. Relevant memory → retrieved by Kora
7. Irrelevant memory → not retrieved
8. Secret/credential → rejected completely
9. User correction → memory updated
10. User forget → memory removed
11. Empty database → no fake memories
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

# Ensure apps/agent is resolvable by language server and pytest runner
_agent_path = Path(__file__).resolve().parents[2] / "apps" / "agent"
if str(_agent_path) not in sys.path:
    sys.path.insert(0, str(_agent_path))

import pytest

from core.memory import Memory
from graph.service import KnowledgeGraphService
from memory.extractor import MemoryCandidateDetector
from memory.manager import MemoryManager
from memory.types import MemorySource, MemoryStatus, MemoryType
from memory.validator import MemoryValidationError
from rag.embedder import BaseEmbedder


class MockEmbedder(BaseEmbedder):
    """Deterministic pseudo-embedder for vector retrieval testing."""

    async def embed(self, chunks):
        return chunks

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._vectorize(t) for t in texts]

    async def embed_query(self, query: str) -> list[float]:
        return self._vectorize(query)

    def _vectorize(self, text: str) -> list[float]:
        v = [0.0] * 1024
        t_low = text.lower()
        words = t_low.split()
        for idx, word in enumerate(words):
            bucket = sum(ord(c) for c in word) % 1024
            v[bucket] += 1.0 / (idx + 1.0)
        norm = sum(x * x for x in v) ** 0.5
        if norm > 0:
            v = [x / norm for x in v]
        return v


@pytest.fixture
def embedder() -> MockEmbedder:
    return MockEmbedder()


@pytest.fixture
def memory_manager(embedder: MockEmbedder) -> MemoryManager:
    return MemoryManager(embedder=embedder)


@pytest.fixture
def graph_service() -> KnowledgeGraphService:
    return KnowledgeGraphService()


@pytest.fixture
def memory_system(memory_manager: MemoryManager, graph_service: KnowledgeGraphService) -> Memory:
    session_id = uuid.uuid4()
    project_id = uuid.uuid4()
    return Memory(
        session_id=session_id,
        project_id=project_id,
        db=None,
        redis=None,
        memory_manager=memory_manager,
        graph_service=graph_service,
    )


# ── Verification Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_1_explicit_preference_creates_stored_memory(memory_system: Memory):
    """1. Explicit preference → memory candidate → stored memory."""
    user_msg = "I prefer Python for backend development and always use pytest for testing."
    record = await memory_system.persist(user_msg, "Understood! I will use Python and pytest.")

    assert record is not None
    assert record.type == MemoryType.USER_PREFERENCE
    assert record.status == MemoryStatus.ACTIVE
    assert "Python" in record.content or "python" in record.content.lower()
    assert record.confidence >= 0.9


@pytest.mark.asyncio
async def test_2_temporary_conversation_no_permanent_memory(memory_system: Memory):
    """2. Temporary conversation → no permanent memory."""
    transient_inputs = [
        "Hello Kora, good morning!",
        "What is 2 + 2?",
        "Tell me a quick joke.",
        "Open VSCode please.",
        "Thanks, got it!",
        "What time is it right now?",
    ]

    for msg in transient_inputs:
        record = await memory_system.persist(msg, "Here is your quick response.")
        assert record is None, f"Transient message '{msg}' should NOT create a memory"


@pytest.mark.asyncio
async def test_3_duplicate_memory_merged_or_ignored(memory_system: Memory):
    """3. Duplicate memory → merged/ignored."""
    msg = "I always prefer dark theme for IDE and dashboards."
    record1 = await memory_system.persist(msg)
    record2 = await memory_system.persist(msg)

    assert record1 is not None
    assert record2 is not None
    assert record1.memory_id == record2.memory_id


@pytest.mark.asyncio
async def test_4_contradicting_memory_superseded(memory_system: Memory):
    """4. Contradicting memory → resolved and older superseded."""
    # First preference
    rec1 = await memory_system.persist("I prefer dark mode in all UI applications.")
    assert rec1 is not None
    assert rec1.status == MemoryStatus.ACTIVE

    # Contradicting new preference
    rec2 = await memory_system.persist("I prefer light mode in all UI applications from now on.")
    assert rec2 is not None
    assert rec2.status == MemoryStatus.ACTIVE
    assert rec2.memory_id != rec1.memory_id

    # Check that older contradictory memory was superseded
    old_rec = await memory_system.manager.get_memory(rec1.memory_id)
    assert old_rec is not None
    assert old_rec.status == MemoryStatus.SUPERSEDED


@pytest.mark.asyncio
async def test_5_project_memory_isolated_to_project(embedder: MockEmbedder):
    """5. Project memory → isolated to project scope."""
    proj_a = uuid.uuid4()
    proj_b = uuid.uuid4()

    mgr = MemoryManager(embedder=embedder)

    # Save to Project A
    rec_a = await mgr.create_memory(
        content="This project is built using Flutter Desktop and Riverpod.",
        type=MemoryType.PROJECT_CONTEXT,
        project_id=proj_a,
    )

    # Save to Project B
    rec_b = await mgr.create_memory(
        content="This project is built using React Native and Redux.",
        type=MemoryType.PROJECT_CONTEXT,
        project_id=proj_b,
    )

    # Retrieve from Project A
    results_a = await mgr.retrieve_memories("state management", project_id=proj_a, include_global=False)
    assert any(r.record.memory_id == rec_a.memory_id for r in results_a)
    assert not any(r.record.memory_id == rec_b.memory_id for r in results_a)


@pytest.mark.asyncio
async def test_6_relevant_memory_retrieved(memory_system: Memory):
    """6. Relevant memory → retrieved by Kora."""
    await memory_system.persist("My name is Alice and I work as a Staff Systems Architect.")
    await memory_system.persist("We decided to use PostgreSQL with pgvector for memory storage.")

    retrieved = await memory_system.retrieve("What database do we use for vectors?")
    assert len(retrieved) > 0
    assert any("PostgreSQL" in r.content or "pgvector" in r.content for r in retrieved)


@pytest.mark.asyncio
async def test_7_irrelevant_memory_not_retrieved(memory_system: Memory):
    """7. Irrelevant memory → not retrieved."""
    await memory_system.persist("User prefers dark theme for IDE.")

    retrieved = await memory_system.retrieve("How do I compute eigenvalues in numpy?")
    # Dark theme preference should not match eigenvalue question above threshold
    matching_pref = [r for r in retrieved if "dark theme" in r.content.lower()]
    assert len(matching_pref) == 0


@pytest.mark.asyncio
async def test_8_secret_credential_rejected(memory_system: Memory):
    """8. Secret/credential → rejected completely."""
    secret_msgs = [
        "Please remember my token: ghp_1234567890abcdefghijklmnopqrstuvwxyz",
        "My API secret key is sk-1234567890abcdef1234567890abcdef",
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----",
        "My master password is SuperSecretPassword123!",
    ]

    for sec in secret_msgs:
        rec = await memory_system.persist(sec)
        assert rec is None, f"Sensitive secret '{sec}' must NOT create memory"


@pytest.mark.asyncio
async def test_9_user_correction_updates_memory(memory_system: Memory):
    """9. User correction → memory updated."""
    rec = await memory_system.persist("I prefer Python for backend scripts.")
    assert rec is not None

    # Correct memory
    updated = await memory_system.manager.update_memory(
        memory_id=rec.memory_id,
        content="User prefers Python 3.14 with strict typing for backend services.",
        confidence=0.98,
    )

    assert updated is not None
    assert updated.content == "User prefers Python 3.14 with strict typing for backend services."
    assert updated.confidence == 0.98


@pytest.mark.asyncio
async def test_10_user_forget_removes_memory(memory_system: Memory):
    """10. User forget → memory removed."""
    rec = await memory_system.persist("I always use vim keybindings in IDE.")
    assert rec is not None

    deleted = await memory_system.manager.delete_memory(rec.memory_id)
    assert deleted is True

    fetched = await memory_system.manager.get_memory(rec.memory_id)
    assert fetched is None


@pytest.mark.asyncio
async def test_11_empty_database_no_fake_memories(embedder: MockEmbedder):
    """11. Empty database → no fake memories."""
    mgr = MemoryManager(embedder=embedder)
    stats = await mgr.get_memory_status()
    assert stats.total_memories == 0
    assert stats.active_count == 0

    results = await mgr.retrieve_memories("anything")
    assert len(results) == 0
