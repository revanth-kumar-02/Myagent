"""rag package — RAG V2 Retrieval Engine."""

from rag.types import (
    Chunk,
    DocumentType,
    FileEvent,
    FileEventType,
    IndexStats,
    ParsedDocument,
    RAGContext,
    RetrievalResult,
    RetrievedChunk,
    SearchMode,
)
from rag.scanner import Scanner
from rag.parser import Parser
from rag.chunker import StructuralChunker
from rag.embedder import BaseEmbedder, EmbeddingError, EmbeddingService
from rag.indexer import Indexer
from rag.retriever import RAGRetriever
from rag.reranker import BaseReranker, CrossEncoderReranker, NoOpReranker, Reranker
from rag.context_builder import ContextBuilder
from rag.engine import RetrievalEngine

__all__ = [
    "Chunk",
    "DocumentType",
    "FileEvent",
    "FileEventType",
    "IndexStats",
    "ParsedDocument",
    "RAGContext",
    "RetrievalResult",
    "RetrievedChunk",
    "SearchMode",
    "Scanner",
    "Parser",
    "StructuralChunker",
    "BaseEmbedder",
    "EmbeddingError",
    "EmbeddingService",
    "Indexer",
    "RAGRetriever",
    "BaseReranker",
    "CrossEncoderReranker",
    "NoOpReranker",
    "Reranker",
    "ContextBuilder",
    "RetrievalEngine",
]
