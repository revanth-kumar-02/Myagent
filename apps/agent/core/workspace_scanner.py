import os
import json
import glob
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple

IGNORED_DIRS = {
    ".git", "node_modules", "dist", "build", "target", ".venv", "venv",
    "__pycache__", ".cache", ".dart_tool", ".idea", ".vscode", "coverage",
    ".next", ".nuxt"
}

MANIFEST_MARKERS = {
    "package.json": "JavaScript/TypeScript",
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "Pipfile": "Python",
    "setup.py": "Python",
    "pubspec.yaml": "Dart/Flutter",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "pom.xml": "Java",
    "build.gradle": "Java/Kotlin",
    "build.gradle.kts": "Kotlin",
    "composer.json": "PHP",
    "CMakeLists.txt": "C/C++",
    "Makefile": "C/C++",
}

SOURCE_EXTENSIONS = {
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".py": "Python",
    ".java": "Java",
    ".kt": "Kotlin",
    ".dart": "Dart",
    ".rs": "Rust",
    ".go": "Go",
    ".cpp": "C++",
    ".hpp": "C++",
    ".c": "C",
    ".h": "C",
    ".cs": "C#",
    ".php": "PHP",
}

class ProjectAnalyzer:
    @staticmethod
    def analyze_project(folder_path: str) -> Optional[Dict[str, Any]]:
        folder_name = os.path.basename(folder_path)
        if not folder_name or folder_name.startswith(".") or folder_name in IGNORED_DIRS:
            return None

        # Check for Git inside this specific project directory only
        git_dir = os.path.join(folder_path, ".git")
        has_git = os.path.exists(git_dir)

        # Inspect immediate project directory & limited top subdirectories (like src, apps, packages, lib)
        manifests_found = set()
        configs_found = set()
        source_exts_found = set()
        languages = set()
        frameworks = set()

        # Collect top-level files & inspect up to depth 2 for monorepo packages/config
        try:
            root_entries = os.listdir(folder_path)
        except (PermissionError, FileNotFoundError):
            return None

        # Check manifest files in root
        for item in root_entries:
            if item in MANIFEST_MARKERS:
                manifests_found.add(item)
            elif item.endswith(".csproj") or item.endswith(".sln"):
                manifests_found.add(item)
                languages.add("C#")
                frameworks.add(".NET")

        # Scan for configs & manifests up to 2 levels deep (skipping IGNORED_DIRS)
        for root, dirs, files in os.walk(folder_path, topdown=True):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in IGNORED_DIRS]

            rel = os.path.relpath(root, folder_path)
            depth = 0 if rel == "." else len(rel.split(os.sep))
            if depth > 2:
                continue

            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in SOURCE_EXTENSIONS:
                    source_exts_found.add(ext)

                if f in ("tsconfig.json", "vite.config.ts", "vite.config.js", "svelte.config.js", 
                        "next.config.js", "next.config.mjs", "astro.config.mjs", "angular.json"):
                    configs_found.add(f)

                # Inspect package.json
                if f == "package.json":
                    manifests_found.add("package.json")
                    pkg_path = os.path.join(root, f)
                    try:
                        with open(pkg_path, "r", encoding="utf-8") as pf:
                            pkg_data = json.load(pf)
                            deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}

                            if "typescript" in deps or os.path.exists(os.path.join(root, "tsconfig.json")):
                                languages.add("TypeScript")
                            else:
                                languages.add("JavaScript")

                            if "@tauri-apps/api" in deps or "@tauri-apps/cli" in deps:
                                frameworks.add("Tauri")
                                languages.add("Rust")
                            if "svelte" in deps or "@sveltejs/kit" in deps:
                                frameworks.add("Svelte")
                            if "react" in deps or "react-dom" in deps:
                                frameworks.add("React")
                            if "vue" in deps:
                                frameworks.add("Vue")
                            if "next" in deps:
                                frameworks.add("Next.js")
                            if "nuxt" in deps:
                                frameworks.add("Nuxt")
                            if "vite" in deps:
                                frameworks.add("Vite")
                            if "astro" in deps:
                                frameworks.add("Astro")
                            if "express" in deps:
                                frameworks.add("Express")
                            if "electron" in deps:
                                frameworks.add("Electron")
                            if "@angular/core" in deps:
                                frameworks.add("Angular")
                    except Exception:
                        pass

                # Inspect pyproject.toml / requirements.txt / Pipfile
                if f in ("pyproject.toml", "requirements.txt", "Pipfile", "setup.py"):
                    manifests_found.add(f)
                    languages.add("Python")
                    py_path = os.path.join(root, f)
                    try:
                        with open(py_path, "r", encoding="utf-8", errors="ignore") as pyf:
                            content = pyf.read().lower()
                            if "fastapi" in content:
                                frameworks.add("FastAPI")
                            if "django" in content:
                                frameworks.add("Django")
                            if "flask" in content:
                                frameworks.add("Flask")
                            if "sqlalchemy" in content:
                                frameworks.add("SQLAlchemy")
                            if "torch" in content or "pytorch" in content:
                                frameworks.add("PyTorch")
                            if "tensorflow" in content:
                                frameworks.add("TensorFlow")
                    except Exception:
                        pass

                # Inspect pubspec.yaml
                if f == "pubspec.yaml":
                    manifests_found.add("pubspec.yaml")
                    languages.add("Dart")
                    pub_path = os.path.join(root, f)
                    try:
                        with open(pub_path, "r", encoding="utf-8", errors="ignore") as pubf:
                            content = pubf.read().lower()
                            if "flutter:" in content or "flutter" in content:
                                frameworks.add("Flutter")
                    except Exception:
                        pass

                # Inspect Cargo.toml
                if f == "Cargo.toml":
                    manifests_found.add("Cargo.toml")
                    languages.add("Rust")

                # Inspect Java / Kotlin build files
                if f in ("pom.xml", "build.gradle", "build.gradle.kts"):
                    manifests_found.add(f)
                    if f.endswith(".kts") or any(e == ".kt" for e in source_exts_found):
                        languages.add("Kotlin")
                    else:
                        languages.add("Java")
                    build_path = os.path.join(root, f)
                    try:
                        with open(build_path, "r", encoding="utf-8", errors="ignore") as bf:
                            content = bf.read().lower()
                            if "spring" in content:
                                frameworks.add("Spring Boot")
                            if "android" in content or "com.android" in content:
                                frameworks.add("Android")
                    except Exception:
                        pass

                # Inspect go.mod
                if f == "go.mod":
                    manifests_found.add("go.mod")
                    languages.add("Go")

                # Inspect composer.json
                if f == "composer.json":
                    manifests_found.add("composer.json")
                    languages.add("PHP")

        # Determine detection confidence & validity
        confidence = "low"
        if manifests_found:
            confidence = "high"
        elif has_git or configs_found:
            confidence = "medium"
        elif source_exts_found:
            confidence = "low"
        else:
            # Not a valid project directory if no manifests, no git, no configs, no source files!
            return None

        # Fallback to source extension languages if no language detected yet
        if not languages:
            for ext in source_exts_found:
                if ext in SOURCE_EXTENSIONS:
                    languages.add(SOURCE_EXTENSIONS[ext])

        # Get last modified timestamp
        latest_mtime = 0.0
        try:
            latest_mtime = os.path.getmtime(folder_path)
        except Exception:
            pass

        last_modified = datetime.fromtimestamp(latest_mtime) if latest_mtime > 0 else datetime.utcnow()

        return {
            "title": folder_name,
            "name": folder_name,
            "path": folder_path,
            "description": f"Local project repository at {folder_path}",
            "languages": sorted(list(languages)),
            "frameworks": sorted(list(frameworks)),
            "git_repository": has_git,
            "detection_confidence": confidence,
            "last_modified": last_modified,
            "last_scanned": datetime.utcnow(),
            "metadata_info": {
                "manifests_found": sorted(list(manifests_found)),
                "has_git": has_git,
                "confidence": confidence
            }
        }

