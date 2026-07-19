import threading
import time
import random


class BankAccount:
    """
    Represents a shared resource in a concurrent system.
    """

    def __init__(self, balance=100):
        self.balance = balance
        self.lock = threading.Lock()  # Thread safety

    def deposit(self, amount, user):
        with self.lock:
            print(f"   [{user}] Depositing ${amount}...")
            time.sleep(0.01)  # Simulate DB latency
            self.balance += amount

    def withdraw(self, amount, user):
        with self.lock:
            print(f"   [{user}] Withdrawing ${amount}...")
            time.sleep(0.01)
            self.balance -= amount


class UserSession(threading.Thread):
    """
    Simulates a User acting in their own thread.
    """

    def __init__(self, name, account, action):
        super().__init__()
        self.name = name
        self.account = account
        self.action = action

    def run(self):
        # This runs in PARALLEL.
        # If your tracer is not thread-aware, this method will NEVER appear in the diagram.
        if self.action == "save":
            self.account.deposit(50, self.name)
        elif self.action == "spend":
            self.account.withdraw(20, self.name)


class BankSimulation:
    def run_simulation(self):
        print("   [System] Bank Open.")
        shared_account = BankAccount(1000)

        # Create two parallel users
        u1 = UserSession("Alice", shared_account, "save")
        u2 = UserSession("Bob", shared_account, "spend")

        # Start them simultaneously
        u1.start()
        u2.start()

        # Wait for them to finish
        u1.join()
        u2.join()
        print("   [System] Bank Closed.")