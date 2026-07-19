import os
from collections import defaultdict
from typing import List, Dict


class ArchitectureFilter:
    """
    4-Stage filtering pipeline for trace reduction.

    Stage 1: Remove library / utility noise
             - 1a: Get rid of pip packages and internals
             - 1b:  utility filtering (fan-in/fan-out)

    Stage 2: Dynamic depth limiting (post-processing)

    Stage 3: Architectural boundary check (cross-file rule, optional class refinement)

    Stage 4: Layer classification (UI, Data, Logic)
    """

    def __init__(self, stage1=True, stage2=True, stage3=True, stage4=True):
        # Enable/disable each stage
        self.stage1_enabled = stage1
        self.stage2_enabled = stage2
        self.stage3_enabled = stage3
        self.stage4_enabled = stage4

        # --------------------------------------------------------------------
        # Stage 1 configuration
        # --------------------------------------------------------------------
        # 1a: simple filename-based ignore patterns (used during capture)
        self.ignore_patterns = [
            "site-packages",
            "dist-packages",
            "lib/python",
            "<string>",
            "unittest",
            "pydev",
            "tracer.py",
            "visualizer.py",
            "filter.py",
        ]

        # 1b: fan-in/fan-out thresholds for utility detection (used post-processing)
        self.FAN_IN_THRESHOLD = 3
        self.FAN_OUT_THRESHOLD = 2

    # ========================================================================
    # STAGE 1a: Library/Utility Filtering (during capture, filename-based)
    # ========================================================================

    def should_trace(self, filename: str) -> bool:
        """
        Stage 1a: Decide if this file should be traced at all, based on its path.
        """
        if not self.stage1_enabled:
            return True

        normalized = filename.replace("\\", "/")
        for pattern in self.ignore_patterns:
            if pattern in normalized:
                return False

        return True

    # ========================================================================
    # STAGE 1b: Utility Filtering this code is based on and adjusted according to (Hamou-Lhadj 2005)DOI:10.20381/RUOR-12879
    # ========================================================================

    def apply_stage1_utility_filter(self, trace_events: List[Dict]) -> List[Dict]:
        """
        Stage 1b: Remove utility methods based on fan-in/fan-out.

        This runs after trace capture and complements the basic filename filtering.
        It uses a simple call graph and counts fan-in and fan-out per method.
        """
        if not self.stage1_enabled or not trace_events:
            return trace_events

        print(f"\n{Colors.BLUE}[Stage 1b] Building call graph for utility detection...{Colors.ENDC}")

        call_graph = self._build_call_graph(trace_events)
        metrics = self._compute_metrics(call_graph, trace_events)
        utilities = self._find_utilities(metrics)

        print(f"{Colors.BLUE}[Stage 1b] Identified {len(utilities)} utility methods{Colors.ENDC}")

        filtered = []
        removed = 0

        for event in trace_events:
            method_sig = f"{event['callee']}.{event['method']}"
            if method_sig in utilities:
                removed += 1
            else:
                filtered.append(event)

        print(f"{Colors.GREEN}[Stage 1b] Removed {removed} utility calls, kept {len(filtered)} events{Colors.ENDC}")

        return filtered

    def _build_call_graph(self, trace_events: List[Dict]) -> Dict[str, set]:
        """
        Build a simple caller -> set(callees) call graph from the trace.
        Each node is a "Class.method" signature (or "main" for the external root).
        """
        graph = defaultdict(set)

        for event in trace_events:
            caller = event.get("caller")
            caller_method = event.get("caller_method", "main")

            if caller and caller != "External_User":
                caller_sig = f"{caller}.{caller_method}"
            else:
                caller_sig = caller_method

            callee_sig = f"{event['callee']}.{event['method']}"
            graph[caller_sig].add(callee_sig)

        return dict(graph)

    def _compute_metrics(self, call_graph: Dict[str, set], trace_events: List[Dict]) -> Dict[str, Dict[str, int]]:
        """
        Compute fan-in and fan-out per method.
        Methods are identified by "Class.method".
        """
        # Collect all methods that appear as callees
        all_methods = set()
        for event in trace_events:
            all_methods.add(f"{event['callee']}.{event['method']}")

        metrics = {}
        for method in all_methods:
            metrics[method] = {"fan_in": 0, "fan_out": 0}

        # Fan-out: number of distinct callees per caller
        for caller, callees in call_graph.items():
            if caller in metrics:
                metrics[caller]["fan_out"] = len(callees)

        # Fan-in: number of distinct callers per callee
        for caller, callees in call_graph.items():
            for callee in callees:
                if callee in metrics:
                    metrics[callee]["fan_in"] += 1

        return metrics

    def _find_utilities(self, metrics: Dict[str, Dict[str, int]]) -> set:
        """
        Identify methods considered utilities: high fan-in, low fan-out.
        Thresholds are given by FAN_IN_THRESHOLD and FAN_OUT_THRESHOLD.
        """
        utilities = set()

        for method, metric in metrics.items():
            fan_in = metric["fan_in"]
            fan_out = metric["fan_out"]

            if fan_in >= self.FAN_IN_THRESHOLD and fan_out <= self.FAN_OUT_THRESHOLD:
                utilities.add(method)

        return utilities

    # ========================================================================
    # STAGE 2: Dynamic Depth Limiting (post-processing) this code is based on and adjusted according to (B. Cornelissen, L. Moonen, and A. Zaidman 2008)doi: 10.1109/ICSM.2008.4658063​
    # ========================================================================

    def apply_stage2_filtering(self, trace_events: List[Dict], target_size: int) -> List[Dict]:
        """
        Stage 2: Remove deep implementation details.
        Dynamically calculates a max depth so that we keep around target_size events.
        """
        if not self.stage2_enabled or not trace_events:
            return trace_events

        # Count how many events at each depth
        depth_counts: Dict[int, int] = {}
        for event in trace_events:
            d = event["depth"]
            if d in depth_counts:
                depth_counts[d] += 1
            else:
                depth_counts[d] = 1

        # Find cutoff depth to reach target_size
        accumulated = 0
        max_depth = 0
        for depth in sorted(depth_counts.keys()):
            accumulated += depth_counts[depth]
            max_depth = depth
            if accumulated >= target_size:
                break

        print(f"{Colors.BLUE}[Stage 2] Calculated max depth: {max_depth}{Colors.ENDC}")

        # Filter out events deeper than max_depth
        filtered = [e for e in trace_events if e["depth"] <= max_depth]
        removed = len(trace_events) - len(filtered)

        print(f"{Colors.GREEN}[Stage 2] Removed {removed} deep events, kept {len(filtered)} events{Colors.ENDC}")

        return filtered

    # ========================================================================
    # STAGE 3: Architectural Boundary Check (cross-component interaction) This code is inspired from(Steven P.Reiss 2001)DOI:10.5555/381473.381497
    # ========================================================================

    def is_architectural_interaction(
            self,
            caller_file: str,
            callee_file: str,
            caller_class: str = None,
            callee_class: str = None,
    ) -> bool:
        """
        Stage 3: Decide whether a call is an "architectural interaction".

        Architectural interactions are:
        1. Cross-file calls (different modules)
        2. Cross-class calls within same file (different components)

        Non-architectural (filtered out):
        - Same class calling itself (internal implementation)
        """
        if not self.stage3_enabled:
            return True

        # Cross-file = always architectural
        if caller_file != callee_file:
            return True

        # Same file but different classes = architectural (component interaction)
        if caller_class and callee_class and caller_class != callee_class:
            return True

        # Same class calling itself = internal implementation (not architectural)
        return False

    # ========================================================================
    # STAGE 4: Layer Classification
    # ========================================================================

    def categorize_class(self, instance) -> str:
        """
        Stage 4: Guess which layer this class belongs to.
        Returns: Presentation_Layer, Data_Layer, Logic_Layer or Participant (if disabled).
        """
        if not self.stage4_enabled:
            return "Participant"

        if instance is None:
            return "Logic_Layer"

        class_name = instance.__class__.__name__

        # UI / Presentation clues
        if hasattr(instance, "winfo_id") or hasattr(instance, "mainloop"):
            return "Presentation_Layer"
        if "Window" in class_name or "View" in class_name or "Serializer" in class_name:
            return "Presentation_Layer"

        # Data / Persistence clues
        if hasattr(instance, "cursor") or hasattr(instance, "execute"):
            return "Data_Layer"
        if "Model" in class_name and hasattr(instance, "save"):
            return "Data_Layer"

        # Default: core logic
        return "Logic_Layer"


class Colors:
    """Console colors for pretty output."""
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
