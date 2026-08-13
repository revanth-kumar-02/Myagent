import os
import time
import shutil
import mimetypes
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from core.filesystem.path_validator import PathValidator, PathSecurityError
from core.filesystem.permission_manager import PermissionManager, PermissionLevel, permission_manager as default_permission_manager

logger = logging.getLogger(__name__)

NOISY_DIRECTORIES = {
    ".git", "node_modules", "dist", "build", "target", ".venv", "venv",
    "__pycache__", ".dart_tool", ".cache", "coverage", ".next", ".nuxt"
}

def is_binary_content(sample_bytes: bytes) -> bool:
    """Detects binary files by looking for null bytes in sample."""
    if b"\x00" in sample_bytes:
        return True
    return False

def format_structured_response(tool_name: str, path: str, result: Dict[str, Any], duration_ms: float) -> Dict[str, Any]:
    return {
        "success": True,
        "tool": tool_name,
        "path": path,
        "result": result,
        "duration_ms": round(duration_ms, 2)
    }

def format_structured_error(tool_name: str, path: str, code: str, message: str, duration_ms: float) -> Dict[str, Any]:
    return {
        "success": False,
        "tool": tool_name,
        "path": path,
        "error": {
            "code": code,
            "message": message
        },
        "duration_ms": round(duration_ms, 2)
    }

# ─── Pydantic Schemas for Filesystem Tools ─────────────────────

class ListDirectoryInput(BaseModel):
    path: str = Field(".", description="Directory path to list relative to root or absolute")
    limit: int = Field(100, description="Max entries to return")
    offset: int = Field(0, description="Pagination offset")

class SearchFilesInput(BaseModel):
    query: str = Field(..., description="Filename, path, or text search term")
    search_type: str = Field("filename", description="Type of search: 'filename', 'content', or 'path'")
    root_path: str = Field(".", description="Root directory to start search from")
    max_results: int = Field(50, description="Max search result matches to return")

class ReadFileInput(BaseModel):
    path: str = Field(..., description="File path to read")
    start_line: Optional[int] = Field(None, description="1-indexed starting line")
    end_line: Optional[int] = Field(None, description="1-indexed ending line")

class InspectFileInput(BaseModel):
    path: str = Field(..., description="File or directory path to inspect")

class CreateFileInput(BaseModel):
    path: str = Field(..., description="File path to create")
    content: str = Field("", description="Initial text content")

class EditFileInput(BaseModel):
    path: str = Field(..., description="File path to edit")
    target_content: str = Field(..., description="Exact target content snippet to replace")
    replacement_content: str = Field(..., description="Replacement text content")

class MoveFileInput(BaseModel):
    source_path: str = Field(..., description="Source file or directory path")
    destination_path: str = Field(..., description="Destination file or directory path")

class DeleteFileInput(BaseModel):
    path: str = Field(..., description="File or directory path to delete")


# ─── Filesystem Tool Manager ───────────────────────────────────

