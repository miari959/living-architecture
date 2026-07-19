"""Runner for the Sorter console demo (applications/console_app_1_sorter/sorter.py)."""
from src.filter import ArchitectureFilter
from .base import PROJECT_ROOT, RunOutcome, run_simple  # noqa: F401  (PROJECT_ROOT ensures sys.path)

from applications.console_app_1_sorter.sorter import AppController


class ConsoleApp1Runner:
    def run(self, filter_engine: ArchitectureFilter) -> RunOutcome:
        def action():
            app = AppController()
            app.start_sorting_job()

        return run_simple(filter_engine, action)
