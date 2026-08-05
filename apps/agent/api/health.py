from fastapi import APIRouter
from config import settings

router = APIRouter(tags=["Health"])

@router.get("/health")
async def health_check():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "llm_provider": settings.LLM_PROVIDER,
    }
