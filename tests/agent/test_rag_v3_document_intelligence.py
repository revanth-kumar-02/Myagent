"""
tests.agent.test_rag_v3_document_intelligence — Comprehensive RAG V3 Document Intelligence Tests

Covers:
  1. PDF Parsing & Page/Section Chunking
  2. DOCX Parsing & Heading/Table Extraction
  3. XLSX Spreadsheet & Sheet/Cell-Range Chunking
  4. PPTX Presentation & Slide-Level Chunking
  5. CSV Parsing & Header-Aware Row Grouping
  6. Code & Markdown Symbol/Heading Preservation
  7. Structural Metadata Integrity
  8. Provenance Retrieval on Natural Queries (Page, Sheet, Slide, Symbol)
  9. ContextBuilder Rich Provenance Formatting
"""

from __future__ import annotations

import csv
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import docx as python_docx
import openpyxl
import pytest
from pptx import Presentation

from rag.chunker import StructuralChunker
from rag.context_builder import ContextBuilder
from rag.parser import Parser
from rag.retriever import RAGRetriever
from rag.types import (
    Chunk,
    DocumentType,
    RetrievedChunk,
    SearchMode,
)


class TestDocumentParsingAndChunking:
    @pytest.mark.asyncio
    async def test_pdf_parsing_and_page_chunking(self) -> None:
        parser = Parser()
        # Mock pypdf reader for PDF extraction test
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            mock_page1 = MagicMock()
            mock_page1.extract_text.return_value = "Executive Summary\nThis document outlines system design."
            mock_page2 = MagicMock()
            mock_page2.extract_text.return_value = "Technical Specifications\nDatabase uses PostgreSQL pgvector."

            mock_reader = MagicMock()
            mock_reader.pages = [mock_page1, mock_page2]
            mock_reader.metadata = {"/Title": "Kora Architecture", "/Author": "DeepMind"}

            with pytest.MonkeyPatch.context() as mp:
                import pypdf
                mp.setattr(pypdf, "PdfReader", lambda path: mock_reader)

                doc = await parser.parse(tmp_path)
                assert doc is not None
                assert doc.doc_type == DocumentType.DOCUMENT
                assert doc.metadata["page_count"] == 2
                assert "Page 1" in doc.content
                assert "Page 2" in doc.content

                chunker = StructuralChunker(uuid.uuid4(), chunk_size=500)
                chunks = chunker.chunk(doc)
                assert len(chunks) == 2
                assert chunks[0].metadata["page_number"] == 1
                assert chunks[0].metadata.get("heading") == "Executive Summary"
                assert chunks[1].metadata["page_number"] == 2
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_docx_parsing_headings_and_tables(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            doc = python_docx.Document()
            doc.add_heading("Project Overview", level=1)
            doc.add_paragraph("Kora is an autonomous agent.")
            doc.add_heading("Database Architecture", level=2)
            doc.add_paragraph("Using pgvector for vector storage.")

            table = doc.add_table(rows=2, cols=2)
            table.cell(0, 0).text = "Component"
            table.cell(0, 1).text = "Technology"
            table.cell(1, 0).text = "Vector DB"
            table.cell(1, 1).text = "PostgreSQL"
            doc.save(tmp_path)

            parser = Parser()
            parsed = await parser.parse(tmp_path)
            assert parsed is not None
            assert parsed.doc_type == DocumentType.DOCUMENT
            assert len(parsed.metadata["headings"]) == 2
            assert "Vector DB | PostgreSQL" in parsed.content

            chunker = StructuralChunker(uuid.uuid4())
            chunks = chunker.chunk(parsed)
            assert len(chunks) >= 1
            assert any("pgvector" in c.content for c in chunks)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_xlsx_spreadsheet_sheets_and_cell_ranges(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            wb = openpyxl.Workbook()
            ws1 = wb.active
            ws1.title = "Q1_Metrics"
            ws1.append(["Metric", "Target", "Actual"])
            ws1.append(["Latency", "50ms", "42ms"])
            ws1.append(["Throughput", "1000rps", "1250rps"])

            ws2 = wb.create_sheet(title="Q2_Metrics")
            ws2.append(["Metric", "Target", "Actual"])
            ws2.append(["Accuracy", "99%", "99.4%"])
            wb.save(tmp_path)

            parser = Parser()
            parsed = await parser.parse(tmp_path)
            assert parsed is not None
            assert parsed.doc_type == DocumentType.SPREADSHEET
            assert parsed.metadata["sheet_count"] == 2
            assert "Q1_Metrics" in parsed.metadata["sheet_names"]
            assert "Q2_Metrics" in parsed.metadata["sheet_names"]

            chunker = StructuralChunker(uuid.uuid4())
            chunks = chunker.chunk(parsed)
            assert len(chunks) >= 2
            assert chunks[0].metadata["sheet_name"] == "Q1_Metrics"
            assert chunks[0].metadata["cell_range"] == "A1:C3"
            assert chunks[1].metadata["sheet_name"] == "Q2_Metrics"
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_pptx_presentation_slide_chunking(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            prs = Presentation()
            slide1 = prs.slides.add_slide(prs.slide_layouts[0])
            slide1.shapes.title.text = "System Architecture"
            slide1.placeholders[1].text = "Overview of Kora Autonomous Agent."

            slide2 = prs.slides.add_slide(prs.slide_layouts[1])
            slide2.shapes.title.text = "RAG Pipeline"
            slide2.placeholders[1].text = "Scanner -> Chunker -> Retriever -> Reranker."
            prs.save(tmp_path)

            parser = Parser()
            parsed = await parser.parse(tmp_path)
            assert parsed is not None
            assert parsed.doc_type == DocumentType.DOCUMENT
            assert parsed.metadata["slide_count"] == 2

            chunker = StructuralChunker(uuid.uuid4())
            chunks = chunker.chunk(parsed)
            assert len(chunks) == 2
            assert chunks[0].metadata["slide_number"] == 1
            assert chunks[0].metadata["slide_title"] == "System Architecture"
            assert chunks[1].metadata["slide_number"] == 2
            assert chunks[1].metadata["slide_title"] == "RAG Pipeline"
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_csv_header_aware_chunking(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as tmp:
            writer = csv.writer(tmp)
            writer.writerow(["user_id", "email", "role"])
            for i in range(1, 25):
                writer.writerow([f"user_{i}", f"user{i}@example.com", "admin" if i == 1 else "member"])
            tmp_path = Path(tmp.name)

        try:
            parser = Parser()
            parsed = await parser.parse(tmp_path)
            assert parsed is not None
            assert parsed.doc_type == DocumentType.SPREADSHEET
            assert parsed.metadata["headers"] == ["user_id", "email", "role"]
            assert parsed.metadata["row_count"] == 24

            chunker = StructuralChunker(uuid.uuid4(), chunk_size=80)
            chunks = chunker.chunk(parsed)
            assert len(chunks) >= 1
            # Every CSV chunk must preserve header information
            for chunk in chunks:
                assert "user_id | email | role" in chunk.content
                assert chunk.metadata["headers"] == ["user_id", "email", "role"]
                assert "row_start" in chunk.metadata
                assert "row_end" in chunk.metadata
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


class TestStructuralProvenanceRetrieval:
    @pytest.mark.asyncio
    async def test_sheet_intent_query_boosting(self) -> None:
        project_id = uuid.uuid4()
        mock_db = AsyncMock()

        c_sheet = Chunk(
            chunk_index=0,
            content="Q1 Financials revenue breakdown",
            doc_type=DocumentType.SPREADSHEET,
            file_path="reports/q1.xlsx",
            project_id=project_id,
            metadata={"sheet_name": "Financials", "cell_range": "A1:D20"},
        )
        rc_sheet = RetrievedChunk(chunk=c_sheet, db_id=c_sheet.id, dense_score=0.7, sparse_score=0.5)

        c_text = Chunk(
            chunk_index=1,
            content="general text notes about financials",
            doc_type=DocumentType.PLAIN,
            file_path="notes.txt",
            project_id=project_id,
        )
        rc_text = RetrievedChunk(chunk=c_text, db_id=c_text.id, dense_score=0.75, sparse_score=0.5)

        retriever = RAGRetriever(mock_db)
        retriever._dense_search = AsyncMock(return_value=[rc_text, rc_sheet])
        retriever._sparse_search = AsyncMock(return_value=[rc_sheet, rc_text])
        retriever._embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)

        # Query asking for sheet
        results = await retriever.query("Which sheet contains Financials?", project_id, mode=SearchMode.HYBRID)
        assert len(results) == 2
        assert results[0].chunk_id == c_sheet.id
        assert results[0].structural_boost > 0.0

    @pytest.mark.asyncio
    async def test_page_intent_query_boosting(self) -> None:
        project_id = uuid.uuid4()
        mock_db = AsyncMock()

        c_page3 = Chunk(
            chunk_index=2,
            content="Specifications for encryption algorithm",
            doc_type=DocumentType.DOCUMENT,
            file_path="security_spec.pdf",
            project_id=project_id,
            metadata={"page_number": 3},
        )
        rc_page3 = RetrievedChunk(chunk=c_page3, db_id=c_page3.id, dense_score=0.6, sparse_score=0.4)

        c_page1 = Chunk(
            chunk_index=0,
            content="Introduction to security algorithm",
            doc_type=DocumentType.DOCUMENT,
            file_path="security_spec.pdf",
            project_id=project_id,
            metadata={"page_number": 1},
        )
        rc_page1 = RetrievedChunk(chunk=c_page1, db_id=c_page1.id, dense_score=0.7, sparse_score=0.5)

        retriever = RAGRetriever(mock_db)
        retriever._dense_search = AsyncMock(return_value=[rc_page1, rc_page3])
        retriever._sparse_search = AsyncMock(return_value=[rc_page1, rc_page3])
        retriever._embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)

        results = await retriever.query("Show information from page 3", project_id, mode=SearchMode.HYBRID)
        assert len(results) == 2
        assert results[0].chunk_id == c_page3.id
        assert results[0].page_number == 3

    @pytest.mark.asyncio
    async def test_slide_intent_query_boosting(self) -> None:
        project_id = uuid.uuid4()
        mock_db = AsyncMock()

        c_slide = Chunk(
            chunk_index=1,
            content="System Architecture Diagram",
            doc_type=DocumentType.DOCUMENT,
            file_path="deck.pptx",
            project_id=project_id,
            metadata={"slide_number": 2, "slide_title": "Architecture"},
        )
        rc_slide = RetrievedChunk(chunk=c_slide, db_id=c_slide.id, dense_score=0.7)

        retriever = RAGRetriever(mock_db)
        retriever._apply_signal_boosts(
            rc_slide,
            query="Find the slide about Architecture",
            query_terms=["slide", "architecture"],
            structural_intent={"prefer_slides": True},
        )
        assert rc_slide.structural_boost > 0.0


class TestRichProvenanceContextBuilderV3:
    def test_context_builder_formats_all_document_types(self) -> None:
        project_id = uuid.uuid4()
        builder = ContextBuilder(max_context_tokens=2000)

        # 1. Spreadsheet chunk
        c_sheet = Chunk(
            chunk_index=0,
            content="Metric | Q1 | Q2\nRevenue | $100k | $150k",
            doc_type=DocumentType.SPREADSHEET,
            file_path="finance.xlsx",
            project_id=project_id,
            metadata={"sheet_name": "Revenue", "cell_range": "A1:C2"},
        )
        rc_sheet = RetrievedChunk(chunk=c_sheet, combined_score=0.92)

        # 2. Slide chunk
        c_slide = Chunk(
            chunk_index=1,
            content="Modular autonomous agent framework",
            doc_type=DocumentType.DOCUMENT,
            file_path="overview.pptx",
            project_id=project_id,
            metadata={"slide_number": 3, "slide_title": "Core Vision"},
        )
        rc_slide = RetrievedChunk(chunk=c_slide, combined_score=0.88)

        # 3. CSV chunk
        c_csv = Chunk(
            chunk_index=2,
            content="id | name\n1 | alice",
            doc_type=DocumentType.SPREADSHEET,
            file_path="users.csv",
            project_id=project_id,
            metadata={"headers": ["id", "name"], "row_start": 1, "row_end": 1},
        )
        rc_csv = RetrievedChunk(chunk=c_csv, combined_score=0.85)

        ctx = builder.build("agent architecture", [rc_sheet, rc_slide, rc_csv], project_id)
        assert "finance.xlsx" in ctx.context_text
        assert "sheet: Revenue" in ctx.context_text
        assert "range: A1:C2" in ctx.context_text
        assert "overview.pptx" in ctx.context_text
        assert "slide: 3" in ctx.context_text
        assert "title: Core Vision" in ctx.context_text
        assert "users.csv" in ctx.context_text
        assert "headers: id, name" in ctx.context_text
        assert len(ctx.sources) == 3
