# KORA — RAG V3: DOCUMENT INTELLIGENCE VERIFICATION REPORT

## Execution Summary

- **Date**: 2026-09-18
- **Platform**: Linux (x86_64), Python 3.14.4
- **Test Framework**: Pytest 9.0.2 + pytest-asyncio
- **Status**: **100% PASS** (45/45 tests passed)

---

## Test Results by Category

### 1. Document Intelligence Suite (`tests/agent/test_rag_v3_document_intelligence.py`)

| Test Case | Format / Category | Status |
|---|---|---|
| `test_pdf_parsing_and_page_chunking` | PDF Page & Heading Extraction | **PASSED** |
| `test_docx_parsing_headings_and_tables` | Word Heading Levels & Tables | **PASSED** |
| `test_xlsx_spreadsheet_sheets_and_cell_ranges` | Multi-Sheet & Cell Range Calculation | **PASSED** |
| `test_pptx_presentation_slide_chunking` | Slide Title & Shape Text Chunking | **PASSED** |
| `test_csv_header_aware_chunking` | Header-Aware Row Batching | **PASSED** |
| `test_sheet_intent_query_boosting` | Provenance Query: "Which sheet contains X?" | **PASSED** |
| `test_page_intent_query_boosting` | Provenance Query: "Show information from page X" | **PASSED** |
| `test_slide_intent_query_boosting` | Provenance Query: "Find the slide about X" | **PASSED** |
| `test_context_builder_formats_all_document_types` | Multi-Format Rich Provenance Context | **PASSED** |

### 2. Retrieval Engine Suite (`tests/agent/test_rag_v2_retrieval.py`)

| Test Case | Description | Status |
|---|---|---|
| `test_semantic_retrieval_flow` | Dense vector similarity search | **PASSED** |
| `test_keyword_retrieval_flow` | Sparse full-text BM25 search | **PASSED** |
| `test_exact_symbol_match_boosts_score` | Exact symbol match rank boost | **PASSED** |
| `test_path_match_boost` | File path query match boost | **PASSED** |
| `test_duplicate_removal_by_id_and_span` | Overlap and duplicate removal | **PASSED** |
| `test_metadata_filtering_by_doc_type_and_path` | Post-filtering by metadata | **PASSED** |
| `test_cross_encoder_reranker` | Cross-encoder reranking | **PASSED** |
| `test_noop_reranker` | No-op pass-through reranker | **PASSED** |
| `test_rich_provenance_formatting` | Provenance tag construction | **PASSED** |
| `test_sensitive_content_filtering` | Secret & private key protection | **PASSED** |
| `test_embedder_dimension_validation` | 1024-dimension enforcement | **PASSED** |
| `test_embed_empty_query_raises` | Empty query error handling | **PASSED** |
| `test_retrieval_engine_facade` | Public facade API | **PASSED** |
| `test_empty_query_returns_empty_results` | Empty query handling | **PASSED** |
| `test_invalid_project_id_raises_value_error` | UUID validation | **PASSED** |

### 3. RAG Pipeline Suite (`tests/agent/test_rag_pipeline.py`)

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
| `test_rrf_project_isolation` | Project Isolation | **PASSED** |
| `test_context_respects_token_budget` | Context Builder | **PASSED** |
| `test_sources_match_included_chunks` | Context Builder | **PASSED** |

### 4. Integration Suite (`tests/agent/test_rag_integration.py`)

| Test Case | Category | Status |
|---|---|---|
| `test_spreadsheet_xlsx_parsing_and_chunking` | Multi-Format Ingestion | **PASSED** |
| `test_multilingual_code_parsing` | Multi-Language Parsing | **PASSED** |
| `test_embed_chunks_mocked_or_direct` | Batch Embedding | **PASSED** |
| `test_embed_query` | Query Vectorization | **PASSED** |
| `test_reranker_scores_and_sorts` | Reranker Scoring | **PASSED** |
| `test_indexer_workflow` | Incremental Indexing | **PASSED** |
| `test_retriever_enforces_project_id` | Project Isolation | **PASSED** |

---

## Pytest Raw Console Output

