"""Tasks, the data dependencies between them, and the levels a scheduler can run side by side.

A task's dependencies are not written by hand: they are read from the references (Ref) inside its inputs, because a
task depends on another exactly when it needs a value that task produces. Everything here is plain data and pure
functions, so the analysis can be tested without a clock or an event loop.
"""
from dataclasses import dataclass, field
from typing import Any, Literal


class GraphError(ValueError):
    """The task list cannot be scheduled: a duplicate id, a reference to nothing, or a cycle."""


@dataclass(frozen=True)
class Ref:
    """The value ``key`` of the result that task ``task`` produces."""
    task: str
    key: str


@dataclass(frozen=True)
class Task:
    id: str
    kind: Literal["tool", "model"]
    name: str
    inputs: dict[str, Any]
    timeout_s: float
    # "all": run only when every dependency finished well. "settled": run once every dependency has ended,
    # whatever way, and be told what is missing (the task must then mark its own output as partial).
    join: Literal["all", "settled"] = "all"
    needs: tuple[str, ...] = field(default=(), init=False)

    def __post_init__(self):
        found = dict.fromkeys(ref.task for ref in refs_in(self.inputs))
        object.__setattr__(self, "needs", tuple(found))


def refs_in(value) -> list[Ref]:
    """Every Ref inside a nested input, in reading order."""
    if isinstance(value, Ref):
        return [value]
    if isinstance(value, dict):
        return [ref for item in value.values() for ref in refs_in(item)]
    if isinstance(value, (list, tuple)):
        return [ref for item in value for ref in refs_in(item)]
    return []


def resolve(value, results: dict[str, dict]):
    """Replace each Ref by the value it points at; a result that does not exist (yet) becomes None."""
    if isinstance(value, Ref):
        produced = results.get(value.task)
        return produced.get(value.key) if produced is not None else None
    if isinstance(value, dict):
        return {key: resolve(item, results) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [resolve(item, results) for item in value]
    return value


def levels(tasks: list[Task]) -> dict[str, int]:
    """Level 1 holds tasks that need nothing; every other task sits one level below its deepest dependency.

    Tasks on one level never depend on each other, so they are the ones that may run side by side.
    """
    by_id = {task.id: task for task in tasks}
    if len(by_id) != len(tasks):
        raise GraphError("task ids must be unique")
    for task in tasks:
        unknown = [need for need in task.needs if need not in by_id]
        if unknown:
            raise GraphError(f"{task.id} needs {unknown[0]}, which is not a task")
    depth: dict[str, int] = {}

    def visit(task_id: str, path: tuple[str, ...]) -> int:
        if task_id in path:
            raise GraphError("dependency cycle: " + " -> ".join((*path, task_id)))
        if task_id not in depth:
            needs = by_id[task_id].needs
            depth[task_id] = 1 + max((visit(need, (*path, task_id)) for need in needs), default=0)
        return depth[task_id]

    for task in tasks:
        visit(task.id, ())
    return depth


def critical_path_ms(tasks: list[Task], durations: dict[str, int]) -> int:
    """The longest chain of measured durations through the graph: no schedule can finish sooner than this."""
    by_id = {task.id: task for task in tasks}
    best: dict[str, int] = {}

    def finish(task_id: str) -> int:
        if task_id not in best:
            best[task_id] = durations.get(task_id, 0) + max((finish(need) for need in by_id[task_id].needs), default=0)
        return best[task_id]

    return max((finish(task.id) for task in tasks), default=0)
