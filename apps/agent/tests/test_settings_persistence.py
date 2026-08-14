import pytest
from fastapi.testclient import TestClient
from main import app
from db.session import init_db, AsyncSessionLocal
from db.models import SettingModel
from sqlalchemy.future import select
from config import settings

client = TestClient(app)

@pytest.mark.asyncio
async def test_single_setting_persistence():
    await init_db()

    # Update single setting via API
    res = client.post("/api/v1/settings", json={"key": "test_theme_mode", "value": "dark"})
    assert res.status_code == 200
    data = res.json()
    assert data["key"] == "test_theme_mode"
    assert data["value"] == "dark"

    # Verify database persistence across fresh session
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SettingModel).where(SettingModel.key == "test_theme_mode"))
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.value == "dark"

@pytest.mark.asyncio
async def test_bulk_settings_persistence_and_runtime_sync():
    await init_db()

    payload = {
        "settings": {
            "llm_provider": "Groq",
            "llm_model": "llama-3.3-70b-versatile",
            "llm_api_key": "gsk_test_mock_key_12345",
            "backend_url": "http://localhost:8000"
        }
    }

    res = client.post("/api/v1/settings/bulk", json=payload)
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 4

    # Verify runtime settings updated
    assert settings.LLM_PROVIDER == "Groq"
    assert settings.LLM_MODEL == "llama-3.3-70b-versatile"
    assert settings.LLM_API_KEY == "gsk_test_mock_key_12345"

    # Get settings list
    res_list = client.get("/api/v1/settings")
    assert res_list.status_code == 200
    all_settings = {s["key"]: s["value"] for s in res_list.json()}
    assert all_settings["llm_provider"] == "Groq"
    assert all_settings["llm_model"] == "llama-3.3-70b-versatile"

@pytest.mark.asyncio
async def test_masked_secrets_in_settings_list():
    await init_db()

    # Save secret key
    client.post("/api/v1/settings", json={"key": "secret_api_key", "value": "gsk_mock_test_key_dummy_not_real_key_0000"})

    # Fetch with mask_secrets=True
    res = client.get("/api/v1/settings?mask_secrets=true")
    assert res.status_code == 200
    all_settings = {s["key"]: s["value"] for s in res.json()}
    
    # Secret must be masked
    secret_val = all_settings["secret_api_key"]
    assert "••••" in secret_val
    assert secret_val != "gsk_mock_test_key_dummy_not_real_key_0000"