class WorkspaceScanner:
    @staticmethod
    def scan_directory(root_path: str) -> List[Dict[str, Any]]:
        root_path = os.path.abspath(os.path.expanduser(root_path))
        if not os.path.exists(root_path):
            raise ValueError(f"Workspace directory '{root_path}' does not exist.")
        if not os.path.isdir(root_path):
            raise ValueError(f"Path '{root_path}' is not a directory.")

        discovered_projects = []

        # RULE 1: ONLY scan immediate child directories inside root_path.
        # NEVER include the root_path workspace directory itself as a project!
        try:
            entries = os.listdir(root_path)
        except PermissionError:
            raise PermissionError(f"Permission denied to access workspace directory '{root_path}'.")

        real_root_path = os.path.realpath(root_path)

        for entry in sorted(entries):
            if entry.startswith(".") or entry in IGNORED_DIRS:
                continue

            full_path = os.path.join(root_path, entry)

            # RULE 2: Ensure path is a directory and strictly a child of root_path
            if os.path.isdir(full_path):
                real_full_path = os.path.realpath(full_path)
                if not real_full_path.startswith(real_root_path) or real_full_path == real_root_path:
                    continue

                # RULE 3 & 4: Analyze child directory using ProjectAnalyzer
                proj = ProjectAnalyzer.analyze_project(full_path)
                if proj:
                    discovered_projects.append(proj)

        return discovered_projects
