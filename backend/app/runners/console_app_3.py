"""Runner for the ETL console demo (applications/console_app_3/etl.py)."""
from src.filter import ArchitectureFilter
from .base import PROJECT_ROOT, RunOutcome, run_simple  # noqa: F401  (PROJECT_ROOT ensures sys.path)

from applications.console_app_3.etl import ETLPipeline


class ConsoleApp3Runner:
    def run(self, filter_engine: ArchitectureFilter) -> RunOutcome:
        def action():
            pipeline = ETLPipeline()
            pipeline.run_daily_job()

        return run_simple(filter_engine, action)
