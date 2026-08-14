import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.future import select

from db.session import AsyncSessionLocal
from db.models import Automation, ActivityLog
from api.websocket import ws_manager

logger = logging.getLogger(__name__)

class AutomationSchedulerManager:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.running_jobs: Dict[str, bool] = {}

    async def start(self):
        """Starts the background AsyncIOScheduler and recovers enabled automations from DB."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("APScheduler background automation engine started.")
            await self.recover_enabled_automations()

    async def stop(self):
        """Gracefully stops the scheduler on FastAPI shutdown."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler background automation engine stopped.")

    async def recover_enabled_automations(self):
        """Loads enabled automations from the database on startup and registers valid jobs."""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Automation).where(Automation.is_active == True))
                automations = result.scalars().all()
                
                count = 0
                for auto in automations:
                    success = self.register_automation_job(auto)
                    if success:
                        count += 1
                logger.info(f"Restored {count} active automation jobs in APScheduler.")
        except Exception as e:
            logger.error(f"Error during startup recovery of automations: {e}")

    def parse_trigger(self, trigger_config: Optional[dict]):
        """Parses trigger_config dictionary into an APScheduler trigger (Interval or Cron)."""
        if not trigger_config or not isinstance(trigger_config, dict):
            # Default fallback: 1 hour interval
            return IntervalTrigger(hours=1)

        t_type = str(trigger_config.get("type") or trigger_config.get("trigger_type") or "interval").lower()

        if t_type == "interval":
            seconds = int(trigger_config.get("seconds") or 0)
            minutes = int(trigger_config.get("minutes") or 0)
            hours = int(trigger_config.get("hours") or 0)
            days = int(trigger_config.get("days") or 0)
            
            if seconds == 0 and minutes == 0 and hours == 0 and days == 0:
                seconds = 60 # Default to 60s if specified as 0
            
            return IntervalTrigger(seconds=seconds, minutes=minutes, hours=hours, days=days)

        elif t_type == "cron":
            cron_expr = trigger_config.get("cron_expression") or trigger_config.get("cron")
            if cron_expr and isinstance(cron_expr, str):
                parts = cron_expr.strip().split()
                if len(parts) == 5:
                    return CronTrigger(
                        minute=parts[0],
                        hour=parts[1],
                        day=parts[2],
                        month=parts[3],
                        day_of_week=parts[4]
                    )
            # Standard cron fields fallback
            return CronTrigger(
                minute=trigger_config.get("minute", "*"),
                hour=trigger_config.get("hour", "*"),
                day=trigger_config.get("day", "*"),
                month=trigger_config.get("month", "*"),
                day_of_week=trigger_config.get("day_of_week", "*")
            )

        return IntervalTrigger(hours=1)

    def register_automation_job(self, auto: Automation) -> bool:
        """Registers or replaces an automation job in APScheduler using auto.id as job ID."""
        if not auto.is_active:
            self.remove_automation_job(auto.id)
            return False

        try:
            trigger = self.parse_trigger(auto.trigger_config)
            self.scheduler.add_job(
                func=self._job_wrapper,
                trigger=trigger,
                id=str(auto.id),
                args=[str(auto.id)],
                replace_existing=True,
                max_instances=1,
                coalesce=True
            )
            logger.info(f"Registered automation job '{auto.title}' (ID: {auto.id})")
            return True
        except Exception as e:
            logger.error(f"Failed to register automation job {auto.id}: {e}")
            return False

    def remove_automation_job(self, automation_id: str):
        """Removes a job from APScheduler if present."""
        if self.scheduler.get_job(str(automation_id)):
            self.scheduler.remove_job(str(automation_id))
            logger.info(f"Removed automation job ID: {automation_id}")

    async def trigger_now(self, automation_id: str):
        """Immediately triggers an automation execution in a background task."""
        asyncio.create_task(self._execute_automation(automation_id))

    async def _job_wrapper(self, automation_id: str):
        """Wrapper invoked by APScheduler to handle task execution safely."""
        await self._execute_automation(automation_id)

    async def _execute_automation(self, automation_id: str):
        """Executes an automation through the Agent Orchestrator with complete event reporting."""
        # Prevent overlapping execution of the same job
        if self.running_jobs.get(automation_id):
            logger.warning(f"Automation {automation_id} is already running. Skipping overlap.")
            return

        self.running_jobs[automation_id] = True
        
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Automation).where(Automation.id == automation_id))
                auto = result.scalar_one_or_none()

                if not auto:
                    logger.error(f"Automation {automation_id} not found in DB.")
                    return

                if not auto.is_active:
                    logger.info(f"Automation {automation_id} is disabled. Skipping execution.")
                    self.remove_automation_job(automation_id)
                    return

                prompt = auto.description or auto.title
                project_id = auto.project_id

                # Broadcast start event
                await ws_manager.broadcast({
                    "event": "automation.started",
                    "automation_id": auto.id,
                    "title": auto.title,
                    "message": f"Automation '{auto.title}' triggered"
                })

                # Lazy import agent_orchestrator to prevent circular imports
                from core.agent import agent_orchestrator
                
                # Execute via agent orchestrator
                task = await agent_orchestrator.run_goal(
                    goal=prompt,
                    project_id=project_id
                )

                now_utc = datetime.utcnow()
                auto.last_run_at = now_utc

                if task.status in ["completed", "done", "verified"]:
                    auto.last_run_result = task.result or "Completed successfully"
                    await db.commit()

                    await ws_manager.broadcast({
                        "event": "automation.completed",
                        "automation_id": auto.id,
                        "title": auto.title,
                        "task_id": task.id,
                        "result": auto.last_run_result
                    })
                else:
                    auto.last_run_result = f"Failed: {task.result or 'Task failed step execution'}"
                    await db.commit()

                    await ws_manager.broadcast({
                        "event": "automation.failed",
                        "automation_id": auto.id,
                        "title": auto.title,
                        "task_id": task.id,
                        "error": auto.last_run_result
                    })

        except Exception as e:
            logger.error(f"Error executing automation {automation_id}: {e}", exc_info=True)
            await ws_manager.broadcast({
                "event": "automation.failed",
                "automation_id": automation_id,
                "error": str(e)
            })
        finally:
            self.running_jobs[automation_id] = False

automation_scheduler = AutomationSchedulerManager()
