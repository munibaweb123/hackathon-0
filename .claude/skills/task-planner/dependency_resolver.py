"""
Dependency Resolver — topological sort and dependency validation for task plans.

Validates task dependency graphs, detects cycles, identifies parallel groups,
and computes the critical path for time estimation.
"""

from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple


class DependencyResolver:
    """
    Resolves task dependencies using Kahn's algorithm (topological sort).

    Supports:
    - Cycle detection
    - Missing dependency detection
    - Self-reference detection
    - Parallel group identification (tasks at the same topological level)
    - Critical path computation
    """

    def __init__(self) -> None:
        self._graph: Dict[str, Set[str]] = {}  # task_id -> set of dependencies
        self._reverse: Dict[str, Set[str]] = defaultdict(set)  # task_id -> dependents

    def add_task(self, task_id: str, depends_on: Optional[List[str]] = None) -> None:
        """Register a task with its dependencies."""
        deps = set(depends_on) if depends_on else set()
        self._graph[task_id] = deps
        for dep in deps:
            self._reverse[dep].add(task_id)
        # Ensure all dependency targets exist in graph (as leaves if not added)
        for dep in deps:
            if dep not in self._graph:
                self._graph[dep] = set()

    def validate(self) -> Dict[str, Any]:
        """
        Validate the dependency graph.

        Returns:
            {valid: bool, errors: [str]}
        """
        errors = []

        # Check self-references
        for task_id, deps in self._graph.items():
            if task_id in deps:
                errors.append(f"Self-reference: {task_id} depends on itself")

        # Check missing dependencies
        all_tasks = set(self._graph.keys())
        for task_id, deps in self._graph.items():
            for dep in deps:
                if dep not in all_tasks:
                    errors.append(
                        f"Missing dependency: {task_id} depends on {dep} "
                        f"which is not defined"
                    )

        # Check for cycles using DFS
        cycle = self._detect_cycle()
        if cycle:
            errors.append(f"Dependency cycle detected: {' -> '.join(cycle)}")

        return {"valid": len(errors) == 0, "errors": errors}

    def resolve(self) -> List[str]:
        """
        Return tasks in dependency order (topological sort via Kahn's algorithm).

        Returns:
            Ordered list of task IDs.

        Raises:
            ValueError: If the graph contains cycles.
        """
        validation = self.validate()
        if not validation["valid"]:
            raise ValueError(
                f"Cannot resolve: {'; '.join(validation['errors'])}"
            )

        # Compute in-degrees
        in_degree: Dict[str, int] = {t: 0 for t in self._graph}
        for task_id, deps in self._graph.items():
            for dep in deps:
                # dep -> task_id edge means task_id has an incoming edge
                pass
            in_degree[task_id] = len(deps)

        # Start with zero in-degree nodes
        queue = deque(
            sorted(t for t, d in in_degree.items() if d == 0)
        )
        result = []

        while queue:
            task_id = queue.popleft()
            result.append(task_id)

            # Reduce in-degree for dependents
            for dependent in sorted(self._reverse.get(task_id, set())):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self._graph):
            raise ValueError("Cycle detected — not all tasks could be resolved")

        return result

    def get_parallel_groups(self) -> List[List[str]]:
        """
        Group tasks by topological level (tasks at the same level can run in parallel).

        Returns:
            List of groups, each group is a list of task IDs that can execute concurrently.
        """
        validation = self.validate()
        if not validation["valid"]:
            return []

        # Compute in-degrees
        in_degree: Dict[str, int] = {
            t: len(deps) for t, deps in self._graph.items()
        }

        current_level = sorted(
            t for t, d in in_degree.items() if d == 0
        )
        groups = []

        while current_level:
            groups.append(current_level)
            next_level_set: Set[str] = set()

            for task_id in current_level:
                for dependent in self._reverse.get(task_id, set()):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_level_set.add(dependent)

            current_level = sorted(next_level_set)

        return groups

    def get_critical_path(
        self, time_estimates: Dict[str, float]
    ) -> Tuple[List[str], float]:
        """
        Find the critical path (longest dependency chain by cumulative time).

        Args:
            time_estimates: {task_id: hours}

        Returns:
            (path_as_task_ids, total_hours)
        """
        order = self.resolve()

        # Earliest finish time and predecessor tracking
        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}

        for task_id in order:
            task_time = time_estimates.get(task_id, 0.0)
            deps = self._graph.get(task_id, set())

            if not deps:
                earliest[task_id] = task_time
                predecessor[task_id] = None
            else:
                # Find the dependency with the latest finish time
                best_dep = max(deps, key=lambda d: earliest.get(d, 0.0))
                earliest[task_id] = earliest.get(best_dep, 0.0) + task_time
                predecessor[task_id] = best_dep

        if not earliest:
            return [], 0.0

        # Trace back from the task with the latest finish time
        end_task = max(earliest, key=lambda t: earliest[t])
        total_time = earliest[end_task]

        path = []
        current: Optional[str] = end_task
        while current is not None:
            path.append(current)
            current = predecessor[current]

        path.reverse()
        return path, total_time

    def _detect_cycle(self) -> Optional[List[str]]:
        """Detect cycles using DFS. Returns cycle path or None."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {t: WHITE for t in self._graph}
        parent: Dict[str, Optional[str]] = {t: None for t in self._graph}

        def dfs(node: str) -> Optional[List[str]]:
            color[node] = GRAY
            for dep in self._graph.get(node, set()):
                if dep not in color:
                    continue
                if color[dep] == GRAY:
                    # Found cycle — trace back
                    cycle = [dep, node]
                    return cycle
                if color[dep] == WHITE:
                    parent[dep] = node
                    result = dfs(dep)
                    if result:
                        return result
            color[node] = BLACK
            return None

        for task_id in self._graph:
            if color[task_id] == WHITE:
                result = dfs(task_id)
                if result:
                    return result

        return None

    def reset(self) -> None:
        """Clear all tasks and dependencies."""
        self._graph.clear()
        self._reverse.clear()
