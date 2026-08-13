from typing import List, Optional
from pydantic import BaseModel, Field
from core.llm import LLMProviderGateway, BaseLLMProvider

class PlanStepSchema(BaseModel):
    id: str = Field(description="Unique step ID, e.g. step_1")
    title: str = Field(description="Short human readable action step title")
    description: str = Field(description="Detailed step execution instructions")
    tool: Optional[str] = Field(default="web_search", description="Tool name: web_search | filesystem | browser | scheduler")
    status: str = Field(default="pending", description="Initial step status: pending")

class TaskPlan(BaseModel):
    goal: str = Field(description="Original user goal statement")
    steps: List[PlanStepSchema] = Field(description="Sequential list of executable steps")

class AgentPlanner:
    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm = llm_provider or LLMProviderGateway.get_provider()

    async def generate_plan(self, goal: str) -> TaskPlan:
        system_prompt = (
            "You are an autonomous AI Agent Planner. "
            "Your task is to decompose high-level user goals into structured, logical, sequential execution steps. "
            "Each step must assign an appropriate tool from [web_search, filesystem, browser, scheduler]."
        )
        user_prompt = f"Goal to accomplish: '{goal}'"
        
        try:
            plan = await self.llm.generate_structured(user_prompt, TaskPlan, system_prompt)
            if not plan.steps:
                raise ValueError("Planner returned an empty plan step list")
            return plan
        except Exception as e:
            # Fallback deterministic plan if structured LLM generation encounters an issue
            return TaskPlan(
                goal=goal,
                steps=[
                    PlanStepSchema(
                        id="step_1",
                        title=f"Analyze requirement: '{goal[:40]}'",
                        description="Gather required context and parameters for execution",
                        tool="web_search",
                        status="pending"
                    ),
                    PlanStepSchema(
                        id="step_2",
                        title="Execute main task objective",
                        description="Perform primary action and gather intermediate results",
                        tool="filesystem",
                        status="pending"
                    ),
                    PlanStepSchema(
                        id="step_3",
                        title="Verify results and formulate response",
                        description="Validate completed work against user requirements",
                        tool="browser",
                        status="pending"
                    )
                ]
            )
