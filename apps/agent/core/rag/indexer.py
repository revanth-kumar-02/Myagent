import os
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Set
from sqlalchemy.future import select
from sqlalchemy import delete as sql_delete, func

from db.session import AsyncSessionLocal
from db.models import Project, ProjectFile, ProjectChunk
from core.rag.filter import is_ignored_directory, should_index_file, get_file_language
from core.rag.chunker import structural_chunker
from core.embeddings import default_embedding_provider, BaseEmbeddingProvider

logger = logging.getLogger(__name__)

def hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

class ProjectRagIndexer:
    """
    Incremental Project RAG Indexer.
    Uses SHA-256 content hashes to skip unchanged files, update only affected chunks,
    and remove deleted files from PostgreSQL/pgvector storage.
    """

    def __init__(self, embedding_provider: Optional[BaseEmbeddingProvider] = None):
        self.embedding_provider = embedding_provider or default_embedding_provider

    async def index_project(
        self,
        project_id: str,
        workspace_path: Optional[str] = None,
        force_full: bool = False
    ) -> Dict[str, Any]:
        """
        Incrementally index project source code, documentation, and structural chunks.
        """
        async with AsyncSessionLocal() as db:
            proj_res = await db.execute(select(Project).where(Project.id == project_id))
            proj = proj_res.scalar_one_or_none()
            if not proj:
                return {"status": "error", "message": f"Project '{project_id}' not found"}

            effective_path = workspace_path or proj.path
            if not effective_path or not os.path.exists(effective_path):
                return {"status": "error", "message": f"Invalid path '{effective_path}'"}

            root_path = Path(effective_path).resolve()

            # 1. Fetch existing indexed files from DB
            existing_files_res = await db.execute(
                select(ProjectFile).where(ProjectFile.project_id == project_id)
            )
            existing_files_list = existing_files_res.scalars().all()
            existing_files_map: Dict[str, ProjectFile] = {
                f.relative_path: f for f in existing_files_list
            }

            # 2. Discover files in workspace path
            discovered_files: List[Path] = []
            for root, dirs, files in os.walk(str(root_path)):
                dirs[:] = [d for d in dirs if not is_ignored_directory(d)]
                for fname in files:
                    full_p = Path(root) / fname
                    if should_index_file(full_p):
                        discovered_files.append(full_p)

            current_disk_paths: Set[str] = set()
            files_unchanged = 0
            files_updated = 0
            files_created = 0
            chunks_created = 0
            chunks_updated = 0
            chunks_deleted = 0
            chunks_unchanged = 0

            # 3. Process discovered files
            for file_path in discovered_files:
                try:
                    rel_path = str(file_path.relative_to(root_path))
                except ValueError:
                    continue

                current_disk_paths.add(rel_path)

                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception as e:
                    logger.debug(f"Could not read {file_path}: {e}")
                    continue

                if not should_index_file(file_path, content):
                    continue

                file_hash = hash_content(content)
                existing_file = existing_files_map.get(rel_path)

                # Incremental skip: check if file is completely unchanged
                if (
                    not force_full
                    and existing_file
                    and existing_file.content_hash == file_hash
                ):
                    files_unchanged += 1
                    continue

                # File is new or changed - parse and structural chunk
                language = get_file_language(file_path) or "text"
                raw_chunks = structural_chunker.chunk(content, language)

                # Fetch existing chunks for this specific file
                existing_chunks_res = await db.execute(
                    select(ProjectChunk).where(
                        ProjectChunk.project_id == project_id,
                        ProjectChunk.file_path == rel_path
                    )
                )
                existing_chunks = existing_chunks_res.scalars().all()
                existing_chunk_map = {c.chunk_index: c for c in existing_chunks}

                new_chunk_count = len(raw_chunks)
                for raw in raw_chunks:
                    ex_chunk = existing_chunk_map.get(raw.chunk_index)
                    if (
                        not force_full
                        and ex_chunk
                        and ex_chunk.content_hash == raw.content_hash
                        and ex_chunk.embedding is not None
                    ):
                        # Chunk unchanged, keep existing embedding
                        chunks_unchanged += 1
                        ex_chunk.symbol = raw.symbol
                        ex_chunk.updated_at = datetime.utcnow()
                    else:
                        # Chunk is new or modified: compute embedding
                        embedding = await self.embedding_provider.get_embedding(raw.content)
                        if ex_chunk:
                            ex_chunk.content = raw.content
                            ex_chunk.content_hash = raw.content_hash
                            ex_chunk.file_hash = file_hash
                            ex_chunk.symbol = raw.symbol
                            ex_chunk.language = raw.language
                            ex_chunk.embedding = embedding
                            ex_chunk.updated_at = datetime.utcnow()
                            chunks_updated += 1
                        else:
                            new_chunk_model = ProjectChunk(
                                project_id=project_id,
                                file_path=rel_path,
                                language=raw.language,
                                chunk_index=raw.chunk_index,
                                symbol=raw.symbol,
                                content=raw.content,
                                content_hash=raw.content_hash,
                                file_hash=file_hash,
                                embedding=embedding,
                                created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow()
                            )
                            db.add(new_chunk_model)
                            chunks_created += 1

                # Prune old chunks if file now has fewer chunks than before
                for idx, ex_chunk in existing_chunk_map.items():
                    if idx >= new_chunk_count:
                        await db.delete(ex_chunk)
                        chunks_deleted += 1

                # Update or insert ProjectFile record
                stat = file_path.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime)
                if existing_file:
                    existing_file.content_hash = file_hash
                    existing_file.size_bytes = stat.st_size
                    existing_file.last_modified = mtime
                    files_updated += 1
                else:
                    new_file_record = ProjectFile(
                        project_id=project_id,
                        relative_path=rel_path,
                        file_type="source",
                        size_bytes=stat.st_size,
                        content_hash=file_hash,
                        last_modified=mtime,
                        created_at=datetime.utcnow()
                    )
                    db.add(new_file_record)
                    files_created += 1

            # 4. Handle Deleted Files: remove files & chunks no longer on disk
            files_deleted = 0
            for rel_path, ex_file in existing_files_map.items():
                if rel_path not in current_disk_paths:
                    # Delete chunks for this deleted file
                    await db.execute(
                        sql_delete(ProjectChunk).where(
                            ProjectChunk.project_id == project_id,
                            ProjectChunk.file_path == rel_path
                        )
                    )
                    # Delete file record
                    await db.delete(ex_file)
                    files_deleted += 1

            # Update Project timestamps
            proj.last_scanned = datetime.utcnow()
            proj.last_modified = datetime.utcnow()

            await db.commit()

            # 5. Total counts query
            total_chunks_res = await db.execute(
                select(func.count()).select_from(ProjectChunk).where(ProjectChunk.project_id == project_id)
            )
            total_chunks = total_chunks_res.scalar() or 0

            total_files_res = await db.execute(
                select(func.count()).select_from(ProjectFile).where(ProjectFile.project_id == project_id)
            )
            total_files = total_files_res.scalar() or 0

            return {
                "status": "success",
                "project_id": project_id,
                "workspace_path": str(root_path),
                "files_scanned": len(discovered_files),
                "files_unchanged": files_unchanged,
                "files_created": files_created,
                "files_updated": files_updated,
                "files_deleted": files_deleted,
                "total_indexed_files": total_files,
                "chunks_created": chunks_created,
                "chunks_updated": chunks_updated,
                "chunks_deleted": chunks_deleted,
                "chunks_unchanged": chunks_unchanged,
                "total_chunks": total_chunks,
                "last_indexed": proj.last_scanned.isoformat()
            }

project_rag_indexer = ProjectRagIndexer()
