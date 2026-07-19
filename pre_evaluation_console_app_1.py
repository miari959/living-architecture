import sys
import os

# 1. PATH SETUP
# Ensure the project root is in sys.path so we can import 'src' modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Add the specific experiment directory to path so we can import 'sorter'
experiment_path = os.path.join(current_dir, 'applications', 'console_app_1_sorter')
if experiment_path not in sys.path:
    sys.path.append(experiment_path)

from src.tracer import ArchitectureTracer
from src.filter import ArchitectureFilter
from src.visualizer import PlantUMLGenerator

# Import the Target Application (The Sorter)
try:
    from applications.console_app_1_sorter.sorter import AppController
except ImportError:
    print("[CRITICAL] Could not import 'AppController.py'. Check your file structure.")
    sys.exit(1)


def run_evaluation():
    """
    Runs the 'Sorter' Console App through the evaluation configurations.
    For each configuration, it generates a JSON trace and a PlantUML diagram.
    """

    # Evaluation configurations
    configs = [
        {"id": "0", "name": "Stage0_Before_Filtering", "s1": False, "s2": False, "s3": False, "s4": False},
        {"id": "1", "name": "Stage1",                "s1": True,  "s2": False, "s3": False, "s4": False},
        {"id": "2", "name": "Stage2",                "s1": True,  "s2": True,  "s3": False, "s4": False},
        {"id": "3", "name": "Stage3",                "s1": True,  "s2": True,  "s3": True,  "s4": False},
        {"id": "4", "name": "Stage4",                "s1": True,  "s2": True,  "s3": True,  "s4": True},
    ]

    print(f"[{'=' * 20} STARTING EVALUATION: CONSOLE APP 1 (SORTER) {'=' * 20}]")

    for c in configs:
        print(f"\n>>> TESTING CONFIG {c['id']}: {c['name']}")

        # 1. Configure the Filter (controls Stage 1–4 behaviour globally)
        current_filter = ArchitectureFilter(
            stage1=c["s1"],
            stage2=c["s2"],
            stage3=c["s3"],
            stage4=c["s4"],
        )

        # 2. Initialize Tracer with the Custom Filter
        tracer = ArchitectureTracer(custom_filter=current_filter)

        # 3. Start Tracing
        tracer.start_trace()

        # 4. Run the Target Application Logic
        try:
            app = AppController()
            app.start_sorting_job()
        except Exception as e:
            print(f"   [Error] App crashed during execution: {e}")

        # 5. Stop Tracing and Save JSON (Stage 2 runs inside tracer.stop_trace)
        json_path = f"output/console_app_1_{c['name']}.json"
        tracer.stop_trace(json_path)

        # 6. Generate PlantUML Diagram
        puml_path = f"output/console_app_1_{c['name']}.puml"
        print(f"[Visualizer] Generating diagram: {puml_path}")

        try:
            # Pass the same filter configuration into the visualizer so Stage 1b and Stage 3
            # use the same thresholds and toggles.
            viz = PlantUMLGenerator(json_path)
            viz.filter_engine = current_filter
            viz.generate(puml_path)
        except Exception as e:
            print(f"   [Visualizer Error] Could not generate diagram: {e}")


if __name__ == "__main__":
    run_evaluation()