```
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.0.2, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/rev/My_Personal_Space/Projects/Unfinished/Myagent
plugins: asyncio-1.4.0, anyio-4.14.2, typeguard-4.4.4
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collecting 4 items                                                             collected 45 items                                                             

tests/agent/test_rag_pipeline.py::TestScanner::test_detect_added_files PASSED [  2%]
tests/agent/test_rag_pipeline.py::TestScanner::test_detect_changed_files_by_hash PASSED [  4%]
tests/agent/test_rag_pipeline.py::TestScanner::test_detect_deleted_files PASSED [  6%]
tests/agent/test_rag_pipeline.py::TestScanner::test_ignores_default_patterns PASSED [  8%]
tests/agent/test_rag_pipeline.py::TestParser::test_parse_code PASSED     [ 11%]
tests/agent/test_rag_pipeline.py::TestParser::test_parse_markdown PASSED [ 13%]
tests/agent/test_rag_pipeline.py::TestParser::test_parse_plain PASSED    [ 15%]
tests/agent/test_rag_pipeline.py::TestStructuralChunker::test_code_chunk_respects_token_limit PASSED [ 17%]
tests/agent/test_rag_pipeline.py::TestStructuralChunker::test_markdown_chunk_preserves_heading_hierarchy PASSED [ 20%]
tests/agent/test_rag_pipeline.py::TestStructuralChunker::test_chunk_carries_provenance_metadata PASSED [ 22%]
tests/agent/test_rag_pipeline.py::TestRRFFusion::test_rrf_score_increases_with_dual_ranking PASSED [ 24%]
tests/agent/test_rag_pipeline.py::TestRRFFusion::test_rrf_project_isolation PASSED [ 26%]
tests/agent/test_rag_pipeline.py::TestContextBuilder::test_context_respects_token_budget PASSED [ 28%]
tests/agent/test_rag_pipeline.py::TestContextBuilder::test_sources_match_included_chunks PASSED [ 31%]
tests/agent/test_rag_integration.py::TestRAGFormats::test_spreadsheet_xlsx_parsing_and_chunking PASSED [ 33%]
tests/agent/test_rag_integration.py::TestRAGFormats::test_multilingual_code_parsing PASSED [ 35%]
tests/agent/test_rag_integration.py::TestEmbeddingService::test_embed_chunks_mocked_or_direct PASSED [ 37%]
tests/agent/test_rag_integration.py::TestEmbeddingService::test_embed_query PASSED [ 40%]
tests/agent/test_rag_integration.py::TestReranker::test_reranker_scores_and_sorts PASSED [ 42%]
tests/agent/test_rag_integration.py::TestIncrementalIndexer::test_indexer_workflow PASSED [ 44%]
tests/agent/test_rag_integration.py::TestProjectIsolation::test_retriever_enforces_project_id PASSED [ 46%]
tests/agent/test_rag_v2_retrieval.py::TestSemanticAndKeywordRetrieval::test_semantic_retrieval_flow PASSED [ 48%]
tests/agent/test_rag_v2_retrieval.py::TestSemanticAndKeywordRetrieval::test_keyword_retrieval_flow PASSED [ 51%]
tests/agent/test_rag_v2_retrieval.py::TestMultiSignalHybridRanking::test_exact_symbol_match_boosts_score PASSED [ 53%]
tests/agent/test_rag_v2_retrieval.py::TestMultiSignalHybridRanking::test_path_match_boost PASSED [ 55%]
tests/agent/test_rag_v2_retrieval.py::TestDeduplicationAndFiltering::test_duplicate_removal_by_id_and_span PASSED [ 57%]
tests/agent/test_rag_v2_retrieval.py::TestDeduplicationAndFiltering::test_metadata_filtering_by_doc_type_and_path PASSED [ 60%]
tests/agent/test_rag_v2_retrieval.py::TestRerankerAbstraction::test_cross_encoder_reranker PASSED [ 62%]
tests/agent/test_rag_v2_retrieval.py::TestRerankerAbstraction::test_noop_reranker PASSED [ 64%]
tests/agent/test_rag_v2_retrieval.py::TestRichProvenanceContextBuilder::test_rich_provenance_formatting PASSED [ 66%]
tests/agent/test_rag_v2_retrieval.py::TestEmbeddingPipelineEdgeCases::test_sensitive_content_filtering PASSED [ 68%]
tests/agent/test_rag_v2_retrieval.py::TestEmbeddingPipelineEdgeCases::test_embedder_dimension_validation PASSED [ 71%]
tests/agent/test_rag_v2_retrieval.py::TestEmbeddingPipelineEdgeCases::test_embed_empty_query_raises PASSED [ 73%]
tests/agent/test_rag_v2_retrieval.py::TestRetrievalEngineAPI::test_retrieval_engine_facade PASSED [ 75%]
tests/agent/test_rag_v2_retrieval.py::TestRetrievalEngineAPI::test_empty_query_returns_empty_results PASSED [ 77%]
tests/agent/test_rag_v2_retrieval.py::TestRetrievalEngineAPI::test_invalid_project_id_raises_value_error PASSED [ 80%]
tests/agent/test_rag_v3_document_intelligence.py::TestDocumentParsingAndChunking::test_pdf_parsing_and_page_chunking PASSED [ 82%]
tests/agent/test_rag_v3_document_intelligence.py::TestDocumentParsingAndChunking::test_docx_parsing_headings_and_tables PASSED [ 84%]
tests/agent/test_rag_v3_document_intelligence.py::TestDocumentParsingAndChunking::test_xlsx_spreadsheet_sheets_and_cell_ranges PASSED [ 86%]
tests/agent/test_rag_v3_document_intelligence.py::TestDocumentParsingAndChunking::test_pptx_presentation_slide_chunking PASSED [ 88%]
tests/agent/test_rag_v3_document_intelligence.py::TestDocumentParsingAndChunking::test_csv_header_aware_chunking PASSED [ 91%]
tests/agent/test_rag_v3_document_intelligence.py::TestStructuralProvenanceRetrieval::test_sheet_intent_query_boosting PASSED [ 93%]
tests/agent/test_rag_v3_document_intelligence.py::TestStructuralProvenanceRetrieval::test_page_intent_query_boosting PASSED [ 95%]
tests/agent/test_rag_v3_document_intelligence.py::TestStructuralProvenanceRetrieval::test_slide_intent_query_boosting PASSED [ 97%]
tests/agent/test_rag_v3_document_intelligence.py::TestRichProvenanceContextBuilderV3::test_context_builder_formats_all_document_types PASSED [100%]

============================== 45 passed in 1.97s ==============================
```