class FilesystemToolSet:
    def __init__(self, validator: PathValidator, perm_manager: PermissionManager = None):
        self.validator = validator
        self.perm_manager = perm_manager or default_permission_manager

    # 1. list_directory
    async def list_directory(self, input_data: ListDirectoryInput) -> Dict[str, Any]:
        start_time = time.time()
        try:
            target_path = self.validator.validate_path(input_data.path)
            if not target_path.is_dir():
                return format_structured_error("list_directory", input_data.path, "NOT_A_DIRECTORY", f"Path '{input_data.path}' is not a directory.", (time.time() - start_time) * 1000)

            all_entries = []
            for child in target_path.iterdir():
                if child.name in NOISY_DIRECTORIES:
                    continue
                try:
                    stat = child.stat()
                    all_entries.append({
                        "name": child.name,
                        "type": "directory" if child.is_dir() else "file",
                        "size": stat.st_size if child.is_file() else 0,
                        "modified_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(stat.st_mtime))
                    })
                except Exception:
                    continue

            # Sort directories first, then files alphabetically
            all_entries.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
            paginated = all_entries[input_data.offset : input_data.offset + input_data.limit]

            res = {
                "path": str(target_path),
                "entries": paginated,
                "total_count": len(all_entries),
                "limit": input_data.limit,
                "offset": input_data.offset
            }
            return format_structured_response("list_directory", str(target_path), res, (time.time() - start_time) * 1000)

        except PathSecurityError as pse:
            return format_structured_error("list_directory", input_data.path, pse.code, pse.message, (time.time() - start_time) * 1000)
        except Exception as e:
            return format_structured_error("list_directory", input_data.path, "UNKNOWN_ERROR", str(e), (time.time() - start_time) * 1000)

    # 2. search_files
    async def search_files(self, input_data: SearchFilesInput) -> Dict[str, Any]:
        start_time = time.time()
        try:
            root = self.validator.validate_path(input_data.root_path)
            matches = []

            for dirpath, dirnames, filenames in os.walk(root):
                # Filter noisy directories in-place
                dirnames[:] = [d for d in dirnames if d not in NOISY_DIRECTORIES]

                for fname in filenames:
                    if len(matches) >= input_data.max_results:
                        break

                    file_path = Path(dirpath) / fname
                    rel_path = str(file_path.relative_to(root))

                    if input_data.search_type == "filename":
                        if input_data.query.lower() in fname.lower():
                            matches.append({"path": rel_path, "type": "filename_match"})

                    elif input_data.search_type == "path":
                        if input_data.query.lower() in rel_path.lower():
                            matches.append({"path": rel_path, "type": "path_match"})

                    elif input_data.search_type == "content":
                        # Content search (skip binary or > 1MB files)
                        try:
                            if file_path.stat().st_size > 1_000_000:
                                continue
                            with open(file_path, "rb") as f:
                                sample = f.read(1024)
                                if is_binary_content(sample):
                                    continue

                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                for line_idx, line in enumerate(f, start=1):
                                    if input_data.query.lower() in line.lower():
                                        matches.append({
                                            "path": rel_path,
                                            "line": line_idx,
                                            "snippet": line.strip()[:200]
                                        })
                                        if len(matches) >= input_data.max_results:
                                            break
                        except Exception:
                            continue

            res = {
                "root_path": str(root),
                "query": input_data.query,
                "search_type": input_data.search_type,
                "matches": matches,
                "count": len(matches)
            }
            return format_structured_response("search_files", str(root), res, (time.time() - start_time) * 1000)

        except PathSecurityError as pse:
            return format_structured_error("search_files", input_data.root_path, pse.code, pse.message, (time.time() - start_time) * 1000)
        except Exception as e:
            return format_structured_error("search_files", input_data.root_path, "UNKNOWN_ERROR", str(e), (time.time() - start_time) * 1000)

    # 3. read_file
    async def read_file(self, input_data: ReadFileInput) -> Dict[str, Any]:
        start_time = time.time()
        try:
            target = self.validator.validate_path(input_data.path)
            if not target.is_file():
                return format_structured_error("read_file", input_data.path, "NOT_A_FILE", f"Path '{input_data.path}' is not a regular file.", (time.time() - start_time) * 1000)

            # Check binary
            with open(target, "rb") as f:
                sample = f.read(2048)
                if is_binary_content(sample):
                    return format_structured_error("read_file", input_data.path, "BINARY_FILE", "Binary file reading is not supported. Use inspect_file for metadata.", (time.time() - start_time) * 1000)

            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)

            # Default / ranged limits
            start = input_data.start_line or 1
            end = input_data.end_line or total_lines

            start = max(1, start)
            end = min(total_lines, end)

            if end - start > 500 and not input_data.end_line:
                # Truncate to 500 max lines if end_line wasn't specified
                end = start + 499

            selected_lines = lines[start - 1 : end]
            content = "".join(selected_lines)

            res = {
                "path": str(target),
                "content": content,
                "line_range": [start, end],
                "total_lines": total_lines,
                "encoding": "utf-8"
            }
            return format_structured_response("read_file", str(target), res, (time.time() - start_time) * 1000)

        except PathSecurityError as pse:
            return format_structured_error("read_file", input_data.path, pse.code, pse.message, (time.time() - start_time) * 1000)
        except Exception as e:
            return format_structured_error("read_file", input_data.path, "UNKNOWN_ERROR", str(e), (time.time() - start_time) * 1000)

    # 4. inspect_file
    async def inspect_file(self, input_data: InspectFileInput) -> Dict[str, Any]:
        start_time = time.time()
        try:
            target = self.validator.validate_path(input_data.path)
            stat = target.stat()
            mime_type, _ = mimetypes.guess_type(target.name)

            res = {
                "name": target.name,
                "path": str(target),
                "extension": target.suffix,
                "mime_type": mime_type or "application/octet-stream",
                "size": stat.st_size if target.is_file() else 0,
                "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(stat.st_ctime)),
                "modified_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(stat.st_mtime)),
                "is_directory": target.is_dir(),
                "is_file": target.is_file(),
                "git_ignored": target.name in NOISY_DIRECTORIES
            }
            return format_structured_response("inspect_file", str(target), res, (time.time() - start_time) * 1000)

        except PathSecurityError as pse:
            return format_structured_error("inspect_file", input_data.path, pse.code, pse.message, (time.time() - start_time) * 1000)
        except Exception as e:
            return format_structured_error("inspect_file", input_data.path, "UNKNOWN_ERROR", str(e), (time.time() - start_time) * 1000)

    # 5. create_file
    async def create_file(self, input_data: CreateFileInput) -> Dict[str, Any]:
        start_time = time.time()
        try:
            target = self.validator.validate_path(input_data.path, allow_non_existent=True)

            # Permission check
            has_perm = await self.perm_manager.check_permission(
                tool_name="create_file", path=str(target), operation="create", permission_level=PermissionLevel.WRITE
            )
            if not has_perm:
                return format_structured_error("create_file", input_data.path, "PERMISSION_DENIED", "WRITE permission denied for file creation.", (time.time() - start_time) * 1000)

            # Ensure parent directories exist
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(input_data.content)

            # Verification
            if not target.exists() or not target.is_file():
                return format_structured_error("create_file", input_data.path, "VERIFICATION_FAILED", "Post-write verification failed: File was not created.", (time.time() - start_time) * 1000)

            res = {
                "path": str(target),
                "size": target.stat().st_size,
                "verified": True
            }
            return format_structured_response("create_file", str(target), res, (time.time() - start_time) * 1000)

        except PathSecurityError as pse:
            return format_structured_error("create_file", input_data.path, pse.code, pse.message, (time.time() - start_time) * 1000)
        except Exception as e:
            return format_structured_error("create_file", input_data.path, "UNKNOWN_ERROR", str(e), (time.time() - start_time) * 1000)

    # 6. edit_file
    async def edit_file(self, input_data: EditFileInput) -> Dict[str, Any]:
        start_time = time.time()
        try:
            target = self.validator.validate_path(input_data.path)
            if not target.is_file():
                return format_structured_error("edit_file", input_data.path, "NOT_A_FILE", f"Target '{input_data.path}' is not a regular file.", (time.time() - start_time) * 1000)

            # Permission check
            has_perm = await self.perm_manager.check_permission(
                tool_name="edit_file", path=str(target), operation="edit", permission_level=PermissionLevel.WRITE
            )
            if not has_perm:
                return format_structured_error("edit_file", input_data.path, "PERMISSION_DENIED", "WRITE permission denied for file edit.", (time.time() - start_time) * 1000)

            with open(target, "r", encoding="utf-8") as f:
                original_content = f.read()

            if input_data.target_content not in original_content:
                return format_structured_error("edit_file", input_data.path, "TARGET_NOT_FOUND", "Target content snippet not found in target file.", (time.time() - start_time) * 1000)

            new_content = original_content.replace(input_data.target_content, input_data.replacement_content, 1)

            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)

            # Post-write Content Verification
            with open(target, "r", encoding="utf-8") as f:
                verified_content = f.read()

            if verified_content != new_content:
                return format_structured_error("edit_file", input_data.path, "VERIFICATION_FAILED", "Post-edit verification failed: File content does not match expected result.", (time.time() - start_time) * 1000)

            res = {
                "path": str(target),
                "bytes_written": len(input_data.replacement_content),
                "verified": True
            }
            return format_structured_response("edit_file", str(target), res, (time.time() - start_time) * 1000)

        except PathSecurityError as pse:
            return format_structured_error("edit_file", input_data.path, pse.code, pse.message, (time.time() - start_time) * 1000)
        except Exception as e:
            return format_structured_error("edit_file", input_data.path, "UNKNOWN_ERROR", str(e), (time.time() - start_time) * 1000)

    # 7. move_file
    async def move_file(self, input_data: MoveFileInput) -> Dict[str, Any]:
        start_time = time.time()
        try:
            src = self.validator.validate_path(input_data.source_path)
            dest = self.validator.validate_path(input_data.destination_path, allow_non_existent=True)

            has_perm = await self.perm_manager.check_permission(
                tool_name="move_file", path=str(src), operation="move", permission_level=PermissionLevel.WRITE
            )
            if not has_perm:
                return format_structured_error("move_file", input_data.source_path, "PERMISSION_DENIED", "WRITE permission denied for moving file.", (time.time() - start_time) * 1000)

            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))

            # Post-move verification
            if not dest.exists() or src.exists():
                return format_structured_error("move_file", input_data.source_path, "VERIFICATION_FAILED", "Post-move verification failed: Destination does not exist or source still exists.", (time.time() - start_time) * 1000)

            res = {
                "source_path": str(src),
                "destination_path": str(dest),
                "verified": True
            }
            return format_structured_response("move_file", str(dest), res, (time.time() - start_time) * 1000)

        except PathSecurityError as pse:
            return format_structured_error("move_file", input_data.source_path, pse.code, pse.message, (time.time() - start_time) * 1000)
        except Exception as e:
            return format_structured_error("move_file", input_data.source_path, "UNKNOWN_ERROR", str(e), (time.time() - start_time) * 1000)

    # 8. delete_file
    async def delete_file(self, input_data: DeleteFileInput) -> Dict[str, Any]:
        start_time = time.time()
        try:
            target = self.validator.validate_path(input_data.path)

            # Permission check: DELETE always requires explicit approval
            has_perm = await self.perm_manager.check_permission(
                tool_name="delete_file", path=str(target), operation="delete", permission_level=PermissionLevel.DELETE
            )
            if not has_perm:
                return format_structured_error("delete_file", input_data.path, "PERMISSION_DENIED", "DELETE permission denied by user or policy.", (time.time() - start_time) * 1000)

            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

            # Post-delete verification
            if target.exists():
                return format_structured_error("delete_file", input_data.path, "VERIFICATION_FAILED", "Post-delete verification failed: Target still exists.", (time.time() - start_time) * 1000)

            res = {
                "path": str(target),
                "deleted": True,
                "verified": True
            }
            return format_structured_response("delete_file", str(target), res, (time.time() - start_time) * 1000)

        except PathSecurityError as pse:
            return format_structured_error("delete_file", input_data.path, pse.code, pse.message, (time.time() - start_time) * 1000)
        except Exception as e:
            return format_structured_error("delete_file", input_data.path, "UNKNOWN_ERROR", str(e), (time.time() - start_time) * 1000)
