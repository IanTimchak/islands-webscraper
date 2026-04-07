from __future__ import annotations


class ProgressReporter:
    """Small interface for workflow progress reporting."""

    def emit(self, level: int, message: str) -> None:
        raise NotImplementedError


class NullProgressReporter(ProgressReporter):
    """No-op reporter for silent runs."""

    def emit(self, level: int, message: str) -> None:
        pass


class ConsoleProgressReporter(ProgressReporter):
    """
    Simple console reporter.

    level 0 = top-level run progress
    level 1 = household progress
    level 2 = detailed debug
    """

    def __init__(self, max_level: int = 1) -> None:
        self.max_level = max_level

    def emit(self, level: int, message: str) -> None:
        if level > self.max_level:
            return

        indent = "  " * level
        print(f"{indent}{message}")