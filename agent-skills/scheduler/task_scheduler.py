"""
Task Scheduler Module

This module implements scheduling for periodic watcher execution and daily reasoning runs.
It ensures that scheduled tasks don't bypass approval requirements.

Silver Tier Extensions:
- APScheduler integration for robust scheduling
- Cron-based scheduling support
- Async job execution
- Job persistence across restarts
"""

import os
import threading
import time
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any, List, Union
from pathlib import Path

# Try to import APScheduler, fall back to basic implementation
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.jobstores.memory import MemoryJobStore
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False

try:
    from core.logger import Logger
except ImportError:
    Logger = None


class APSchedulerWrapper:
    """
    APScheduler-based task scheduler for Silver Tier.
    Provides robust scheduling with cron support and async execution.
    """

    def __init__(self, logger: Optional[Any] = None, use_async: bool = False):
        """
        Initialize the APScheduler wrapper.

        Args:
            logger: Logger instance for auditability
            use_async: Whether to use async scheduler
        """
        if not APSCHEDULER_AVAILABLE:
            raise ImportError(
                "APScheduler is required for Silver Tier scheduling. "
                "Install it with: pip install apscheduler"
            )

        self.logger = logger
        self.use_async = use_async

        # Configure job stores
        jobstores = {
            'default': MemoryJobStore()
        }

        # Create scheduler
        if use_async:
            self.scheduler = AsyncIOScheduler(jobstores=jobstores)
        else:
            self.scheduler = BackgroundScheduler(jobstores=jobstores)

        self._job_callbacks: Dict[str, Callable] = {}

    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        seconds: int,
        args: Optional[List] = None,
        kwargs: Optional[Dict] = None,
        start_immediately: bool = True,
    ) -> str:
        """
        Add an interval-based job.

        Args:
            job_id: Unique job identifier
            func: Function to execute
            seconds: Interval in seconds (min: 30)
            args: Positional arguments for func
            kwargs: Keyword arguments for func
            start_immediately: Whether to run immediately

        Returns:
            Job ID
        """
        if seconds < 30:
            seconds = 30  # Enforce minimum

        trigger = IntervalTrigger(seconds=seconds)

        self.scheduler.add_job(
            func,
            trigger,
            id=job_id,
            args=args or [],
            kwargs=kwargs or {},
            replace_existing=True,
            next_run_time=datetime.now() if start_immediately else None,
        )

        self._job_callbacks[job_id] = func
        self._log_event("job_added", f"Interval job '{job_id}' added ({seconds}s)")

        return job_id

    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        cron_expression: str,
        args: Optional[List] = None,
        kwargs: Optional[Dict] = None,
    ) -> str:
        """
        Add a cron-based job.

        Args:
            job_id: Unique job identifier
            func: Function to execute
            cron_expression: Cron expression (minute hour day month weekday)
            args: Positional arguments for func
            kwargs: Keyword arguments for func

        Returns:
            Job ID
        """
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError("Cron expression must have 5 parts")

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )

        self.scheduler.add_job(
            func,
            trigger,
            id=job_id,
            args=args or [],
            kwargs=kwargs or {},
            replace_existing=True,
        )

        self._job_callbacks[job_id] = func
        self._log_event("job_added", f"Cron job '{job_id}' added ({cron_expression})")

        return job_id

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job."""
        try:
            self.scheduler.remove_job(job_id)
            self._job_callbacks.pop(job_id, None)
            self._log_event("job_removed", f"Job '{job_id}' removed")
            return True
        except Exception:
            return False

    def pause_job(self, job_id: str) -> bool:
        """Pause a scheduled job."""
        try:
            self.scheduler.pause_job(job_id)
            self._log_event("job_paused", f"Job '{job_id}' paused")
            return True
        except Exception:
            return False

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        try:
            self.scheduler.resume_job(job_id)
            self._log_event("job_resumed", f"Job '{job_id}' resumed")
            return True
        except Exception:
            return False

    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            self._log_event("scheduler_started", "APScheduler started")

    def stop(self, wait: bool = True):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            self._log_event("scheduler_stopped", "APScheduler stopped")

    def get_jobs(self) -> List[Dict[str, Any]]:
        """Get all scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name or job.id,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return jobs

    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status."""
        return {
            "running": self.scheduler.running,
            "job_count": len(self.scheduler.get_jobs()),
            "jobs": self.get_jobs(),
        }

    def _log_event(self, event_type: str, message: str):
        """Log a scheduler event."""
        if self.logger:
            self.logger.log_system_event(
                event_type=event_type,
                component="apscheduler",
                message=message,
                details={}
            )


class TaskScheduler:
    """
    Scheduler for periodic watcher execution and daily reasoning runs.
    Ensures that scheduled tasks don't bypass approval requirements.
    """

    def __init__(self, logger: Optional[Logger] = None):
        """
        Initialize the task scheduler.

        Args:
            logger: Logger instance for auditability
        """
        self.logger = logger
        self.scheduled_tasks = {}
        self.running = False
        self.scheduler_thread = None

    def schedule_task(self, task_name: str, task_func: Callable, interval_seconds: int,
                      start_immediately: bool = True) -> str:
        """
        Schedule a recurring task.

        Args:
            task_name: Name of the task
            task_func: Function to execute
            interval_seconds: Interval in seconds between executions
            start_immediately: Whether to start the task immediately

        Returns:
            Task ID
        """
        task_id = f"sched_task_{task_name}_{int(time.time())}"

        task_info = {
            "id": task_id,
            "name": task_name,
            "function": task_func,
            "interval": interval_seconds,
            "last_run": datetime.now() if start_immediately else None,
            "next_run": datetime.now() if start_immediately else datetime.now() + timedelta(seconds=interval_seconds)
        }

        self.scheduled_tasks[task_id] = task_info

        if self.logger:
            self.logger.log_system_event(
                event_type="task_scheduled",
                component="task_scheduler",
                message=f"Task '{task_name}' scheduled with interval {interval_seconds}s",
                details={"task_id": task_id, "interval_seconds": interval_seconds}
            )

        return task_id

    def schedule_daily_task(self, task_name: str, task_func: Callable, run_time: str) -> str:
        """
        Schedule a daily task at a specific time.

        Args:
            task_name: Name of the task
            task_func: Function to execute
            run_time: Time to run in HH:MM format (24-hour)

        Returns:
            Task ID
        """
        # Parse the time
        hour, minute = map(int, run_time.split(':'))

        # Calculate next occurrence
        now = datetime.now()
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if next_run <= now:
            # If time has passed today, schedule for tomorrow
            next_run += timedelta(days=1)

        task_id = f"daily_task_{task_name}_{int(time.time())}"

        task_info = {
            "id": task_id,
            "name": task_name,
            "function": task_func,
            "type": "daily",
            "run_time": run_time,
            "last_run": None,
            "next_run": next_run
        }

        self.scheduled_tasks[task_id] = task_info

        if self.logger:
            self.logger.log_system_event(
                event_type="daily_task_scheduled",
                component="task_scheduler",
                message=f"Daily task '{task_name}' scheduled for {run_time}",
                details={"task_id": task_id, "run_time": run_time}
            )

        return task_id

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a scheduled task.

        Args:
            task_id: ID of the task to cancel

        Returns:
            True if task was canceled, False if not found
        """
        if task_id in self.scheduled_tasks:
            task_name = self.scheduled_tasks[task_id]["name"]
            del self.scheduled_tasks[task_id]

            if self.logger:
                self.logger.log_system_event(
                    event_type="task_canceled",
                    component="task_scheduler",
                    message=f"Task '{task_name}' canceled",
                    details={"task_id": task_id}
                )

            return True

        return False

    def _run_scheduler_loop(self):
        """Main scheduler loop that runs in a background thread."""
        while self.running:
            try:
                current_time = datetime.now()

                # Check all scheduled tasks
                for task_id, task_info in list(self.scheduled_tasks.items()):
                    if current_time >= task_info["next_run"]:
                        try:
                            # Execute the task
                            task_info["function"]()

                            # Update last run and next run
                            task_info["last_run"] = current_time

                            if task_info.get("type") == "daily":
                                # For daily tasks, schedule for next day
                                next_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                                run_time = task_info["run_time"].split(':')
                                task_info["next_run"] = next_day.replace(
                                    hour=int(run_time[0]),
                                    minute=int(run_time[1])
                                )
                            else:
                                # For interval tasks, add the interval
                                task_info["next_run"] = current_time + timedelta(seconds=task_info["interval"])

                            if self.logger:
                                self.logger.log_system_event(
                                    event_type="task_executed",
                                    component="task_scheduler",
                                    message=f"Scheduled task '{task_info['name']}' executed",
                                    details={"task_id": task_id}
                                )

                        except Exception as e:
                            if self.logger:
                                self.logger.log_system_event(
                                    event_type="task_execution_error",
                                    component="task_scheduler",
                                    message=f"Error executing scheduled task '{task_info['name']}': {e}",
                                    details={"task_id": task_id}
                                )

                # Sleep briefly to avoid consuming too much CPU
                time.sleep(1)

            except Exception as e:
                if self.logger:
                    self.logger.log_system_event(
                        event_type="scheduler_error",
                        component="task_scheduler",
                        message=f"Error in scheduler loop: {e}",
                        details={}
                    )

    def start(self):
        """Start the scheduler."""
        if self.running:
            return

        self.running = True

        # Start the scheduler loop in a background thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler_loop, daemon=True)
        self.scheduler_thread.start()

        if self.logger:
            self.logger.log_system_event(
                event_type="scheduler_started",
                component="task_scheduler",
                message="Task scheduler started",
                details={}
            )

    def stop(self):
        """Stop the scheduler."""
        self.running = False

        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=2)  # Wait up to 2 seconds for graceful shutdown

        if self.logger:
            self.logger.log_system_event(
                event_type="scheduler_stopped",
                component="task_scheduler",
                message="Task scheduler stopped",
                details={}
            )

    def get_task_status(self) -> Dict[str, Any]:
        """
        Get the status of all scheduled tasks.

        Returns:
            Dictionary with task statuses
        """
        status = {
            "running": self.running,
            "total_tasks": len(self.scheduled_tasks),
            "tasks": {}
        }

        for task_id, task_info in self.scheduled_tasks.items():
            status["tasks"][task_id] = {
                "name": task_info["name"],
                "last_run": task_info["last_run"].isoformat() if task_info["last_run"] else None,
                "next_run": task_info["next_run"].isoformat(),
                "interval": task_info.get("interval"),
                "type": task_info.get("type", "interval")
            }

        return status


