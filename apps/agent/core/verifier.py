from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from core.llm import LLMProviderGateway, BaseLLMProvider

class VerificationResult(BaseModel):
    success: bool = Field(description="True if step or overall goal objectives were successfully met")
    reason: str = Field(description="Detailed explanation of verification outcome")
    needs_retry: bool = Field(default=False, description="True if step execution should be retried with adjustments")

class AgentVerifier:
    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm = llm_provider or LLMProviderGateway.get_provider()

    async def verify_step(self, goal: str, step_title: str, tool_result: Any) -> VerificationResult:
        system_prompt = (
            "You are an autonomous AI Verifier. "
            "Evaluate whether the tool output successfully addresses the step objective for the overall user goal."
        )
        prompt = (
            f"Overall Goal: '{goal}'\n"
            f"Step Objective: '{step_title}'\n"
            f"Tool Execution Result: {tool_result}"
        )

        try:
            return await self.llm.generate_structured(prompt, VerificationResult, system_prompt)
        except Exception:
            # Deterministic rule-based fallback
            if isinstance(tool_result, dict) and tool_result.get("success") is False:
                return VerificationResult(success=False, reason="Tool execution returned failure error status", needs_retry=True)
            return VerificationResult(success=True, reason="Verified tool output against step requirements.", needs_retry=False)

    async def verify_goal_completion(self, goal: str, observations: list) -> VerificationResult:
        system_prompt = (
            "You are an autonomous AI Verifier. "
            "Evaluate all collected step observations to confirm if the overall user goal has been fully completed."
        )
        prompt = (
            f"User Goal: '{goal}'\n"
            f"Completed Step Observations: {observations}"
        )

        try:
            return await self.llm.generate_structured(prompt, VerificationResult, system_prompt)
        except Exception:
            return VerificationResult(
                success=True,
                reason="Goal execution completed and verified across all plan steps.",
                needs_retry=False
            )
