import logging
from typing import Dict, Any, Type, TypeVar, Optional, List
from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from core.llm.registry import ModelConfig
from core.llm.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

class RuleBasedLLMProvider(BaseLLMProvider):
    """
    Deterministic local fallback provider used when no API credentials are supplied
    or for hermetic offline test runs.
    """

    @property
    def name(self) -> str:
        return "rule_based"

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> str:
        return f"RuleBasedLLM response for: {prompt[:100]}..."

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> str:
        last_msg = messages[-1]["content"] if messages else "empty"
        return f"RuleBasedLLM chat reply to: {last_msg[:100]}"

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> T:
        fields = schema.model_fields
        mock_data: Dict[str, Any] = {}
        for f_name, f_info in fields.items():
            if f_name == "goal":
                mock_data["goal"] = prompt[:100]
            elif f_name == "steps":
                mock_data["steps"] = [
                    {
                        "id": "step_1",
                        "title": "Analyze user request and gather context",
                        "description": "Examine requirements and identify initial targets",
                        "tool": "web_search",
                        "status": "pending"
                    },
                    {
                        "id": "step_2",
                        "title": "Inspect filesystem resources",
                        "description": "Read project directory and verify local files",
                        "tool": "filesystem",
                        "status": "pending"
                    },
                    {
                        "id": "step_3",
                        "title": "Synthesize results and verify goal completion",
                        "description": "Formulate final findings and verify requirements",
                        "tool": "browser",
                        "status": "pending"
                    }
                ]
            elif f_name == "success":
                mock_data["success"] = True
            elif f_name == "reason":
                mock_data["reason"] = "All step objectives verified and completed successfully."
            elif f_name == "needs_retry":
                mock_data["needs_retry"] = False
            elif f_info.default is not None and f_info.default != PydanticUndefined:
                mock_data[f_name] = f_info.default
            else:
                # Infer type from annotation
                annotation = f_info.annotation
                if annotation in (int, "int"):
                    mock_data[f_name] = 1
                elif annotation in (float, "float"):
                    mock_data[f_name] = 1.0
                elif annotation in (bool, "bool"):
                    mock_data[f_name] = True
                elif annotation in (list, "list") or (hasattr(annotation, "__origin__") and annotation.__origin__ is list):
                    mock_data[f_name] = []
                elif annotation in (dict, "dict") or (hasattr(annotation, "__origin__") and annotation.__origin__ is dict):
                    mock_data[f_name] = {}
                else:
                    mock_data[f_name] = f"rule_based_{f_name}"
        return schema.model_validate(mock_data)

    async def understand_vision(
        self,
        image_bytes: bytes,
        prompt: str,
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> str:
        return f"RuleBased vision description for image ({len(image_bytes)} bytes): {prompt}"

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> str:
        return "RuleBased transcribed speech audio text."

    async def synthesize_speech(
        self,
        text: str,
        model_config: Optional[ModelConfig] = None,
        **kwargs
    ) -> bytes:
        return b"RIFF_MOCK_WAV_HEADER_DATA"
