import sys
import time
import json
import os
from types import FrameType
from typing import Any
from collections import defaultdict
from src.filter import ArchitectureFilter


class Colors:
    """Console colors."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def log_tool(msg: str):
    """Print tracer messages in blue."""
    print(f"{Colors.BLUE}[TRACER] {msg}{Colors.ENDC}")


class ArchitectureTracer:
    """
    Traces program execution and applies the 4-stage filtering concept.

    Stage 1: Applied during capture (library / filename filtering).
             (Fan-in/fan-out utility filtering is done in post-processing.)

    Stage 2: Applied after capture (dynamic depth limiting).

    Stage 3: Applied after capture (architectural boundary check - cross-file or cross-class).

    Stage 4: Applied during capture (layer labeling based on instance capabilities).
    """

    def __init__(self, custom_filter=None):
        self.trace_log = []
        self.start_time = 0.0

        # Use provided filter or create default
        if custom_filter:
            self.filter_engine = custom_filter
        else:
            self.filter_engine = ArchitectureFilter()

        # Stats tracking
        self.total_filtered_count = 0
        self.filtered_stats = defaultdict(list)
        self.report_stats = defaultdict(int)
        self.stage2_removed = 0
        self.stage3_removed = 0
        self.layer_stats = defaultdict(int)

    def start_trace(self):
        """Start capturing execution events."""
        log_tool("Starting trace...")
        self.start_time = time.time()

        # Reset everything
        self.trace_log = []
        self.total_filtered_count = 0
        self.stage2_removed = 0
        self.stage3_removed = 0
        self.filtered_stats.clear()
        self.report_stats.clear()
        self.layer_stats.clear()

        sys.settrace(self._trace_callback)

    def stop_trace(self, output_path: str = "output/trace_data.json"):
        """
        Stop capturing and apply post-processing filters.
        Applies Stage 2 (dynamic depth limiting) and Stage 3 (boundary check).
        Stage 1b (fan-in/fan-out) can run later in the pipeline if needed.
        """
        sys.settrace(None)

        log_tool(f"Captured {len(self.trace_log)} events")

        # Stage 2: Dynamic depth filtering (post-processing)
        if self.filter_engine.stage2_enabled:
            captured = len(self.trace_log)
            if captured > 0:
                # For now: target size = 50% of captured events (at least 10)
                target_size = max(10, captured // 2)
            else:
                target_size = captured

            before = len(self.trace_log)
            self.trace_log = self.filter_engine.apply_stage2_filtering(
                self.trace_log,
                target_size
            )
            self.stage2_removed = before - len(self.trace_log)

        # Stage 3: Architectural boundary check (post-processing)
        if self.filter_engine.stage3_enabled:
            before = len(self.trace_log)
            self.trace_log = self._apply_stage3_filtering(self.trace_log)
            self.stage3_removed = before - len(self.trace_log)

        # Stage 1b (fan-in/fan-out utility filtering) is not applied here.
        # It can be applied later in the visualizer or evaluation scripts.

        # Save results
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        log_tool(f"Saving to {output_path}")
        self._save_results(output_path)
        self._print_report()

    def _apply_stage3_filtering(self, trace_events):
        """
        Stage 3: Keep only architectural interactions (cross-file or cross-class).
        Filters out same-class calls as they are considered internal implementation details.
        """
        if not trace_events:
            return trace_events

        print(f"{Colors.BLUE}[Stage 3] Applying architectural boundary filter (cross-file or cross-class)...{Colors.ENDC}")

        filtered = []
        removed = 0

        for event in trace_events:
            caller_file = event.get("caller_file", "")
            callee_file = event.get("callee_file", event.get("file", ""))
            caller_class = event.get("caller", "")
            callee_class = event.get("callee", "")

            # If caller_file is not set (e.g., external entry point), keep the event
            if not caller_file or caller_file == "":
                filtered.append(event)
                continue

            # Apply architectural boundary check with class information
            if self.filter_engine.is_architectural_interaction(
                caller_file,
                callee_file,
                caller_class,
                callee_class
            ):
                filtered.append(event)
            else:
                removed += 1

        print(f"{Colors.GREEN}[Stage 3] Removed {removed} internal calls, kept {len(filtered)} events{Colors.ENDC}")

        return filtered

    def _trace_callback(self, frame: FrameType, event: str, arg: Any):
        """Called for every function call during execution."""
        if event != 'call':
            return self._trace_callback

        filename = frame.f_code.co_filename
        func_name = frame.f_code.co_name

        # Calculate call depth for later Stage 2 filtering
        depth = 0
        f = frame
        while f:
            depth += 1
            f = f.f_back

        # Stage 1a: Check if we should ignore this file
        if not self.filter_engine.should_trace(filename):
            self._record_filtered("Stage 1 (Utility/Lib)", func_name)
            return None

        # Get caller info (including caller_file for Stage 3)
        caller_frame = frame.f_back
        caller_method = caller_frame.f_code.co_name if caller_frame else "main"
        caller_class = "External_User"
        caller_file = ""

        if caller_frame:
            caller_file = caller_frame.f_code.co_filename
            if 'self' in caller_frame.f_locals:
                caller_class = caller_frame.f_locals['self'].__class__.__name__

        # Get callee info
        class_name = "Global_Script"
        layer_type = "Script"

        if 'self' in frame.f_locals:
            instance = frame.f_locals['self']
            class_name = instance.__class__.__name__

            # Do not trace the tracer itself
            if class_name == self.__class__.__name__:
                return None

            # Stage 4: Classify layer
            layer_type = self.filter_engine.categorize_class(instance)

        # Track layer stats
        self.layer_stats[layer_type] += 1

        # Record event with both caller_file and callee_file for Stage 3
        self.trace_log.append({
            "caller": caller_class,
            "caller_method": caller_method,
            "caller_file": caller_file,
            "callee": class_name,
            "method": func_name,
            "callee_file": filename,
            "layer": layer_type,
            "file": filename,  # Keep for backward compatibility
            "depth": depth
        })

        return self._trace_callback

    def _record_filtered(self, reason, name):
        """Track filtered events for reporting."""
        self.total_filtered_count += 1
        self.report_stats[reason] += 1
        if len(self.filtered_stats[reason]) < 3:
            self.filtered_stats[reason].append(name)

    def _print_report(self):
        """Print filtering statistics."""
        print("\n" + "=" * 85)
        print(f"{Colors.HEADER}{Colors.BOLD} FILTERING REPORT {Colors.ENDC}")
        print("=" * 85)

        total = len(self.trace_log) + self.total_filtered_count + self.stage2_removed + self.stage3_removed

        print(f"{Colors.BOLD}SUMMARY:{Colors.ENDC}")
        print(f" > Total events analyzed: {total}")
        print(f" > Events kept: {Colors.GREEN}{len(self.trace_log)}{Colors.ENDC}")

        if total > 0:
            reduction = ((self.total_filtered_count + self.stage2_removed + self.stage3_removed) / total) * 100
            print(f" > Reduction: {Colors.CYAN}{reduction:.2f}%{Colors.ENDC}")

        print("-" * 85)
        print(f"{Colors.BOLD}{'STAGE':<30} | {'REMOVED':<10} | {'EXAMPLES'}{Colors.ENDC}")
        print("-" * 85)

        # Stage 1 (filename-based)
        count = self.report_stats.get("Stage 1 (Utility/Lib)", 0)
        samples = self.filtered_stats.get("Stage 1 (Utility/Lib)", [])
        sample_str = ", ".join(samples) + "..." if samples else "N/A"
        print(f"{Colors.FAIL}{'Stage 1 (Libraries&Utilities)':<30}{Colors.ENDC} | {count:<10} | {sample_str}")

        # Stage 2 (depth)
        print(f"{Colors.FAIL}{'Stage 2 (Depth)':<30}{Colors.ENDC} | {self.stage2_removed:<10} | (post-processed)")

        # Stage 3 (boundary) - now applied during trace processing
        s3_sample = f"{self.stage3_removed} internal calls" if self.stage3_removed > 0 else "N/A"
        print(f"{Colors.FAIL}{'Stage 3 (Boundary)':<30}{Colors.ENDC} | {self.stage3_removed:<10} | {s3_sample}")

        print("-" * 85)
        print(f"{Colors.BOLD}{'LAYER DISTRIBUTION':<30} | {'COUNT':<10} | {'BREAKDOWN'}{Colors.ENDC}")
        print("-" * 85)

        if self.layer_stats:
            breakdown = ", ".join([f"{k}: {v}" for k, v in self.layer_stats.items()])
            if len(breakdown) > 45:
                breakdown = breakdown[:42] + "..."
            print(f"{Colors.GREEN}{'Stage 4 (Layers)':<30}{Colors.ENDC} | {len(self.trace_log):<10} | {breakdown}")
        else:
            print(f"{'Stage 4 (Layers)':<30} | {0:<10} | N/A")

        print("=" * 85 + "\n")

    def get_report_dict(self):
        """
        Structured equivalent of _print_report().

        Reads the same instance attributes _print_report() prints and returns
        them as a plain dict, so callers (e.g. a web backend) can consume the
        filtering statistics as data instead of parsing stdout. This is purely
        additive: it does not touch stop_trace() or _print_report().

        Must be called AFTER stop_trace(), once the post-processing filters
        (Stage 2 / Stage 3) have run and the stats attributes are final.
        """
        kept = len(self.trace_log)
        total = kept + self.total_filtered_count + self.stage2_removed + self.stage3_removed
        removed = self.total_filtered_count + self.stage2_removed + self.stage3_removed
        reduction = (removed / total * 100) if total > 0 else 0.0

        return {
            "total_events": total,
            "kept": kept,
            "removed": removed,
            "reduction_pct": round(reduction, 2),
            "stage1_removed": self.report_stats.get("Stage 1 (Utility/Lib)", 0),
            "stage2_removed": self.stage2_removed,
            "stage3_removed": self.stage3_removed,
            "layer_breakdown": dict(self.layer_stats),
        }

    def _save_results(self, filepath):
        """Save trace to JSON file."""
        try:
            with open(filepath, 'w') as f:
                json.dump(self.trace_log, f, indent=4)
        except Exception as e:
            print(f"{Colors.FAIL}[Error] Failed to save: {e}{Colors.ENDC}")
