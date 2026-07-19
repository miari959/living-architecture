import time
import random


class Logger:
    """
    Simple utility class - will be identified by Stage 3
    High fan-in (called from many places), low fan-out (calls nothing)
    """

    def log(self, message):
        """Called from everywhere - should be filtered by Stage 3"""
        print(f"   [Log] {message}")


class Validator:
    """
    Simple utility class - validates data
    High fan-in, low fan-out
    """

    def is_valid(self, data):
        """Called from multiple places - should be filtered by Stage 3"""
        return data is not None and len(data) > 0


class DataGenerator:
    """
    Represents the 'Data Layer'.
    """

    def __init__(self, logger, validator):
        self.logger = logger
        self.validator = validator

    def get_data(self, size):
        self.logger.log(f"Generating {size} items...")
        data = [random.randint(1, 100) for _ in range(size)]

        # Validate generated data
        if self.validator.is_valid(data):
            self.logger.log("Data generation successful")

        return data


class MergeSorter:
    """
    Represents the 'Logic Layer'.
    """

    def __init__(self, logger, validator):
        self.logger = logger
        self.validator = validator

    def sort(self, arr):
        self.logger.log(f"Sorting array of size {len(arr)}")

        # Validate input
        if not self.validator.is_valid(arr):
            return []

        # Base case
        if len(arr) <= 1:
            return arr

        mid = len(arr) // 2
        left_half = arr[:mid]
        right_half = arr[mid:]

        # RECURSIVE CALLS
        left_sorted = self.sort(left_half)
        right_sorted = self.sort(right_half)

        result = self._merge(left_sorted, right_sorted)
        self.logger.log("Sort completed")
        return result

    def _merge(self, left, right):
        sorted_list = []
        i = j = 0
        while i < len(left) and j < len(right):
            if left[i] < right[j]:
                sorted_list.append(left[i])
                i += 1
            else:
                sorted_list.append(right[j])
                j += 1
        sorted_list.extend(left[i:])
        sorted_list.extend(right[j:])
        return sorted_list


class Statistics:
    """
    Simple statistics calculator
    """

    def __init__(self, logger):
        self.logger = logger

    def calculate_average(self, arr):
        self.logger.log("Calculating average")
        return sum(arr) / len(arr) if arr else 0

    def find_min_max(self, arr):
        self.logger.log("Finding min and max")
        return min(arr), max(arr)


class AppController:
    """
    Represents the 'Presentation/Control Layer'.
    """

    def __init__(self):
        self.logger = Logger()
        self.validator = Validator()

        # Business components
        self.provider = DataGenerator(self.logger, self.validator)
        self.worker = MergeSorter(self.logger, self.validator)
        self.stats = Statistics(self.logger)

    def start_sorting_job(self):
        self.logger.log("Job Started")

        # 1. Get Data
        data = self.provider.get_data(6)

        # 2. Validate before sorting
        if not self.validator.is_valid(data):
            self.logger.log("Invalid data")
            return

        # 3. Sort
        result = self.worker.sort(data)

        # 4. Calculate statistics
        avg = self.stats.calculate_average(result)
        min_val, max_val = self.stats.find_min_max(result)

        self.logger.log(f"Job Done. Result: {result}")
        self.logger.log(f"Average: {avg:.1f}, Range: {min_val}-{max_val}")
