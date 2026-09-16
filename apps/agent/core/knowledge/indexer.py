import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlalchemy.future import select
from sqlalchemy import delete as sql_delete

from db.session import AsyncSessionLocal
from db.models import Project, ProjectFile, ProjectTechnology, ProjectDependency, GitMetadata, AgentMemory
from core.knowledge.technology_detector import detect_project_technologies, IGNORE_DIRS
from core.knowledge.git_indexer import inspect_git_repository

logger = logging.getLogger(__name__)

def determine_file_category(file_path: Path) -> str:
    name_lower = file_path.name.lower()
    ext = file_path.suffix.lower()
    
    if name_lower in ("package.json", "requirements.txt", "pyproject.toml", "cargo.toml", "pom.xml", "build.gradle", "tsconfig.json", "dockerfile"):
        return "config"
    if name_lower in ("readme.md", "license", "changelog.md", "architecture.md"):
        return "documentation"
    if ext in (".py", ".ts", ".js", ".jsx", ".tsx", ".rs", ".java", ".go", ".c", ".cpp", ".h", ".kt", ".dart", ".svelte", ".vue", ".html", ".css"):
        return "source"
    return "other"

class ProjectKnowledgeIndexer:
    """Orchestrates scanning, technology detection, Git metadata extraction, and PostgreSQL Knowledge Graph synchronization."""

    async def scan_and_index_project(self, project_id: str, project_path: Optional[str] = None) -> Dict[str, Any]:
        """Performs full workspace knowledge index & synchronization into PostgreSQL."""
        async with AsyncSessionLocal() as db:
            proj_res = await db.execute(select(Project).where(Project.id == project_id))
            proj = proj_res.scalar_one_or_none()
            if not proj:
                logger.warning(f"Project '{project_id}' not found for knowledge indexing.")
                return {"status": "error", "message": f"Project '{project_id}' not found"}

            effective_path = project_path or proj.path
            if not effective_path or not os.path.exists(effective_path):
                return {"status": "error", "message": f"Invalid path '{effective_path}'"}

            root_path = Path(effective_path)

            # 1. Detect Technologies & Dependencies
            techs, deps = detect_project_technologies(effective_path)

            # 2. Inspect Git Metadata
            git_info = inspect_git_repository(effective_path)

            # 3. Discover Files (ignoring node_modules, .venv, .git, etc.)
            file_records = []
            max_file_count = 500
            count = 0
            for root, dirs, files in os.walk(effective_path):
                # Filter ignore dirs
                dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
                for f in files:
                    if count >= max_file_count:
                        break
                    if f.startswith(".") or f.endswith((".pyc", ".log", ".tmp", ".bin", ".png", ".jpg", ".svg", ".ico", ".woff", ".woff2")):
                        continue
                    full_p = Path(root) / f
                    rel_p = str(full_p.relative_to(root_path))
                    cat = determine_file_category(full_p)
                    size = full_p.stat().st_size if full_p.exists() else 0
                    mtime = datetime.fromtimestamp(full_p.stat().st_mtime) if full_p.exists() else datetime.utcnow()
                    file_records.append({
                        "relative_path": rel_p,
                        "file_type": cat,
                        "size_bytes": size,
                        "last_modified": mtime
                    })
                    count += 1

            # 4. Sync Database Relational Models
            # Delete old relational file/tech/dep records for clean update
            await db.execute(sql_delete(ProjectFile).where(ProjectFile.project_id == project_id))
            await db.execute(sql_delete(ProjectTechnology).where(ProjectTechnology.project_id == project_id))
            await db.execute(sql_delete(ProjectDependency).where(ProjectDependency.project_id == project_id))
            await db.execute(sql_delete(GitMetadata).where(GitMetadata.project_id == project_id))
            await db.flush()

            # Insert Files
            for fr in file_records:
                db.add(ProjectFile(
                    project_id=project_id,
                    relative_path=fr["relative_path"],
                    file_type=fr["file_type"],
                    size_bytes=fr["size_bytes"],
                    last_modified=fr["last_modified"]
                ))

            # Insert Technologies
            lang_names = []
            fw_names = []
            for t in techs:
                db.add(ProjectTechnology(
                    project_id=project_id,
                    name=t.name,
                    category=t.category,
                    version=t.version,
                    evidence_source=t.evidence_source
                ))
                if t.category == "language":
                    lang_names.append(t.name)
                elif t.category in ("framework", "build_tool", "tool"):
                    fw_names.append(t.name)

            # Insert Dependencies
            for d in deps:
                db.add(ProjectDependency(
                    project_id=project_id,
                    name=d.name,
                    version_spec=d.version_spec,
                    ecosystem=d.ecosystem,
                    is_dev=d.is_dev
                ))

            # Insert Git Metadata
            if git_info.is_repo:
                db.add(GitMetadata(
                    project_id=project_id,
                    branch=git_info.branch,
                    latest_commit_hash=git_info.latest_commit_hash,
                    latest_commit_message=git_info.latest_commit_message,
                    latest_commit_author=git_info.latest_commit_author,
                    latest_commit_date=git_info.latest_commit_date,
                    modified_files_count=git_info.modified_files_count,
                    status_clean=git_info.status_clean
                ))
                proj.git_repository = True

            # Update Project Record Meta
            proj.languages = list(set(lang_names)) if lang_names else (proj.languages or [])
            proj.frameworks = list(set(fw_names)) if fw_names else (proj.frameworks or [])
            proj.last_scanned = datetime.utcnow()
            proj.last_modified = datetime.utcnow()

            await db.commit()

            # 5. Create / Update Durable Project Knowledge Memory
            summary_facts = []
            if proj.languages:
                summary_facts.append(f"Project '{proj.title}' uses languages: {', '.join(proj.languages)}.")
            if proj.frameworks:
                summary_facts.append(f"Project '{proj.title}' framework stack includes: {', '.join(proj.frameworks)}.")
            if git_info.is_repo:
                summary_facts.append(f"Project '{proj.title}' Git repository is on branch '{git_info.branch}'.")

            from core.memory import memory_manager
            for fact in summary_facts:
                try:
                    await memory_manager.remember(
                        memory_type="PROJECT_KNOWLEDGE",
                        content=fact,
                        project_id=project_id,
                        source="PROJECT_FILE",
                        source_reliability="PROJECT_FILE",
                        importance=7,
                        confidence=1.0,
                        verification_status="ACTIVE"
                    )
                except Exception as e:
                    logger.debug(f"Knowledge memory update note: {e}")

            return {
                "status": "success",
                "project_id": project_id,
                "files_indexed": len(file_records),
                "technologies_detected": len(techs),
                "dependencies_detected": len(deps),
                "git_branch": git_info.branch if git_info.is_repo else None
            }

knowledge_indexer = ProjectKnowledgeIndexer()
