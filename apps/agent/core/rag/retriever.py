import re
import logging
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
from sqlalchemy.future import select
from sqlalchemy import and_, or_

import db.session as db_session
from db.session import AsyncSessionLocal
from db.models import ProjectChunk
from core.embeddings import default_embedding_provider, BaseEmbeddingProvider
from core.memory import cosine_similarity

logger = logging.getLogger(__name__)

class SearchResultChunk(BaseModel):
    id: str
    project_id: str
    file_path: str
    language: str
    chunk_index: int
    symbol: Optional[str] = None
    content: str
    relevance: float
    match_type: str = "hybrid"

class ProjectRagRetriever:
    """
    Hybrid RAG retrieval engine enforcing strict project isolation.
    Combines pgvector/cosine semantic vector similarity, keyword/token matching,
    symbol bonus, and metadata filtering.
    """

    def __init__(self, embedding_provider: Optional[BaseEmbeddingProvider] = None):
        self.embedding_provider = embedding_provider or default_embedding_provider

    def get_active_vector_backend(self) -> str:
        if db_session.IS_POSTGRES_ACTIVE and db_session.IS_PGVECTOR_AVAILABLE:
            return "NATIVE_PGVECTOR"
        elif db_session.IS_POSTGRES_ACTIVE:
            return "POSTGRES_PYTHON_FALLBACK"
        else:
            return "SQLITE_PYTHON_FALLBACK"

    async def search(
        self,
        query: str,
        project_id: str,
        limit: int = 10,
        language: Optional[str] = None,
        file_path_filter: Optional[str] = None
    ) -> List[SearchResultChunk]:
        """
        Executes deterministic hybrid search scoped strictly to `project_id`.
        """
        if not project_id:
            raise ValueError("project_id is required for project RAG search")

        clean_query = query.strip()
        if not clean_query:
            return []

        # 1. Compute query vector
        query_vec = await self.embedding_provider.get_embedding(clean_query)

        # 2. Query candidates from database enforcing strict project boundaries
        async with AsyncSessionLocal() as db:
            conditions = [ProjectChunk.project_id == project_id]
            if language:
                conditions.append(ProjectChunk.language == language.lower())
            if file_path_filter:
                conditions.append(ProjectChunk.file_path.ilike(f"%{file_path_filter}%"))

            stmt = select(ProjectChunk).where(and_(*conditions))

            # If native pgvector is available, utilize native cosine distance ordering
            backend = self.get_active_vector_backend()
            if backend == "NATIVE_PGVECTOR":
                try:
                    stmt = stmt.order_by(ProjectChunk.embedding.cosine_distance(query_vec)).limit(limit * 4)
                except Exception as e:
                    logger.warning(f"Native pgvector distance ordering fallback: {e}")
                    stmt = stmt.limit(150)
            else:
                stmt = stmt.limit(200)

            res = await db.execute(stmt)
            candidates = res.scalars().all()

        if not candidates:
            return []

        # 3. Hybrid scoring: vector similarity + keyword token match + symbol bonus
        q_tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9_]+", clean_query) if len(t) > 1]
        scored_candidates: List[Tuple[float, ProjectChunk]] = []

        for chunk in candidates:
            # 3.1 Vector similarity
            vec_sim = 0.0
            if chunk.embedding and isinstance(chunk.embedding, list):
                vec_sim = max(0.0, cosine_similarity(query_vec, chunk.embedding))

            # 3.2 Keyword token matching
            content_lower = chunk.content.lower()
            sym_lower = (chunk.symbol or "").lower()
            path_lower = chunk.file_path.lower()

            matches = 0
            for t in q_tokens:
                if t in content_lower:
                    matches += 1
                if t in sym_lower:
                    matches += 1.5
                if t in path_lower:
                    matches += 1.0

            total_tokens = max(1, len(q_tokens))
            kw_score = min(1.0, matches / (total_tokens * 1.5))

            # 3.3 Exact symbol or exact phrase bonus
            bonus = 0.0
            if sym_lower and any(t in sym_lower for t in q_tokens):
                bonus += 0.15
            if clean_query.lower() in content_lower:
                bonus += 0.10

            # Deterministic hybrid score (0.0 to 1.0)
            final_relevance = round(
                (0.50 * vec_sim) + (0.35 * kw_score) + min(0.15, bonus),
                4
            )
            scored_candidates.append((final_relevance, chunk))

        # 4. Sort deterministically by relevance descending, then chunk_index ascending
        scored_candidates.sort(key=lambda x: (x[0], -x[1].chunk_index), reverse=True)

        results: List[SearchResultChunk] = []
        for rel, chunk in scored_candidates[:limit]:
            results.append(
                SearchResultChunk(
                    id=chunk.id,
                    project_id=chunk.project_id,
                    file_path=chunk.file_path,
                    language=chunk.language,
                    chunk_index=chunk.chunk_index,
                    symbol=chunk.symbol,
                    content=chunk.content,
                    relevance=rel,
                    match_type="hybrid"
                )
            )

        return results

project_rag_retriever = ProjectRagRetriever()
