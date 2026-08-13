import json
import logging
from typing import Dict, Any
from schemas.schemas import ResearchPlan, ResearchPlanStep
from core.llm import LLMProviderGateway

logger = logging.getLogger(__name__)

class ResearchPlanner:
    def __init__(self, llm_gateway: LLMProviderGateway = None):
        self.llm_gateway = llm_gateway or LLMProviderGateway()

    async def generate_plan(self, goal: str) -> ResearchPlan:
        """
        Generates a structured multi-step ResearchPlan for a natural-language goal.
        """
        prompt = (
            f"You are Cocoa's Research Planner.\n"
            f"Decompose the following research goal into 2-4 focused investigation steps.\n"
            f"Goal: {goal}\n\n"
            f"Respond strictly in valid JSON matching this schema:\n"
            f"{{\n"
            f'  "goal": "{goal}",\n'
            f'  "steps": [\n'
            f'    {{\n'
            f'      "id": "step_1",\n'
            f'      "objective": "High-level investigation objective",\n'
            f'      "queries": ["web search query 1", "web search query 2"],\n'
            f'      "status": "pending"\n'
            f'    }}\n'
            f'  ]\n'
            f'}}\n'
        )

        try:
            provider = self.llm_gateway.get_provider()
            response_text = await provider.generate_text(prompt)
            
            # Extract JSON block if surrounded by markdown code blocks
            clean_text = response_text.strip()
            if "```json" in clean_text:
                clean_text = clean_text.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_text:
                clean_text = clean_text.split("```")[1].split("```")[0].strip()

            parsed = json.loads(clean_text)
            if "steps" in parsed and isinstance(parsed["steps"], list):
                steps = []
                for i, s in enumerate(parsed["steps"]):
                    steps.append(
                        ResearchPlanStep(
                            id=s.get("id") or f"step_{i+1}",
                            objective=s.get("objective") or f"Investigate aspect {i+1}",
                            queries=s.get("queries") if isinstance(s.get("queries"), list) else [goal],
                            status="pending"
                        )
                    )
                return ResearchPlan(goal=goal, steps=steps)
        except Exception as e:
            logger.warning(f"LLM planner failed or returned invalid JSON: {e}. Using intelligent fallback plan.")

        # Fallback structured plan
        return ResearchPlan(
            goal=goal,
            steps=[
                ResearchPlanStep(
                    id="step_1",
                    objective=f"Search technical specifications and architecture overview for: {goal}",
                    queries=[goal, f"{goal} architecture benchmarks"],
                    status="pending"
                ),
                ResearchPlanStep(
                    id="step_2",
                    objective=f"Evaluate community benchmarks and real-world deployment trade-offs for: {goal}",
                    queries=[f"{goal} comparison pros and cons", f"{goal} production best practices"],
                    status="pending"
                )
            ]
        )
