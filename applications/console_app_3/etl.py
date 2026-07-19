import time
import random


class DataSource:
    """
    Simulates reading from a CSV or API.
    """

    def extract_batch(self, batch_size):
        print(f"   [ETL] Extracting {batch_size} records...")
        # Simulating data rows
        return [{"id": i, "val": random.randint(1, 100)} for i in range(batch_size)]


class Transformer:
    """
    Simulates the Logic Layer (Heavy computation).
    """

    def clean_data(self, raw_data):
        print("   [ETL] Transforming data...")
        cleaned = []
        for item in raw_data:
            # We want to see if the Tracer handles this loop
            # without creating 1000 separate arrows if we don't need them.
            # (For now, it will create them, which justifies 'Loop Detection' later).
            item["val"] = item["val"] * 1.5
            cleaned.append(item)
        return cleaned


class DataWarehouse:
    """
    Simulates the Persistence Layer.
    """

    def load(self, data):
        print(f"   [ETL] Loading {len(data)} records to DB...")
        time.sleep(0.1)  # Simulate write latency
        print("   [ETL] Commit successful.")


class ETLPipeline:
    def __init__(self):
        self.source = DataSource()
        self.transformer = Transformer()
        self.warehouse = DataWarehouse()

    def run_daily_job(self):
        print("   [App] Starting Daily Job.")

        # 1. EXTRACT
        raw = self.source.extract_batch(50)  # Keep small (50) for readable trace for now

        # 2. TRANSFORM
        clean = self.transformer.clean_data(raw)

        # 3. LOAD
        self.warehouse.load(clean)

        print("   [App] Job Complete.")