# KORA — RAG V2: RETRIEVAL ENGINE VERIFICATION REPORT

## Execution Summary

- **Date**: 2026-09-18
- **Platform**: Linux (x86_64), Python 3.14.4
- **Test Framework**: Pytest 9.0.2 + pytest-asyncio
- **Status**: **100% PASS** (36/36 tests passed)

---

## Test Results by Category

### 1. RAG V2 Retrieval Engine Suite (`tests/agent/test_rag_v2_retrieval.py`)

| Test Case | Description | Status |
|---|---|---|
| `test_semantic_retrieval_flow` | Vector cosine similarity search via pgvector bindings | **PASSED** |
| `test_keyword_retrieval_flow` | Full-text search via PostgreSQL tsvector / ts_rank | **PASSED** |
| `test_exact_symbol_match_boosts_score` | Exact symbol and identifier matching boosts rank to #1 | **PASSED** |
| `test_path_match_boost` | File path and directory term matching boost | **PASSED** |
| `test_duplicate_removal_by_id_and_span` | Removal of duplicate chunk IDs and overlapping line spans | **PASSED** |
| `test_metadata_filtering_by_doc_type_and_path` | Strict post-filtering by `doc_type` and `file_path` | **PASSED** |
| `test_cross_encoder_reranker` | Cross-encoder relevance scoring and top-k truncation | **PASSED** |
| `test_noop_reranker` | Zero-overhead pass-through reranker | **PASSED** |
| `test_rich_provenance_formatting` | Formats file, line span, type, symbol, heading, and score | **PASSED** |
| `test_sensitive_content_filtering` | Guards against embedding private keys, tokens, and credentials | **PASSED** |
| `test_embedder_dimension_validation` | Enforces uniform vector dimensions (`1024`) | **PASSED** |
| `test_embed_empty_query_raises` | Handles empty / whitespace query strings safely | **PASSED** |
| `test_retrieval_engine_facade` | Public facade methods (`search`, `retrieve_context`) | **PASSED** |
| `test_empty_query_returns_empty_results` | Returns empty results on empty query without failing | **PASSED** |
| `test_invalid_project_id_raises_value_error` | Validates UUID project identifiers | **PASSED** |

### 2. RAG Foundation Pipeline Suite (`tests/agent/test_rag_pipeline.py`)

| Test Case | Category | Status |
|---|---|---|
| `test_detect_added_files` | Scanner | **PASSED** |
| `test_detect_changed_files_by_hash` | Scanner | **PASSED** |
| `test_detect_deleted_files` | Scanner | **PASSED** |
| `test_ignores_default_patterns` | Scanner | **PASSED** |
| `test_parse_code` | Parser | **PASSED** |
| `test_parse_markdown` | Parser | **PASSED** |
| `test_parse_plain` | Parser | **PASSED** |
| `test_code_chunk_respects_token_limit` | Chunker | **PASSED** |
| `test_markdown_chunk_preserves_heading_hierarchy` | Chunker | **PASSED** |
| `test_chunk_carries_provenance_metadata` | Chunker | **PASSED** |
| `test_rrf_score_increases_with_dual_ranking` | RRF Fusion | **PASSED** |
| `test_rrf_project_isolation` | Project Scoping | **PASSED** |
| `test_context_respects_token_budget` | Context Builder | **PASSED** |
| `test_sources_match_included_chunks` | Context Builder | **PASSED** |

### 3. End-to-End Integration Suite (`tests/agent/test_rag_integration.py`)

| Test Case | Category | Status |
|---|---|---|
| `test_spreadsheet_xlsx_parsing_and_chunking` | Multi-Format Ingestion | **PASSED** |
| `test_multilingual_code_parsing` | Dart/TS/SQL/HTML Parsing | **PASSED** |
| `test_embed_chunks_mocked_or_direct` | Batch Embedding | **PASSED** |
| `test_embed_query` | Query Vectorization | **PASSED** |
| `test_reranker_scores_and_sorts` | Cross-Encoder Reranking | **PASSED** |
| `test_indexer_workflow` | Incremental Ingestion & DB Upsert | **PASSED** |
| `test_retriever_enforces_project_id` | Strict Project Isolation | **PASSED** |

---

## Pytest Raw Console Output

