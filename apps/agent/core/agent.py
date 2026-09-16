import uuid
import logging
from datetime import datetime
from typing import Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import AsyncSessionLocal
from db.models import Task, TaskStep, ActivityLog
from core.state import ExecutionContext, AgentState
from core.planner import AgentPlanner
from core.executor import AgentExecutor
from core.verifier import AgentVerifier
from core.rag.intent_router import context_intent_router, ContextIntentRouter, ContextRoutingMode
from core.rag.context_builder import unified_agent_context_builder, UnifiedAgentContextBuilder, UnifiedAgentContext
from core.research.providers.router import search_provider_router, SearchProviderRouter
from api.websocket import ws_manager

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    def __init__(
        self,
        planner: Optional[AgentPlanner] = None,
        executor: Optional[AgentExecutor] = None,
        verifier: Optional[AgentVerifier] = None,
        intent_router: Optional[ContextIntentRouter] = None,
        context_builder: Optional[UnifiedAgentContextBuilder] = None,
        search_router: Optional[SearchProviderRouter] = None
    ):
        self.planner = planner or AgentPlanner()
        self.verifier = verifier or AgentVerifier()
        self.executor = executor or AgentExecutor(verifier=self.verifier)
        self.intent_router = intent_router or context_intent_router
        self.context_builder = context_builder or unified_agent_context_builder
        self.search_router = search_router or search_provider_router

    async def run_goal(self, goal: str, project_id: Optional[str] = None, task_id: Optional[str] = None) -> Task:
        t_id = task_id or str(uuid.uuid4())
        
        async with AsyncSessionLocal() as db:
            # Check or create DB task
            task = await db.get(Task, t_id)
            if not task:
                task = Task(
                    id=t_id,
                    title=goal,
                    description=f"Goal: {goal}",
                    status="planning",
                    project_id=project_id
                )
                db.add(task)
                await db.commit()
                await db.refresh(task)

            # Broadcast starting event
            await ws_manager.broadcast({
                "event": "agent.started",
                "task_id": t_id,
                "status": "planning",
                "message": f"Starting autonomous goal planning for '{goal}'"
            })

            # Create Execution Context
            ctx = ExecutionContext(task_id=t_id, goal=goal, project_id=project_id, current_state=AgentState.PLANNING)

            # Helper for DB activity log insertion
            async def log_activity(event_type: str, message: str, details: dict):
                async with AsyncSessionLocal() as log_db:
                    now_str = datetime.now().strftime("%H:%M:%S")
                    log_entry = ActivityLog(
                        id=str(uuid.uuid4()),
                        task_id=t_id,
                        timestamp=now_str,
                        message=message,
                        status="active" if "start" in event_type else "done",
                        details=[str(v) for v in details.values()] if details else None
                    )
                    log_db.add(log_entry)
                    await log_db.commit()

            await log_activity("agent.started", f"Goal execution initialized: '{goal}'", {})

            # 1. Detect Intent and determine Context Routing Mode
            routing_decision = await self.intent_router.route(goal, project_id=project_id)
            await log_activity(
                "agent.context_routed",
                f"Context routing decided: {routing_decision.mode.value} (RAG: {routing_decision.needs_rag}, Web: {routing_decision.needs_web})",
                {"mode": routing_decision.mode.value, "reasoning": routing_decision.reasoning}
            )
            await ws_manager.broadcast({
                "event": "agent.context_routed",
                "task_id": t_id,
                "routing_mode": routing_decision.mode.value,
                "reasoning": routing_decision.reasoning,
                "needs_rag": routing_decision.needs_rag,
                "needs_web": routing_decision.needs_web
            })

            # 2. Retrieve Web Research if needed (Locked: Tavily Primary -> DuckDuckGo Fallback)
            web_sources: List[Any] = []
            provider_used = "none"
            if routing_decision.needs_web:
                try:
                    results, provider_used = await self.search_router.search(goal, max_results=5)
                    web_sources = results
                    await log_activity(
                        "agent.web_retrieved",
                        f"Web research completed using {provider_used} ({len(results)} sources retrieved)",
                        {"provider": provider_used, "sources_count": len(results)}
                    )
                except Exception as web_err:
                    logger.warning(f"Web research retrieval error: {web_err}")

            # 3. Assemble Unified Context (bounded context + strict provenance)
            unified_context: Optional[UnifiedAgentContext] = None
            if routing_decision.needs_rag or routing_decision.needs_web:
                try:
                    unified_context = await self.context_builder.build_unified_context(
                        query=goal,
                        project_id=project_id if routing_decision.needs_rag else None,
                        web_sources=web_sources
                    )
                    await log_activity(
                        "agent.context_assembled",
                        f"Unified context assembled: {len(unified_context.project_chunks)} RAG chunks, {len(unified_context.web_items)} Web sources",
                        {
                            "rag_chunks": len(unified_context.project_chunks),
                            "web_items": len(unified_context.web_items)
                        }
                    )
                except Exception as ctx_err:
                    logger.warning(f"Unified context building error: {ctx_err}")

            # 4. Record provenance and routing in task.plan_data
            plan_meta = {
                "context_routing": routing_decision.mode.value,
                "needs_rag": routing_decision.needs_rag,
                "needs_web": routing_decision.needs_web,
                "reasoning": routing_decision.reasoning,
                "provider_used": provider_used,
                "rag_chunks_count": len(unified_context.project_chunks) if unified_context else 0,
                "web_sources_count": len(unified_context.web_items) if unified_context else 0,
                "sources": []
            }
            if unified_context:
                for pc in unified_context.project_chunks:
                    plan_meta["sources"].append({
                        "type": "project",
                        "file": pc.file,
                        "path": pc.path,
                        "symbol": pc.symbol,
                        "relevance": pc.relevance
                    })
                for ws in unified_context.web_items:
                    plan_meta["sources"].append({
                        "type": "web",
                        "title": ws.title,
                        "url": ws.url,
                        "domain": ws.domain,
                        "relevance": ws.relevance,
                        "published_date": ws.published_date
                    })

            task.plan_data = plan_meta
            await db.commit()

            # 5. Generate Plan with unified context
            plan = await self.planner.generate_plan(goal, project_id=project_id, context=unified_context)

            # Insert Plan Steps into DB
            for idx, s in enumerate(plan.steps):
                step_record = TaskStep(
                    id=str(uuid.uuid4()),
                    task_id=t_id,
                    step_number=idx + 1,
                    label=s.title,
                    status="pending"
                )
                db.add(step_record)
            
            task.status = "executing"
            await db.commit()

            # Execute Plan
            final_ctx = await self.executor.execute_plan(ctx, plan, on_activity=log_activity)

            # Update DB Task Status & Result
            task.status = final_ctx.current_state.value
            if final_ctx.final_result:
                task.result = final_ctx.final_result
            
            await db.commit()
            await db.refresh(task)
            return task

agent_orchestrator = AgentOrchestrator()
