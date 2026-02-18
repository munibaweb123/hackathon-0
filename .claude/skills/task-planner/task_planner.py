# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "jinja2>=3.1.0",
#     "python-dotenv>=1.0.0",
#     "pyyaml>=6.0",
# ]
# ///
"""
Task Planner — decomposes complex requests into actionable sub-tasks
with dependencies, time estimates, and HITL approval checkpoints.

Generates TASKPLAN_*.md files in the Obsidian vault plans/ folder.

Usage with UV (recommended):
    uv run task_planner.py --vault-path ../../obsidian-vault \\
        --plan "Build landing page with contact form, deploy to production"

    uv run task_planner.py --vault-path ../../obsidian-vault --detect
    uv run task_planner.py --vault-path ../../obsidian-vault --progress <PLAN_ID>
"""

import argparse
import json
import logging
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Local imports — add skill directory to path
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dependency_resolver import DependencyResolver

# ---------------------------------------------------------------------------
# Jinja2 (lazy import for UV auto-install)
# ---------------------------------------------------------------------------
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger("task-planner")

# ---------------------------------------------------------------------------
# Action verb categories for heuristic decomposition
# ---------------------------------------------------------------------------
PHASE_KEYWORDS = {
    "setup": [
        "install", "setup", "configure", "initialize", "provision",
        "create repo", "scaffold", "bootstrap", "prepare",
    ],
    "core": [
        "build", "create", "implement", "develop", "code", "write",
        "design", "add", "integrate", "connect", "wire",
    ],
    "test": [
        "test", "verify", "validate", "check", "review", "audit",
        "inspect", "qa", "quality",
    ],
    "deploy": [
        "deploy", "release", "publish", "launch", "ship", "push",
        "migrate", "rollout",
    ],
    "communicate": [
        "send", "email", "notify", "announce", "post", "share",
        "message", "broadcast", "report",
    ],
}

RISK_HIGH_KEYWORDS = [
    "deploy", "production", "payment", "delete", "remove", "drop",
    "send", "email", "publish", "post", "announce", "transfer",
    "migrate", "rollback",
]

RISK_LOW_KEYWORDS = [
    "read", "review", "check", "test", "document", "list", "view",
    "inspect", "verify", "plan", "draft",
]

TIME_ESTIMATES = {
    "setup": 0.5,
    "configure": 0.5,
    "install": 0.25,
    "create": 1.5,
    "build": 2.0,
    "implement": 2.0,
    "develop": 2.0,
    "design": 1.5,
    "integrate": 1.0,
    "test": 0.75,
    "verify": 0.5,
    "review": 1.0,
    "deploy": 0.5,
    "publish": 0.5,
    "send": 0.25,
    "email": 0.25,
    "notify": 0.25,
    "document": 0.75,
    "migrate": 1.5,
}

PHASE_ORDER = ["setup", "core", "test", "deploy", "communicate"]
PHASE_ICONS = {
    "setup": "1.",
    "core": "2.",
    "test": "3.",
    "deploy": "4.",
    "communicate": "5.",
}
PHASE_DISPLAY = {
    "setup": "Setup & Configuration",
    "core": "Core Implementation",
    "test": "Testing & Verification",
    "deploy": "Deployment & Release",
    "communicate": "Communication & Notification",
}


