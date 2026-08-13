import os
from pathlib import Path
from typing import List, Union, Optional

class PathSecurityError(Exception):
    def __init__(self, message: str, code: str = "PATH_NOT_ALLOWED"):
        super().__init__(message)
        self.message = message
        self.code = code

class PathValidator:
    def __init__(self, authorized_roots: Optional[List[Union[str, Path]]] = None):
        self.authorized_roots: List[Path] = []
        if authorized_roots:
            for root in authorized_roots:
                if root:
                    try:
                        resolved_root = Path(root).resolve()
                        if resolved_root.exists():
                            self.authorized_roots.append(resolved_root)
                    except Exception:
                        pass

    def add_authorized_root(self, root_path: Union[str, Path]):
        if not root_path:
            return
        try:
            resolved = Path(root_path).resolve()
            if resolved not in self.authorized_roots:
                self.authorized_roots.append(resolved)
        except Exception as e:
            raise PathSecurityError(f"Invalid authorized root path: {root_path} ({e})")

    def validate_path(self, target_path: Union[str, Path], allow_non_existent: bool = False) -> Path:
        """
        Validates that target_path resolves strictly within one of the authorized_roots.
        Prevents path traversal (../), symlink escapes, and unauthorized directory access.
        """
        if not self.authorized_roots:
            raise PathSecurityError("No authorized workspace or project roots set for filesystem validator.", code="NO_AUTHORIZED_ROOTS")

        raw_path = Path(target_path)
        
        # If relative path, try resolving relative to the first authorized root
        if not raw_path.is_absolute():
            resolved = (self.authorized_roots[0] / raw_path).resolve()
        else:
            resolved = raw_path.resolve()

        # Check non-existent rules (e.g. for creating new files, parent directory must be authorized)
        if not resolved.exists():
            if not allow_non_existent:
                raise PathSecurityError(f"Target path does not exist: {target_path}", code="FILE_NOT_FOUND")
            # For non-existent files, check resolved parent
            check_target = resolved.parent
        else:
            check_target = resolved

        # Check if check_target is within at least one authorized root
        is_authorized = False
        for root in self.authorized_roots:
            try:
                # check_target == root or root in check_target.parents
                if check_target == root or root in check_target.parents:
                    is_authorized = True
                    break
            except Exception:
                continue

        if not is_authorized:
            raise PathSecurityError(
                f"Path '{target_path}' (resolved: '{resolved}') is outside authorized workspace roots.",
                code="PATH_NOT_ALLOWED"
            )

        # Additional check: ensure symlinks don't resolve outside root
        if resolved.is_symlink():
            real_target = resolved.readlink().resolve()
            symlink_authorized = False
            for root in self.authorized_roots:
                if real_target == root or root in real_target.parents:
                    symlink_authorized = True
                    break
            if not symlink_authorized:
                raise PathSecurityError(f"Symlink target '{real_target}' escapes authorized workspace root.", code="SYMLINK_ESCAPE")

        return resolved
