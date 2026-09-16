import re
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from core.llm import LLMProviderGateway, ModelRole

logger = logging.getLogger(__name__)

class AutomationNLSchema(BaseModel):
    title: str = Field(description="Short human readable automation title")
    description: str = Field(description="Goal prompt for the agent to execute")
    trigger_type: str = Field(default="CRON", description="CRON | INTERVAL | ONE_TIME | MANUAL | TASK_COMPLETION | FILE_CHANGE | GIT_CHANGE | CONDITION")
    trigger_config: Dict[str, Any] = Field(default_factory=dict, description="Structured trigger parameters (e.g. cron_expression, interval_seconds)")
    notification_level: str = Field(default="ON_FAILURE", description="ALWAYS | ON_FAILURE | ON_CHANGE | ON_IMPORTANT_EVENT | SILENT")
    condition: Optional[str] = Field(default=None, description="Optional condition rule for execution or notification")
    allowed_tools: list[str] = Field(default_factory=list, description="List of permitted tools")
    max_retries: int = Field(default=2, description="Maximum retry count")

class NLAutomationParser:
    def __init__(self):
        self.llm = LLMProviderGateway.get_provider(role=ModelRole.REASONING)

    async def parse_natural_language(self, text: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Parses natural language prompt into a validated automation definition."""
        system_prompt = (
            "You are an AI Automation Specialist for Cocoa Agent. "
            "Convert natural language automation requests into a structured automation definition. "
            "trigger_type options: CRON, INTERVAL, ONE_TIME, MANUAL, TASK_COMPLETION, FILE_CHANGE, GIT_CHANGE, CONDITION. "
            "notification_level options: ALWAYS, ON_FAILURE, ON_CHANGE, ON_IMPORTANT_EVENT, SILENT. "
            "For cron triggers, specify valid standard cron expressions (e.g., '0 9 * * 1-5' for weekdays at 9am)."
        )
        user_prompt = f"Convert this request into an automation definition: '{text}'"

        try:
            parsed = await self.llm.generate_structured(user_prompt, AutomationNLSchema, system_prompt)
            return parsed.model_dump()
        except Exception as e:
            logger.info(f"LLM natural language automation parsing fallback for '{text}': {e}")
            return self._build_deterministic_fallback(text)

    def _build_deterministic_fallback(self, text: str) -> Dict[str, Any]:
        lower = text.lower()
        trigger_type = "INTERVAL"
        trigger_config: Dict[str, Any] = {"minutes": 60}

        if "cron" in lower or "at " in lower or "every weekday" in lower or "daily" in lower:
            trigger_type = "CRON"
            if "weekday" in lower:
                trigger_config = {"cron_expression": "0 9 * * 1-5"}
            elif "daily" in lower or "every day" in lower:
                trigger_config = {"cron_expression": "0 9 * * *"}
            else:
                trigger_config = {"cron_expression": "0 0 * * *"}

        elif "every " in lower:
            m = re.search(r'every\s+(\d+)\s*(sec|min|hour|day)', lower)
            if m:
                val = int(m.group(1))
                unit = m.group(2)
                if "sec" in unit: trigger_config = {"seconds": val}
                elif "min" in unit: trigger_config = {"minutes": val}
                elif "hour" in unit: trigger_config = {"hours": val}
                elif "day" in unit: trigger_config = {"days": val}

        notification_level = "ON_FAILURE"
        if "always" in lower:
            notification_level = "ALWAYS"
        elif "silent" in lower:
            notification_level = "SILENT"

        return {
            "title": text[:50].capitalize(),
            "description": text,
            "trigger_type": trigger_type,
            "trigger_config": trigger_config,
            "notification_level": notification_level,
            "condition": "tests_failed" if "test" in lower else None,
            "allowed_tools": ["terminal", "git_status", "list_directory", "read_file"],
            "max_retries": 2
        }

nl_automation_parser = NLAutomationParser()