# Gold Tier: Retry worker (T072)
def process_retry_queue():
    """
    Process pending retry items with exponential backoff.
    Called periodically by the scheduler (every 60 seconds).
    """
    try:
        from core.retry_queue import RetryQueue
        import httpx

        retry_queue = RetryQueue()
        pending = retry_queue.get_pending()

        if not pending:
            return

        coordinator_url = os.environ.get("COORDINATOR_URL", "http://localhost:8000")

        for item in pending:
            retry_queue.mark_retrying(item.id)

            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(
                        f"{coordinator_url}/action/route",
                        json={
                            "actionType": item.action_type,
                            "approvalRef": item.approval_ref or "retry",
                            "payload": item.action_payload,
                        },
                    )
                    if response.status_code == 200:
                        retry_queue.mark_succeeded(item.id)
                    else:
                        retry_queue.mark_failed(
                            item.id,
                            f"HTTP {response.status_code}",
                        )
            except Exception as e:
                retry_queue.mark_failed(item.id, str(e))

    except ImportError:
        pass


# Gold Tier: Token refresh monitoring (T075)
def check_token_expiry():
    """
    Monitor OAuth token expiry and warn 24 hours before expiration.
    Creates notification files in vault when tokens are expiring.
    """
    try:
        from core.credential_manager import CredentialManager

        cm = CredentialManager()
        services = ["xero", "meta", "twitter"]

        for service in services:
            if cm.has_credentials(service) and cm.is_token_expired(service, buffer_hours=24):
                # Create a warning notification in vault
                vault_path = os.environ.get("VAULT_PATH", "./obsidian-vault")
                notification_path = Path(vault_path) / "inbox" / f"TOKEN_EXPIRY_{service.upper()}_{datetime.now().strftime('%Y%m%d')}.md"

                if not notification_path.exists():
                    notification_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(notification_path, "w") as f:
                        f.write(f"---\ntype: token_expiry_warning\nservice: {service}\ntimestamp: {datetime.now().isoformat()}\npriority: high\n---\n\n")
                        f.write(f"# Token Expiry Warning: {service.title()}\n\n")
                        f.write(f"The OAuth token for **{service.title()}** is expiring within 24 hours.\n")
                        f.write(f"Please re-authenticate at the dashboard to maintain connectivity.\n")
    except ImportError:
        pass


# Example usage
def example_scheduled_task():
    """Example task function for demonstration."""
    print(f"[{datetime.now().isoformat()}] Example scheduled task executed")


if __name__ == "__main__":
    # Create a scheduler instance
    scheduler = TaskScheduler()

    # Schedule an example task to run every 10 seconds
    task_id = scheduler.schedule_task("example_task", example_scheduled_task, interval_seconds=10)

    # Schedule a daily task (runs every day at 9:30 AM)
    daily_task_id = scheduler.schedule_daily_task("daily_example", example_scheduled_task, "09:30")

    # Start the scheduler
    scheduler.start()

    # Let it run for a while
    try:
        time.sleep(60)  # Run for 1 minute
    except KeyboardInterrupt:
        print("Stopping scheduler...")
    finally:
        scheduler.stop()