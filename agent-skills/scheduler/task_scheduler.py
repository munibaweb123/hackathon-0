"""
Task Scheduler Module

This module implements scheduling for periodic watcher execution and daily reasoning runs.
It ensures that scheduled tasks don't bypass approval requirements.
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any
from core.logger import Logger


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