class TaskPlanner:
    """
    Decomposes complex requests into structured, dependency-ordered task plans.
    """

    def __init__(self, vault_path: str) -> None:
        self.vault = Path(vault_path).resolve()
        self.resolver = DependencyResolver()

        # Jinja2 environment
        template_dir = Path(__file__).resolve().parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Ensure vault directories exist
        (self.vault / "plans").mkdir(parents=True, exist_ok=True)
        (self.vault / "Logs").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Main entry: decompose request into task plan
    # ------------------------------------------------------------------
    def plan(
        self,
        request: str,
        objective: Optional[str] = None,
        source: str = "cli",
    ) -> Dict[str, Any]:
        """
        Decompose a request into a structured task plan.

        Args:
            request: The complex request text to decompose.
            objective: Optional explicit objective (derived from request if omitted).
            source: Where the request originated (cli, needs_action, api).

        Returns:
            Dict with plan metadata including plan_id, file_path, total_tasks.
        """
        plan_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)

        # Step 1: Decompose
        tasks = self._decompose_request(request)
        if not tasks:
            logger.warning("No actionable tasks extracted from request")
            return {"error": "No actionable tasks found in request"}

        # Step 2: Build dependency graph
        self.resolver.reset()
        for task in tasks:
            self.resolver.add_task(task["id"], task.get("depends_on", []))

        validation = self.resolver.validate()
        if not validation["valid"]:
            logger.error(f"Dependency errors: {validation['errors']}")
            return {"error": f"Dependency issues: {validation['errors']}"}

        # Step 3: Resolve order + parallel groups
        ordered_ids = self.resolver.resolve()
        parallel_groups = self.resolver.get_parallel_groups()

        # Step 4: Time estimates + critical path
        time_map = {t["id"]: t["estimate"] for t in tasks}
        critical_path, critical_hours = self.resolver.get_critical_path(time_map)
        total_hours = sum(t["estimate"] for t in tasks)

        # Step 5: Identify approval checkpoints
        approval_checkpoints = [
            {
                "task_id": t["id"],
                "description": t["description"],
                "reason": self._approval_reason(t["description"]),
            }
            for t in tasks
            if t.get("requires_approval")
        ]

        # Step 6: Group tasks by phase for template
        task_lookup = {t["id"]: t for t in tasks}
        phases = self._group_by_phase(tasks, ordered_ids)

        # Step 7: Render
        obj = objective or self._derive_objective(request)
        dep_graph = self._render_dependency_graph(tasks, parallel_groups)
        timeline = self._render_timeline(tasks, parallel_groups)

        template = self.jinja_env.get_template("plan_template.md")
        rendered = template.render(
            plan_id=plan_id,
            title=self._derive_title(request),
            status="draft",
            created_at=now.strftime("%Y-%m-%d %H:%M UTC"),
            source=source,
            total_tasks=len(tasks),
            completed_tasks=0,
            total_hours=f"{total_hours:.1f}",
            critical_path_hours=f"{critical_hours:.1f}",
            has_approval_tasks=len(approval_checkpoints) > 0,
            progress_pct=0,
            objective=obj,
            phases=phases,
            dependency_graph=dep_graph,
            timeline=timeline,
            approval_checkpoints=approval_checkpoints,
        )

        # Step 8: Write to vault
        filename = f"TASKPLAN_{now.strftime('%Y-%m-%d')}_{plan_id}.md"
        output_path = self.vault / "plans" / filename
        output_path.write_text(rendered, encoding="utf-8")
        logger.info(f"Task plan written: {output_path}")

        # Step 9: Create approval file if needed
        if approval_checkpoints:
            self._create_approval_request(plan_id, obj, approval_checkpoints, now)

        # Step 10: Log event
        self._log_event({
            "event": "plan_created",
            "plan_id": plan_id,
            "title": self._derive_title(request),
            "total_tasks": len(tasks),
            "total_hours": total_hours,
            "critical_path_hours": critical_hours,
            "approval_tasks": len(approval_checkpoints),
            "source": source,
            "timestamp": now.isoformat(),
            "file_path": str(output_path),
        })

        result = {
            "plan_id": plan_id,
            "file_path": str(output_path),
            "filename": filename,
            "total_tasks": len(tasks),
            "total_hours": total_hours,
            "critical_path_hours": critical_hours,
            "approval_checkpoints": len(approval_checkpoints),
            "phases": len(phases),
        }

        print(f"\nTask plan created: {filename}")
        print(f"  Tasks: {len(tasks)} | Hours: ~{total_hours:.1f}h | Critical path: ~{critical_hours:.1f}h")
        if approval_checkpoints:
            print(f"  Approval required for {len(approval_checkpoints)} task(s)")
        print(f"  Output: {output_path}")

        return result

    # ------------------------------------------------------------------
    # Detect requests from Needs_Action/
    # ------------------------------------------------------------------
    def detect_requests(self) -> List[Dict[str, Any]]:
        """Scan Needs_Action/ for plannable requests."""
        needs_dir = self.vault / "Needs_Action"
        if not needs_dir.exists():
            logger.info("No Needs_Action/ directory found")
            return []

        patterns = ["*task*", "*plan*", "*project*", "*request*", "*TODO*"]
        found = []

        for pattern in patterns:
            for f in needs_dir.glob(pattern):
                if not f.is_file() or not f.suffix == ".md":
                    continue
                content = f.read_text(encoding="utf-8")
                found.append({
                    "file": str(f),
                    "name": f.stem,
                    "content": content[:500],
                })

        if found:
            print(f"\nFound {len(found)} plannable request(s) in Needs_Action/:")
            for item in found:
                print(f"  - {item['name']}")
        else:
            print("\nNo plannable requests found in Needs_Action/")

        return found

    # ------------------------------------------------------------------
    # Progress tracking
    # ------------------------------------------------------------------
    def check_progress(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Check completion progress for a plan."""
        plan_file = self._find_plan_file(plan_id)
        if not plan_file:
            print(f"Plan {plan_id} not found")
            return None

        content = plan_file.read_text(encoding="utf-8")

        total = content.count("- [ ]") + content.count("- [x]")
        done = content.count("- [x]")
        pct = round(done / total * 100) if total > 0 else 0

        # Extract title from frontmatter
        title_match = re.search(r'^title:\s*"?(.+?)"?\s*$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else plan_id

        result = {
            "plan_id": plan_id,
            "title": title,
            "total_tasks": total,
            "completed": done,
            "remaining": total - done,
            "progress_pct": pct,
            "status": "completed" if pct == 100 else "in_progress" if done > 0 else "not_started",
        }

        print(f"\nProgress for {title}:")
        print(f"  [{self._progress_bar(pct)}] {pct}%")
        print(f"  {done}/{total} tasks completed, {total - done} remaining")

        return result

    def update_progress(
        self, plan_id: str, task_id: str, done: bool = True
    ) -> bool:
        """Mark a task as done or undone in a plan."""
        plan_file = self._find_plan_file(plan_id)
        if not plan_file:
            print(f"Plan {plan_id} not found")
            return False

        content = plan_file.read_text(encoding="utf-8")

        if done:
            pattern = rf"- \[ \] \*\*{re.escape(task_id)}\*\*"
            replacement = f"- [x] **{task_id}**"
        else:
            pattern = rf"- \[x\] \*\*{re.escape(task_id)}\*\*"
            replacement = f"- [ ] **{task_id}**"

        new_content, count = re.subn(pattern, replacement, content)
        if count == 0:
            print(f"Task {task_id} not found in plan {plan_id}")
            return False

        # Update progress stats in frontmatter
        total = new_content.count("- [ ]") + new_content.count("- [x]")
        completed = new_content.count("- [x]")
        pct = round(completed / total * 100) if total > 0 else 0

        new_content = re.sub(
            r"^completed_tasks:\s*\d+",
            f"completed_tasks: {completed}",
            new_content,
            flags=re.MULTILINE,
        )
        new_content = re.sub(
            r"^progress_pct:\s*\d+",
            f"progress_pct: {pct}",
            new_content,
            flags=re.MULTILINE,
        )

        # Update status
        status = "completed" if pct == 100 else "in_progress"
        new_content = re.sub(
            r"^status:\s*\w+",
            f"status: {status}",
            new_content,
            flags=re.MULTILINE,
        )

        plan_file.write_text(new_content, encoding="utf-8")

        action = "completed" if done else "unmarked"
        print(f"Task {task_id} {action} in plan {plan_id} ({pct}% complete)")

        self._log_event({
            "event": "task_updated",
            "plan_id": plan_id,
            "task_id": task_id,
            "done": done,
            "progress_pct": pct,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return True

    # ------------------------------------------------------------------
    # Archive
    # ------------------------------------------------------------------
    def archive(self, plan_id: str) -> bool:
        """Move a completed plan to Done/."""
        plan_file = self._find_plan_file(plan_id)
        if not plan_file:
            print(f"Plan {plan_id} not found")
            return False

        done_dir = self.vault / "Done"
        done_dir.mkdir(parents=True, exist_ok=True)

        dest = done_dir / plan_file.name
        plan_file.rename(dest)

        print(f"Plan {plan_id} archived to Done/{plan_file.name}")

        self._log_event({
            "event": "plan_archived",
            "plan_id": plan_id,
            "file_path": str(dest),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return True

    # ------------------------------------------------------------------
    # Task decomposition heuristics
    # ------------------------------------------------------------------
    def _decompose_request(self, request: str) -> List[Dict[str, Any]]:
        """
        Heuristic decomposition of a request into tasks.

        Splits on sentence boundaries, commas, and conjunctions (and/then/after).
        Classifies each fragment into a phase and assigns metadata.
        """
        # Normalize and split into action fragments
        fragments = self._split_into_fragments(request)
        if not fragments:
            # Fall back: treat the whole request as one task
            fragments = [request.strip()]

        tasks = []
        task_counter = 1
        phase_counters: Dict[str, int] = {}

        for frag in fragments:
            frag = frag.strip()
            if len(frag) < 3:
                continue

            phase = self._classify_phase(frag)
            phase_counters[phase] = phase_counters.get(phase, 0) + 1

            task_id = f"T{task_counter:03d}"
            risk = self._assess_risk(frag)
            estimate = self._estimate_time(frag)
            requires_approval = risk == "high"

            tasks.append({
                "id": task_id,
                "description": self._clean_description(frag),
                "phase": phase,
                "phase_order": PHASE_ORDER.index(phase) if phase in PHASE_ORDER else 99,
                "depends_on": [],
                "estimate": estimate,
                "risk": risk,
                "risk_emoji": {"low": "G", "medium": "Y", "high": "R"}.get(risk, "Y"),
                "requires_approval": requires_approval,
                "done": False,
            })
            task_counter += 1

        # Sort by phase order
        tasks.sort(key=lambda t: t["phase_order"])

        # Auto-assign dependencies: each task depends on previous tasks in earlier phases
        self._assign_dependencies(tasks)

        return tasks

    def _split_into_fragments(self, text: str) -> List[str]:
        """Split request text into action fragments."""
        # Split on common delimiters
        # 1. Split on sentence boundaries
        text = text.strip()

        # Handle numbered/bulleted lists
        list_items = re.findall(r"(?:^|\n)\s*(?:\d+[.)]\s*|-\s*|\*\s*)(.*)", text)
        if len(list_items) >= 2:
            return [item.strip() for item in list_items if item.strip()]

        # Split on ", and ", ", then ", "; "
        parts = re.split(
            r"[,;]\s*(?:and\s+|then\s+|after\s+that\s+|finally\s+|also\s+)?|"
            r"\.\s+(?:Then\s+|After\s+that\s*,?\s*|Also\s+|Finally\s+)?|"
            r"\s+(?:and\s+then\s+|then\s+)",
            text,
        )

        # Filter out tiny fragments
        return [p.strip().rstrip(".") for p in parts if len(p.strip()) > 5]

    def _classify_phase(self, description: str) -> str:
        """Classify a task description into a phase."""
        desc_lower = description.lower()

        for phase, keywords in PHASE_KEYWORDS.items():
            for kw in keywords:
                if kw in desc_lower:
                    return phase

        # Default to core
        return "core"

    def _assess_risk(self, description: str) -> str:
        """Assess risk level from task description."""
        desc_lower = description.lower()

        for kw in RISK_HIGH_KEYWORDS:
            if kw in desc_lower:
                return "high"

        for kw in RISK_LOW_KEYWORDS:
            if kw in desc_lower:
                return "low"

        return "medium"

    def _estimate_time(self, description: str) -> float:
        """Estimate hours from task description keywords."""
        desc_lower = description.lower()
        best_estimate = 1.0  # default

        for keyword, hours in TIME_ESTIMATES.items():
            if keyword in desc_lower:
                best_estimate = hours
                break

        return best_estimate

    def _assign_dependencies(self, tasks: List[Dict[str, Any]]) -> None:
        """Auto-assign dependencies based on phase ordering."""
        phase_last_task: Dict[str, str] = {}

        for i, task in enumerate(tasks):
            phase = task["phase"]
            phase_idx = task["phase_order"]

            # Find the last task of the previous phase
            for prev_phase in PHASE_ORDER:
                if PHASE_ORDER.index(prev_phase) >= phase_idx:
                    break
                if prev_phase in phase_last_task:
                    dep = phase_last_task[prev_phase]
                    # Only depend on the last task of the immediately prior phase
                    # (not all prior phases) to allow parallelism within phases
                    task["depends_on"] = [dep]

            phase_last_task[phase] = task["id"]

    def _clean_description(self, text: str) -> str:
        """Clean up a fragment into a proper task description."""
        text = text.strip()
        # Capitalize first letter
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        # Remove trailing punctuation
        text = text.rstrip(".,;:")
        return text

    def _derive_title(self, request: str) -> str:
        """Derive a short title from the request."""
        # Take first ~60 chars, break at word boundary
        title = request.strip().split("\n")[0][:60]
        if len(request.strip().split("\n")[0]) > 60:
            title = title.rsplit(" ", 1)[0] + "..."
        return title

    def _derive_objective(self, request: str) -> str:
        """Derive an objective from the request text."""
        return request.strip()

    def _approval_reason(self, description: str) -> str:
        """Generate reason why a task requires approval."""
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in ["deploy", "production", "release"]):
            return "Production deployment requires verification"
        if any(kw in desc_lower for kw in ["send", "email", "notify", "announce"]):
            return "External communication requires review"
        if any(kw in desc_lower for kw in ["payment", "transfer", "invoice"]):
            return "Financial action requires authorization"
        if any(kw in desc_lower for kw in ["delete", "remove", "drop"]):
            return "Destructive action requires confirmation"
        if any(kw in desc_lower for kw in ["publish", "post"]):
            return "Public-facing content requires review"
        return "High-risk action requires human approval"

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _group_by_phase(
        self, tasks: List[Dict[str, Any]], ordered_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Group tasks by phase for template rendering."""
        phase_map: Dict[str, List[Dict[str, Any]]] = {}
        id_set = set(ordered_ids)

        for task in tasks:
            if task["id"] not in id_set:
                continue
            phase = task["phase"]
            if phase not in phase_map:
                phase_map[phase] = []
            phase_map[phase].append(task)

        phases = []
        phase_num = 1
        for phase_key in PHASE_ORDER:
            if phase_key in phase_map:
                phases.append({
                    "number": phase_num,
                    "name": PHASE_DISPLAY.get(phase_key, phase_key.title()),
                    "icon": PHASE_ICONS.get(phase_key, f"{phase_num}."),
                    "steps": phase_map[phase_key],
                })
                phase_num += 1

        return phases

    def _render_dependency_graph(
        self,
        tasks: List[Dict[str, Any]],
        parallel_groups: List[List[str]],
    ) -> str:
        """Render an ASCII dependency graph."""
        lines = []
        task_lookup = {t["id"]: t for t in tasks}

        for level, group in enumerate(parallel_groups):
            if level > 0:
                # Draw arrows from previous level
                prev_group = parallel_groups[level - 1]
                mid = len(prev_group) // 2
                for i, tid in enumerate(prev_group):
                    prefix = "    " * i
                    if i == mid:
                        lines.append(f"{'    ' * mid}    |")
                        lines.append(f"{'    ' * mid}    v")

            # Draw tasks at this level
            group_str = "  |  ".join(
                f"[{tid}]" for tid in group
            )
            lines.append(f"  {group_str}")

        return "\n".join(lines) if lines else "(no dependencies)"

    def _render_timeline(
        self,
        tasks: List[Dict[str, Any]],
        parallel_groups: List[List[str]],
    ) -> str:
        """Render a Gantt-like ASCII timeline."""
        task_lookup = {t["id"]: t for t in tasks}
        lines = []
        cumulative = 0.0

        # Header
        lines.append(f"{'Task':<8} {'Phase':<14} {'Est':>5}  Timeline")
        lines.append(f"{'─' * 8} {'─' * 14} {'─' * 5}  {'─' * 30}")

        for group in parallel_groups:
            max_time = 0.0
            for tid in group:
                task = task_lookup.get(tid)
                if not task:
                    continue
                est = task["estimate"]
                max_time = max(max_time, est)
                bar_len = max(1, int(est * 4))
                offset = int(cumulative * 4)
                phase_short = task["phase"][:12]
                bar = " " * offset + "=" * bar_len
                risk_char = {"high": "!", "medium": "*", "low": " "}.get(
                    task["risk"], " "
                )
                lines.append(
                    f"{tid:<8} {phase_short:<14} {est:>4.1f}h  |{bar}{risk_char}"
                )
            cumulative += max_time

        lines.append(f"\nTotal estimated: ~{cumulative:.1f}h (critical path)")
        return "\n".join(lines)

    def _progress_bar(self, pct: int, width: int = 20) -> str:
        """Render a text progress bar."""
        filled = int(width * pct / 100)
        return "=" * filled + "-" * (width - filled)

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------
    def _find_plan_file(self, plan_id: str) -> Optional[Path]:
        """Find a plan file by plan ID."""
        plans_dir = self.vault / "plans"
        if not plans_dir.exists():
            return None

        for f in plans_dir.glob(f"TASKPLAN_*_{plan_id}*.md"):
            return f

        # Also try Done/
        done_dir = self.vault / "Done"
        if done_dir.exists():
            for f in done_dir.glob(f"TASKPLAN_*_{plan_id}*.md"):
                return f

        return None

    def _create_approval_request(
        self,
        plan_id: str,
        objective: str,
        checkpoints: List[Dict[str, Any]],
        now: datetime,
    ) -> None:
        """Create HITL approval file for high-risk tasks."""
        approval_dir = self.vault / "pending-approval"
        approval_dir.mkdir(parents=True, exist_ok=True)

        task_list = "\n".join(
            f"- **{cp['task_id']}**: {cp['description']}\n  Reason: {cp['reason']}"
            for cp in checkpoints
        )

        content = f"""---
type: task_plan_approval
plan_id: "{plan_id}"
created_at: {now.isoformat()}
expires_at: {now.strftime('%Y-%m-%dT23:59:59Z')}
status: pending
---

# Approval Required: Task Plan {plan_id}

## Objective

{objective}

## Tasks Requiring Approval

{task_list}

## Instructions

To approve: move this file to `Approved/`
To reject: move this file to `Rejected/`

---
_Generated by Task Planner at {now.strftime('%Y-%m-%d %H:%M UTC')}_
"""

        filename = f"APPROVAL_REQUIRED_taskplan_{plan_id}.md"
        (approval_dir / filename).write_text(content, encoding="utf-8")
        logger.info(f"Approval request created: {filename}")

    def _log_event(self, event: Dict[str, Any]) -> None:
        """Append event to Logs/task_plans.json."""
        log_file = self.vault / "Logs" / "task_plans.json"
        events = []
        if log_file.exists():
            try:
                events = json.loads(log_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                events = []

        events.append(event)
        log_file.write_text(
            json.dumps(events, indent=2, default=str), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Task Planner — decomposes requests into actionable task plans"
    )
    parser.add_argument(
        "--vault-path",
        default="./obsidian-vault",
        help="Path to the Obsidian vault (default: ./obsidian-vault)",
    )
    parser.add_argument(
        "--plan",
        type=str,
        help="Request text to decompose into a task plan",
    )
    parser.add_argument(
        "--plan-file",
        type=str,
        help="Path to a file containing the request text",
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Scan Needs_Action/ for plannable requests",
    )
    parser.add_argument(
        "--progress",
        type=str,
        metavar="PLAN_ID",
        help="Check progress for a plan",
    )
    parser.add_argument(
        "--update",
        nargs=2,
        metavar=("PLAN_ID", "TASK_ID"),
        help="Mark a task as done",
    )
    parser.add_argument(
        "--archive",
        type=str,
        metavar="PLAN_ID",
        help="Archive a completed plan to Done/",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    planner = TaskPlanner(args.vault_path)

    if args.plan:
        planner.plan(args.plan)
    elif args.plan_file:
        file_path = Path(args.plan_file)
        if not file_path.exists():
            print(f"Error: file not found: {args.plan_file}")
            sys.exit(1)
        request_text = file_path.read_text(encoding="utf-8")
        planner.plan(request_text, source=f"file:{file_path.name}")
    elif args.detect:
        planner.detect_requests()
    elif args.progress:
        planner.check_progress(args.progress)
    elif args.update:
        plan_id, task_id = args.update
        planner.update_progress(plan_id, task_id)
    elif args.archive:
        planner.archive(args.archive)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
