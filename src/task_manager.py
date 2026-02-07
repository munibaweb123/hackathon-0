"""Task management system."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from .entities import OperationEntity
from .vault_manager import VaultManager
from .logger import Logger


class TaskList:
    """Represents a task list with items and metadata."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.tasks: List[Dict] = []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def add_task(self, task_name: str, description: str = "", priority: str = "normal"):
        """Add a task to the list."""
        task = {
            "id": f"{self.name}_{len(self.tasks) + 1}",
            "name": task_name,
            "description": description,
            "priority": priority,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        self.tasks.append(task)
        self.updated_at = datetime.now()

    def update_task_status(self, task_id: str, status: str):
        """Update the status of a task."""
        for task in self.tasks:
            if task["id"] == task_id:
                task["status"] = status
                task["updated_at"] = datetime.now().isoformat()
                self.updated_at = datetime.now()
                break

    def get_tasks_by_status(self, status: str) -> List[Dict]:
        """Get all tasks with a specific status."""
        return [task for task in self.tasks if task["status"] == status]

    def get_tasks_by_priority(self, priority: str) -> List[Dict]:
        """Get all tasks with a specific priority."""
        return [task for task in self.tasks if task["priority"] == priority]

    def to_dict(self):
        """Convert the task list to a dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tasks": self.tasks
        }

    @classmethod
    def from_dict(cls, data: Dict):
        """Create a TaskList from a dictionary."""
        task_list = cls(data["name"], data.get("description", ""))
        task_list.created_at = datetime.fromisoformat(data["created_at"])
        task_list.updated_at = datetime.fromisoformat(data["updated_at"])
        task_list.tasks = data["tasks"]
        return task_list


class TaskManager:
    """Manages task lists and workflow states."""

    def __init__(self, vault_manager: VaultManager, logger: Logger):
        self.vault_manager = vault_manager
        self.logger = logger
        self.task_lists: Dict[str, TaskList] = {}

    def create_task_list(self, name: str, description: str = "") -> TaskList:
        """Create a new task list."""
        if name in self.task_lists:
            self.logger.warn("task_manager", "task_list_exists",
                            f"Task list {name} already exists, overwriting")

        task_list = TaskList(name, description)
        self.task_lists[name] = task_list

        self.logger.info("task_manager", "task_list_created",
                        f"Created task list: {name}")

        return task_list

    def get_task_list(self, name: str) -> Optional[TaskList]:
        """Get a task list by name."""
        return self.task_lists.get(name)

    def add_task_to_list(self, list_name: str, task_name: str, description: str = "", priority: str = "normal"):
        """Add a task to a specific list."""
        task_list = self.task_lists.get(list_name)
        if not task_list:
            self.logger.error("task_manager", "task_list_not_found",
                             f"Task list {list_name} not found")
            return False

        task_list.add_task(task_name, description, priority)
        self.logger.info("task_manager", "task_added",
                        f"Added task '{task_name}' to list '{list_name}'")

        return True

    def update_task_status(self, list_name: str, task_id: str, status: str):
        """Update the status of a task in a specific list."""
        task_list = self.task_lists.get(list_name)
        if not task_list:
            self.logger.error("task_manager", "task_list_not_found",
                             f"Task list {list_name} not found")
            return False

        task_list.update_task_status(task_id, status)
        self.logger.info("task_manager", "task_status_updated",
                        f"Updated task '{task_id}' status to '{status}' in list '{list_name}'")

        return True

    def save_task_list(self, list_name: str) -> bool:
        """Save a task list to a file in the vault."""
        task_list = self.task_lists.get(list_name)
        if not task_list:
            self.logger.error("task_manager", "task_list_not_found",
                             f"Task list {list_name} not found")
            return False

        # Convert to dict and save as JSON
        task_list_data = task_list.to_dict()

        # Create filename based on list name
        filename = f"task_list_{list_name.replace(' ', '_').lower()}.json"

        # Save to the processing folder
        result = self.vault_manager.create_file(
            "processing",
            filename,
            json.dumps(task_list_data, indent=2)
        )

        if result:
            self.logger.audit("task_manager", "task_list_saved",
                             f"Saved task list '{list_name}' to {result.name}",
                             file_ref=str(result))
            return True
        else:
            self.logger.error("task_manager", "task_list_save_failed",
                             f"Failed to save task list '{list_name}'")
            return False

    def load_task_list(self, file_path: Path) -> bool:
        """Load a task list from a file in the vault."""
        try:
            # Read the file content
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Create task list from data
            task_list = TaskList.from_dict(data)
            self.task_lists[task_list.name] = task_list

            self.logger.audit("task_manager", "task_list_loaded",
                             f"Loaded task list '{task_list.name}' from {file_path.name}",
                             file_ref=str(file_path))

            return True

        except Exception as e:
            self.logger.error("task_manager", "task_list_load_failed",
                             f"Failed to load task list from {file_path.name}: {str(e)}")
            return False

    def get_progress_report(self, list_name: str) -> Dict[str, int]:
        """Get a progress report for a task list."""
        task_list = self.task_lists.get(list_name)
        if not task_list:
            return {}

        # Count tasks by status
        status_counts = {}
        for task in task_list.tasks:
            status = task["status"]
            status_counts[status] = status_counts.get(status, 0) + 1

        return status_counts