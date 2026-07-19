"""
Runner for the Bank console demo (applications/console_app_2/bank.py).

bank.py spawns threads (parallel UserSessions). sys.settrace() does NOT propagate
into child threads, so this runner additionally installs the callback via
threading.settrace() for the duration of the run, exactly like the original
pre_evaluation_console_app_2.py.
"""
from src.filter import ArchitectureFilter
from .base import PROJECT_ROOT, RunOutcome, run_threaded  # noqa: F401

from applications.console_app_2.bank import BankSimulation


class ConsoleApp2Runner:
    def run(self, filter_engine: ArchitectureFilter) -> RunOutcome:
        # No-self closure so the target's caller is External_User (not this runner).
        def action():
            sim = BankSimulation()
            sim.run_simulation()

        return run_threaded(filter_engine, action)
