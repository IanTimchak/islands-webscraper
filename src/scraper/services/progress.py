from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


class ProgressReporter(ABC):
    """Small interface for workflow progress reporting."""

    @abstractmethod
    def emit(self, level: int, message: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def start_task(
        self,
        description: str,
        total: float | None,
        level: int = 0,
        visible: bool = True,
    ) -> Any:
        raise NotImplementedError

    @abstractmethod
    def update_task(
        self,
        task_id: Any,
        *,
        description: str | None = None,
        completed: float | None = None,
        total: float | None = None,
        advance: float | None = None,
        visible: bool | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def finish_task(self, task_id: Any, description: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError


class NullProgressReporter(ProgressReporter):
    """No-op reporter for silent runs."""

    def emit(self, level: int, message: str) -> None:
        return

    def start_task(
        self,
        description: str,
        total: float | None,
        level: int = 0,
        visible: bool = True,
    ) -> None:
        return None

    def update_task(
        self,
        task_id: Any,
        *,
        description: str | None = None,
        completed: float | None = None,
        total: float | None = None,
        advance: float | None = None,
        visible: bool | None = None,
    ) -> None:
        return

    def finish_task(self, task_id: Any, description: str | None = None) -> None:
        return

    def stop(self) -> None:
        return


class ConsoleProgressReporter(ProgressReporter):
    """
    Terminal progress reporter using rich.

    Intended behavior:
    - level 0: top-level workflow bars
    - level 1: secondary bars if you choose to add them later
    - `emit()` is kept for compatibility, but progress bars should be preferred
    """

    def __init__(self, max_level: int = 1) -> None:
        self.max_level = max_level
        self._started = False
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            transient=False,
        )

    def _ensure_started(self) -> None:
        if not self._started:
            self._progress.start()
            self._started = True

    def emit(self, level: int, message: str) -> None:
        if level > self.max_level:
            return
        self._ensure_started()
        self._progress.console.print(message)

    def start_task(
        self,
        description: str,
        total: float | None,
        level: int = 0,
        visible: bool = True,
    ) -> TaskID | None:
        if level > self.max_level:
            return None
        self._ensure_started()
        return self._progress.add_task(
            description=description,
            total=total,
            visible=visible,
        )

    def update_task(
        self,
        task_id: TaskID | None,
        *,
        description: str | None = None,
        completed: float | None = None,
        total: float | None = None,
        advance: float | None = None,
        visible: bool | None = None,
    ) -> None:
        if task_id is None:
            return

        kwargs: dict[str, Any] = {}
        if description is not None:
            kwargs["description"] = description
        if completed is not None:
            kwargs["completed"] = completed
        if total is not None:
            kwargs["total"] = total
        if advance is not None:
            kwargs["advance"] = advance
        if visible is not None:
            kwargs["visible"] = visible

        self._progress.update(task_id, **kwargs)

    def finish_task(self, task_id: TaskID | None, description: str | None = None) -> None:
        if task_id is None:
            return

        task = self._progress.tasks[task_id]
        self._progress.update(
            task_id,
            completed=task.total if task.total is not None else task.completed,
            description=description or task.description,
        )

    def stop(self) -> None:
        if self._started:
            self._progress.stop()
            self._started = False