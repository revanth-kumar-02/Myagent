import logging
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Structured in-memory event registry for observability
RUNTIME_EVENTS: List[Dict[str, Any]] = []

def record_fallback_event(provider: str, reason: str, fallback_provider: str) -> Dict[str, Any]:
    """Records a structured fallback event for observability (no secrets logged)."""
    event = {
        "event_type": "provider.fallback",
        "provider": provider,
        "reason": reason,
        "fallback_provider": fallback_provider,
        "timestamp": time.time()
    }
    RUNTIME_EVENTS.append(event)
    status_msg = f"[PROVIDER FALLBACK] {provider} unavailable ({reason}) -> Using {fallback_provider}"
    logger.warning(status_msg)
    print(status_msg)
    return event

def get_recent_fallback_events(limit: int = 10) -> List[Dict[str, Any]]:
    return RUNTIME_EVENTS[-limit:]
