from typing import List, Optional
from pydantic import BaseModel, Field
from core.llm import LLMProviderGateway, BaseLLMProvider

class PlanStepSchema(BaseModel):
    id: str = Field(description="Unique step ID, e.g. step_1")
    title: str = Field(description="Short human readable action step title")
    description: str = Field(description="Detailed step execution instructions")
    tool: Optional[str] = Field(default="web_search", description="Tool name: web_search | list_directory | search_files | read_file | inspect_file | create_file | edit_file | move_file | delete_file | browser | scheduler")
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
            "Assign tools from [web_search, list_directory, search_files, read_file, inspect_file, create_file, edit_file, move_file, delete_file, browser, scheduler]."
        )
        user_prompt = f"Goal to accomplish: '{goal}'"
        
        try:
            plan = await self.llm.generate_structured(user_prompt, TaskPlan, system_prompt)
            if not plan.steps:
                raise ValueError("Planner returned an empty plan step list")
            return plan
        except Exception as e:
            # Deterministic fallback plan matching prompt heuristics
            lower_goal = goal.lower()
            if "list" in lower_goal:
                tool_name = "list_directory"
            elif "find" in lower_goal or "search" in lower_goal:
                tool_name = "search_files"
            elif "read" in lower_goal or "cat" in lower_goal:
                tool_name = "read_file"
            elif "create" in lower_goal or "write" in lower_goal or "notes.md" in lower_goal:
                tool_name = "create_file"
            elif "edit" in lower_goal or "update" in lower_goal:
                tool_name = "edit_file"
            elif "move" in lower_goal or "rename" in lower_goal:
                tool_name = "move_file"
            elif "delete" in lower_goal or "remove" in lower_goal:
                tool_name = "delete_file"
            else:
                tool_name = "web_search"

            return TaskPlan(
                goal=goal,
                steps=[
                    PlanStepSchema(
                        id="step_1",
                        title=f"Analyze requirement for '{goal[:40]}'",
                        description="Gather required filesystem context and inspect parameters",
                        tool=tool_name,
                        status="pending"
                    ),
                    PlanStepSchema(
                        id="step_2",
                        title="Execute main task objective",
                        description="Perform primary action and gather observation results",
                        tool=tool_name,
                        status="pending"
                    ),
                    PlanStepSchema(
                        id="step_3",
                        title="Verify results and formulate response",
                        description="Validate completed work against user requirements",
                        tool="inspect_file",
                        status="pending"
                    )
                ]
            )
