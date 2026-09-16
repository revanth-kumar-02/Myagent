import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple

IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "build", "dist",
    ".pytest_cache", ".next", ".svelte-kit", "target", "bin", "obj", ".idea", ".vscode"
}

class DetectedTech:
    def __init__(self, name: str, category: str, evidence_source: str, version: str = None):
        self.name = name
        self.category = category  # language, framework, database, tool, build_tool, package_manager
        self.evidence_source = evidence_source
        self.version = version

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "evidence_source": self.evidence_source,
            "version": self.version
        }

class DetectedDep:
    def __init__(self, name: str, ecosystem: str, version_spec: str = None, is_dev: bool = False):
        self.name = name
        self.ecosystem = ecosystem  # npm, pip, cargo, maven, gradle, pub
        self.version_spec = version_spec
        self.is_dev = is_dev

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "ecosystem": self.ecosystem,
            "version_spec": self.version_spec,
            "is_dev": self.is_dev
        }

def detect_project_technologies(project_path: str) -> Tuple[List[DetectedTech], List[DetectedDep]]:
    """
    Scans project_path for actual technology evidence files (package.json, requirements.txt, Cargo.toml, etc.).
    Does NOT infer technology merely from folder names.
    Returns (detected_technologies, detected_dependencies).
    """
    technologies: List[DetectedTech] = []
    dependencies: List[DetectedDep] = []
    
    path = Path(project_path)
    if not path.exists() or not path.is_dir():
        return technologies, dependencies

    # 1. NPM / Node Ecosystem (package.json)
    pkg_json_path = path / "package.json"
    if pkg_json_path.exists() and pkg_json_path.is_file():
        try:
            with open(pkg_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            technologies.append(DetectedTech("Node.js", "language", "package.json"))
            technologies.append(DetectedTech("npm", "package_manager", "package.json"))
            
            deps = data.get("dependencies", {})
            dev_deps = data.get("devDependencies", {})
            all_npm_deps = {**deps, **dev_deps}
            
            # Framework / Library detection with evidence
            framework_map = {
                "react": ("React", "framework"),
                "svelte": ("Svelte", "framework"),
                "vue": ("Vue", "framework"),
                "vite": ("Vite", "build_tool"),
                "next": ("Next.js", "framework"),
                "express": ("Express", "framework"),
                "tailwindcss": ("TailwindCSS", "tool"),
                "typescript": ("TypeScript", "language"),
                "postgresql": ("PostgreSQL", "database"),
                "pg": ("PostgreSQL", "database"),
            }
            
            for dep_name, version in deps.items():
                dependencies.append(DetectedDep(dep_name, "npm", str(version), is_dev=False))
                for key, (tech_name, cat) in framework_map.items():
                    if key in dep_name.lower():
                        technologies.append(DetectedTech(tech_name, cat, "package.json", str(version)))
                        
            for dep_name, version in dev_deps.items():
                dependencies.append(DetectedDep(dep_name, "npm", str(version), is_dev=True))
                for key, (tech_name, cat) in framework_map.items():
                    if key in dep_name.lower():
                        technologies.append(DetectedTech(tech_name, cat, "package.json", str(version)))
                        
        except Exception:
            pass

    # 2. Python Ecosystem (requirements.txt / pyproject.toml / setup.py / Pipfile)
    req_txt = path / "requirements.txt"
    if req_txt.exists() and req_txt.is_file():
        technologies.append(DetectedTech("Python", "language", "requirements.txt"))
        technologies.append(DetectedTech("pip", "package_manager", "requirements.txt"))
        try:
            with open(req_txt, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                match = re.split(r"[=<>]", line, 1)
                dep_name = match[0].strip()
                ver_spec = line[len(dep_name):].strip() if len(match) > 1 else None
                if dep_name:
                    dependencies.append(DetectedDep(dep_name, "pip", ver_spec))
                    dep_lower = dep_name.lower()
                    if "fastapi" in dep_lower:
                        technologies.append(DetectedTech("FastAPI", "framework", "requirements.txt", ver_spec))
                    elif "django" in dep_lower:
                        technologies.append(DetectedTech("Django", "framework", "requirements.txt", ver_spec))
                    elif "flask" in dep_lower:
                        technologies.append(DetectedTech("Flask", "framework", "requirements.txt", ver_spec))
                    elif "sqlalchemy" in dep_lower:
                        technologies.append(DetectedTech("SQLAlchemy", "tool", "requirements.txt", ver_spec))
                    elif "pytest" in dep_lower:
                        technologies.append(DetectedTech("pytest", "tool", "requirements.txt", ver_spec))
                    elif "pgvector" in dep_lower or "psycopg" in dep_lower:
                        technologies.append(DetectedTech("PostgreSQL", "database", "requirements.txt", ver_spec))
        except Exception:
            pass

    pyproject_toml = path / "pyproject.toml"
    if pyproject_toml.exists() and pyproject_toml.is_file():
        technologies.append(DetectedTech("Python", "language", "pyproject.toml"))

    # 3. Rust Ecosystem (Cargo.toml)
    cargo_toml = path / "Cargo.toml"
    if cargo_toml.exists() and cargo_toml.is_file():
        technologies.append(DetectedTech("Rust", "language", "Cargo.toml"))
        technologies.append(DetectedTech("Cargo", "build_tool", "Cargo.toml"))

    # 4. Java / Kotlin Ecosystem (pom.xml / build.gradle)
    pom_xml = path / "pom.xml"
    if pom_xml.exists() and pom_xml.is_file():
        technologies.append(DetectedTech("Java", "language", "pom.xml"))
        technologies.append(DetectedTech("Maven", "build_tool", "pom.xml"))

    build_gradle = path / "build.gradle"
    build_gradle_kts = path / "build.gradle.kts"
    if (build_gradle.exists() and build_gradle.is_file()) or (build_gradle_kts.exists() and build_gradle_kts.is_file()):
        evidence = "build.gradle" if build_gradle.exists() else "build.gradle.kts"
        technologies.append(DetectedTech("Java/Kotlin", "language", evidence))
        technologies.append(DetectedTech("Gradle", "build_tool", evidence))

    # 5. Flutter / Dart (pubspec.yaml)
    pubspec_yaml = path / "pubspec.yaml"
    if pubspec_yaml.exists() and pubspec_yaml.is_file():
        technologies.append(DetectedTech("Dart", "language", "pubspec.yaml"))
        technologies.append(DetectedTech("Flutter", "framework", "pubspec.yaml"))

    # Deduplicate technologies by (name, evidence_source)
    unique_techs: Dict[Tuple[str, str], DetectedTech] = {}
    for t in technologies:
        unique_techs[(t.name.lower(), t.evidence_source)] = t
    
    unique_deps: Dict[Tuple[str, str], DetectedDep] = {}
    for d in dependencies:
        unique_deps[(d.name.lower(), d.ecosystem)] = d

    return list(unique_techs.values()), list(unique_deps.values())
