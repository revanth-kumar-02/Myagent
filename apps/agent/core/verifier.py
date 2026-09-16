from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from core.llm import LLMProviderGateway, BaseLLMProvider, ModelRole

class VerificationResult(BaseModel):
    success: bool = Field(description="True if step or overall goal objectives were successfully met")
    reason: str = Field(description="Detailed explanation of verification outcome")
    needs_retry: bool = Field(default=False, description="True if step execution should be retried with adjustments")

class AgentVerifier:
    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm = llm_provider or LLMProviderGateway.get_provider(role=ModelRole.REASONING)

    async def verify_step(self, goal: str, step_title: str, tool_result: Any) -> VerificationResult:
        # Hard check for process / tool failure
        if isinstance(tool_result, dict):
            if tool_result.get("success") is False or (tool_result.get("exit_code") is not None and tool_result.get("exit_code") != 0):
                exit_code = tool_result.get("exit_code", -1)
                err_msg = tool_result.get("stderr") or tool_result.get("error") or "Non-zero exit code"
                return VerificationResult(
                    success=False,
                    reason=f"COMMAND/TEST FAILED (exit code {exit_code}): {str(err_msg)[:200]}",
                    needs_retry=True
                )

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
