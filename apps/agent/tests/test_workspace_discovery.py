import pytest
import os
from httpx import AsyncClient, ASGITransport
from main import app
from db.session import AsyncSessionLocal, init_db
from sqlalchemy.future import select
from db.models import Workspace, Project

@pytest.mark.asyncio
async def test_workspace_discovery_flow():
    await init_db()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        target_path = "/home/rev/My Personal Space/Projects"
        res = await ac.post("/api/v1/projects/workspace", json={"path": target_path})
        assert res.status_code == 200
        data = res.json()
        
        assert "workspace" in data
        assert "projects" in data
        assert data["workspace"]["path"] == target_path
        
        projects = data["projects"]
        project_titles = [p["title"] for p in projects]

        # REQUIREMENT 1: NEVER INCLUDE THE WORKSPACE ROOT AS A PROJECT
        assert "Projects" not in project_titles
        
        # REQUIREMENT 2: ONLY DISCOVER IMMEDIATE CHILD DIRECTORIES
        for p in projects:
            assert p["path"] != target_path
            assert os.path.dirname(p["path"]) == target_path

        # REQUIREMENT 3 & 4: DISCOVERED CHILD PROJECTS
        assert "Myagent" in project_titles
        assert "codePilot" in project_titles
        assert "relearn.ai" in project_titles
        assert "Miee" in project_titles
        assert "Github-Companion" in project_titles
        assert "Acadex" in project_titles

        # REQUIREMENT 6: NO PLAIN TEXT CLASSIFICATION
        for p in projects:
            assert "Plain Text" not in p["languages"]

        # REQUIREMENT 8: GIT DETECTION PER PROJECT
        myagent_proj = next(p for p in projects if p["title"] == "Myagent")
        assert myagent_proj["git_repository"] is True
        assert "Python" in myagent_proj["languages"]
        assert "TypeScript" in myagent_proj["languages"]
        assert "FastAPI" in myagent_proj["frameworks"]
        assert "Svelte" in myagent_proj["frameworks"]
        assert "Tauri" in myagent_proj["frameworks"]

        code_pilot = next(p for p in projects if p["title"] == "codePilot")
        assert "TypeScript" in code_pilot["languages"]
        assert "React" in code_pilot["frameworks"]

        miee_proj = next(p for p in projects if p["title"] == "Miee")
        assert "Dart" in miee_proj["languages"]
        assert "Flutter" in miee_proj["frameworks"]

        # REQUIREMENT 9: METADATA & CONFIDENCE
        assert "detection_confidence" in myagent_proj
        assert myagent_proj["detection_confidence"] in ("high", "medium", "low")

        # REQUIREMENT 11: RESCAN METADATA UPDATE
        res_rescan = await ac.post("/api/v1/projects/scan")
        assert res_rescan.status_code == 200
        rescan_projects = res_rescan.json()["projects"]
        assert len(rescan_projects) == len(projects)

        # INVALID PATH VALIDATION
        res_invalid = await ac.post("/api/v1/projects/workspace", json={"path": "/non/existent/path/for/cocoa/test"})
        assert res_invalid.status_code == 404
        assert res_invalid.json()["detail"] == "Workspace directory does not exist."

@pytest.mark.asyncio
async def test_db_persistence():
    async with AsyncSessionLocal() as session:
        ws_res = await session.execute(select(Workspace).where(Workspace.is_active == True))
        ws = ws_res.scalar_one_or_none()
        assert ws is not None
        
        proj_res = await session.execute(select(Project).where(Project.workspace_id == ws.id))
        projects = proj_res.scalars().all()
        assert len(projects) > 0
        titles = [p.title for p in projects]
        assert "Projects" not in titles