```
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.0.2, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/rev/My_Personal_Space/Projects/Unfinished/Myagent
plugins: asyncio-1.4.0, anyio-4.14.2, typeguard-4.4.4
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collecting 4 items                                                             collected 36 items                                                             

tests/agent/test_rag_pipeline.py::TestScanner::test_detect_added_files PASSED [  2%]
tests/agent/test_rag_pipeline.py::TestScanner::test_detect_changed_files_by_hash PASSED [  5%]
tests/agent/test_rag_pipeline.py::TestScanner::test_detect_deleted_files PASSED [  8%]
tests/agent/test_rag_pipeline.py::TestScanner::test_ignores_default_patterns PASSED [ 11%]
tests/agent/test_rag_pipeline.py::TestParser::test_parse_code PASSED     [ 13%]
tests/agent/test_rag_pipeline.py::TestParser::test_parse_markdown PASSED [ 16%]
tests/agent/test_rag_pipeline.py::TestParser::test_parse_plain PASSED    [ 19%]
tests/agent/test_rag_pipeline.py::TestStructuralChunker::test_code_chunk_respects_token_limit PASSED [ 22%]
tests/agent/test_rag_pipeline.py::TestStructuralChunker::test_markdown_chunk_preserves_heading_hierarchy PASSED [ 25%]
tests/agent/test_rag_pipeline.py::TestStructuralChunker::test_chunk_carries_provenance_metadata PASSED [ 27%]
tests/agent/test_rag_pipeline.py::TestRRFFusion::test_rrf_score_increases_with_dual_ranking PASSED [ 30%]
tests/agent/test_rag_pipeline.py::TestRRFFusion::test_rrf_project_isolation PASSED [ 33%]
tests/agent/test_rag_pipeline.py::TestContextBuilder::test_context_respects_token_budget PASSED [ 36%]
tests/agent/test_rag_pipeline.py::TestContextBuilder::test_sources_match_included_chunks PASSED [ 38%]
tests/agent/test_rag_integration.py::TestRAGFormats::test_spreadsheet_xlsx_parsing_and_chunking PASSED [ 41%]
tests/agent/test_rag_integration.py::TestRAGFormats::test_multilingual_code_parsing PASSED [ 44%]
tests/agent/test_rag_integration.py::TestEmbeddingService::test_embed_chunks_mocked_or_direct PASSED [ 47%]
tests/agent/test_rag_integration.py::TestEmbeddingService::test_embed_query PASSED [ 50%]
tests/agent/test_rag_integration.py::TestReranker::test_reranker_scores_and_sorts PASSED [ 52%]
tests/agent/test_rag_integration.py::TestIncrementalIndexer::test_indexer_workflow PASSED [ 55%]
tests/agent/test_rag_integration.py::TestProjectIsolation::test_retriever_enforces_project_id PASSED [ 58%]
tests/agent/test_rag_v2_retrieval.py::TestSemanticAndKeywordRetrieval::test_semantic_retrieval_flow PASSED [ 61%]
tests/agent/test_rag_v2_retrieval.py::TestSemanticAndKeywordRetrieval::test_keyword_retrieval_flow PASSED [ 63%]
tests/agent/test_rag_v2_retrieval.py::TestMultiSignalHybridRanking::test_exact_symbol_match_boosts_score PASSED [ 66%]
tests/agent/test_rag_v2_retrieval.py::TestMultiSignalHybridRanking::test_path_match_boost PASSED [ 69%]
tests/agent/test_rag_v2_retrieval.py::TestDeduplicationAndFiltering::test_duplicate_removal_by_id_and_span PASSED [ 72%]
tests/agent/test_rag_v2_retrieval.py::TestDeduplicationAndFiltering::test_metadata_filtering_by_doc_type_and_path PASSED [ 75%]
tests/agent/test_rag_v2_retrieval.py::TestRerankerAbstraction::test_cross_encoder_reranker PASSED [ 77%]
tests/agent/test_rag_v2_retrieval.py::TestRerankerAbstraction::test_noop_reranker PASSED [ 80%]
tests/agent/test_rag_v2_retrieval.py::TestRichProvenanceContextBuilder::test_rich_provenance_formatting PASSED [ 83%]
tests/agent/test_rag_v2_retrieval.py::TestEmbeddingPipelineEdgeCases::test_sensitive_content_filtering PASSED [ 86%]
tests/agent/test_rag_v2_retrieval.py::TestEmbeddingPipelineEdgeCases::test_embedder_dimension_validation PASSED [ 88%]
tests/agent/test_rag_v2_retrieval.py::TestEmbeddingPipelineEdgeCases::test_embed_empty_query_raises PASSED [ 91%]
tests/agent/test_rag_v2_retrieval.py::TestRetrievalEngineAPI::test_retrieval_engine_facade PASSED [ 94%]
tests/agent/test_rag_v2_retrieval.py::TestRetrievalEngineAPI::test_empty_query_returns_empty_results PASSED [ 97%]
tests/agent/test_rag_v2_retrieval.py::TestRetrievalEngineAPI::test_invalid_project_id_raises_value_error PASSED [100%]

============================== 36 passed in 1.56s ==============================
```
