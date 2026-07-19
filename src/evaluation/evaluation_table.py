import json
import os
from collections import defaultdict

# -------------------------------
# PATH RESOLUTION
# -------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

RAW_TRACE_PATH = os.path.join(
    PROJECT_ROOT,
    "output",
    "console_app_1_Stage0_Before_Filtering.json"
)

# -------------------------------
# CONFIGURATION (matching filter.py)
# -------------------------------

# Stage 1a: filename-based ignore patterns
IGNORE_PATTERNS = [
    "site-packages",
    "dist-packages",
    "lib/python",
    "<string>",
    "unittest",
    "pydev",
    "tracer.py",
    "visualizer.py",
    "filter.py"
]

# Stage 1b: fan-in/fan-out thresholds
FAN_IN_THRESHOLD = 3
FAN_OUT_THRESHOLD = 2

# Stage 2: depth limit (for evaluation purposes)
MAX_STACK_DEPTH = 20


# -------------------------------
# SHARED LOGIC
# -------------------------------
def get_confusion_label(should_drop: bool, decision: str) -> str:
    """
    Confusion matrix for filtering decisions.
    """
    is_dropped = (decision == "DROPPED")

    if should_drop and is_dropped:
        return "True Positive"
    if should_drop and not is_dropped:
        return "False Negative"
    if not should_drop and is_dropped:
        return "False Positive"
    return "True Negative"


# ========================================================================
# STAGE 1: UTILITY FILTERING (FILENAME + FAN-IN/FAN-OUT)
# Stage 1a: filename-based filtering
# Stage 1b: fan-in/fan-out utility filtering
# ========================================================================

def stage1a_filename_check(file_path: str):
    """
    Stage 1a: Check if file should be traced based on filename patterns.
    """
    normalized = file_path.replace("\\", "/")
    for pattern in IGNORE_PATTERNS:
        if pattern in normalized:
            return "DROPPED", f"S1a(Filename:{pattern})"
    return "KEPT", None


def build_call_graph(trace_events):
    """
    Build call graph: caller_signature -> set(callee_signatures).
    Matches _build_call_graph from filter.py.
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


def compute_metrics(call_graph, trace_events):
    """
    Compute fan-in and fan-out per method.
    Matches _compute_metrics from filter.py.
    """
    all_methods = set()
    for event in trace_events:
        all_methods.add(f"{event['callee']}.{event['method']}")

    metrics = {}
    for method in all_methods:
        metrics[method] = {"fan_in": 0, "fan_out": 0}

    # Fan-out
    for caller, callees in call_graph.items():
        if caller in metrics:
            metrics[caller]["fan_out"] = len(callees)

    # Fan-in
    for caller, callees in call_graph.items():
        for callee in callees:
            if callee in metrics:
                metrics[callee]["fan_in"] += 1

    return metrics


def find_utilities(metrics):
    """
    Identify utility methods: high fan-in, low fan-out.
    Matches _find_utilities from filter.py.
    """
    utilities = set()

    for method, metric in metrics.items():
        fan_in = metric["fan_in"]
        fan_out = metric["fan_out"]

        if fan_in >= FAN_IN_THRESHOLD and fan_out <= FAN_OUT_THRESHOLD:
            utilities.add(method)

    return utilities


def stage1b_utility_check(method_sig: str, utilities: set):
    """
    Stage 1b: Check if method is a utility based on fan-in/fan-out.
    """
    if method_sig in utilities:
        return "DROPPED", "S1b(Utility-FanIn/Out)"
    return "KEPT", None


def stage1_combined_decision(file_path: str, method_sig: str, utilities: set):
    """
    Full Stage 1 decision combining 1a and 1b.
    """
    # 1a: filename
    res, reason = stage1a_filename_check(file_path)
    if res == "DROPPED":
        return "DROPPED", reason

    # 1b: utility metrics
    res, reason = stage1b_utility_check(method_sig, utilities)
    if res == "DROPPED":
        return "DROPPED", reason

    return "KEPT", None


def generate_stage1_table(trace_data):
    """
    Generate evaluation table for Stage 1 (filename + fan-in/fan-out).
    """
    print("\n[Stage 1 Evaluation] Computing call graph for utility detection...")

    call_graph = build_call_graph(trace_data)
    metrics = compute_metrics(call_graph, trace_data)
    utilities = find_utilities(metrics)

    print(f"[Stage 1 Evaluation] Identified {len(utilities)} utility methods")

    table = []
    for idx, event in enumerate(trace_data, start=1):
        file_path = event.get("file", "")
        callee = event.get("callee", "Unknown")
        method = event.get("method", "unknown")
        method_sig = f"{callee}.{method}"

        # Get metrics for this method
        method_metrics = metrics.get(method_sig, {"fan_in": 0, "fan_out": 0})
        fan_in = method_metrics["fan_in"]
        fan_out = method_metrics["fan_out"]

        decision, reason = stage1_combined_decision(file_path, method_sig, utilities)
        should_drop = (reason is not None)
        conf_case = get_confusion_label(should_drop, decision)

        event_id = f"{method} @ {os.path.basename(file_path)}"
        table.append({
            "No": idx,
            "Event_ID": event_id,
            "FanIn": fan_in,
            "FanOut": fan_out,
            "Reason": reason,
            "Decision": decision,
            "Confusion_Matrix_Result": conf_case
        })

    return table, utilities


def print_stage1_table(table):
    print("\n" + "=" * 120)
    print("STAGE 1 EVALUATION – UTILITY FILTERING (FILENAME + FAN-IN/FAN-OUT)")
    print("=" * 120)
    header = (
        f"{'No':<4} | {'Event (Method @ File)':<40} | {'FanIn':<6} | {'FanOut':<7} | "
        f"{'Reason':<25} | {'Decision':<8} | {'Confusion_Matrix_Result'}"
    )
    print(header)
    print("-" * 120)
    for row in table:
        print(
            f"{row['No']:<4} | {row['Event_ID']:<40} | {row['FanIn']:<6} | {row['FanOut']:<7} | "
            f"{(row['Reason'] or '-'):<25} | {row['Decision']:<8} | {row['Confusion_Matrix_Result']}"
        )


# ========================================================================
# STAGE 2: DYNAMIC DEPTH LIMITING
# ========================================================================

def stage2_decision(file_path: str, depth: int, method_sig: str, utilities: set):
    """
    Stage 2: Stage 1 + depth limiting.
    """
    # Stage 1 first
    res, reason = stage1_combined_decision(file_path, method_sig, utilities)
    if res == "DROPPED":
        return "DROPPED", reason

    # Depth check
    if depth > MAX_STACK_DEPTH:
        return "DROPPED", f"S2(Depth>{MAX_STACK_DEPTH})"

    return "KEPT", None


def generate_stage2_table(trace_data, utilities):
    """
    Generate evaluation table for Stage 2 (Stage 1 + depth).
    """
    table = []
    for idx, event in enumerate(trace_data, start=1):
        file_path = event.get("file", "")
        depth = event.get("depth", 0)
        callee = event.get("callee", "Unknown")
        method = event.get("method", "unknown")
        method_sig = f"{callee}.{method}"

        decision, reason = stage2_decision(file_path, depth, method_sig, utilities)
        should_drop = (reason is not None)
        conf_case = get_confusion_label(should_drop, decision)

        table.append({
            "No": idx,
            "Method": method_sig,
            "Depth": depth,
            "Reason": reason,
            "Decision": decision,
            "Confusion_Matrix_Result": conf_case
        })

    return table


def print_stage2_table(table):
    print("\n" + "=" * 110)
    print("STAGE 2 EVALUATION – DYNAMIC DEPTH LIMITING")
    print("=" * 110)
    header = (
        f"{'No':<4} | {'Method':<40} | {'Depth':<5} | {'Reason':<25} | "
        f"{'Decision':<8} | {'Confusion_Matrix_Result'}"
    )
    print(header)
    print("-" * 110)
    for row in table:
        print(
            f"{row['No']:<4} | {row['Method']:<40} | {row['Depth']:<5} | "
            f"{(row['Reason'] or '-'):<25} | {row['Decision']:<8} | {row['Confusion_Matrix_Result']}"
        )


# ========================================================================
# STAGE 3: ARCHITECTURAL BOUNDARY CHECK (CROSS-FILE OR CROSS-CLASS)
# ========================================================================

def is_architectural_interaction(caller_file: str,
                                 callee_file: str,
                                 caller_class: str = None,
                                 callee_class: str = None) -> bool:
    """
    Stage 3: Decide if a call is architectural based on cross-file or cross-class rule.
    Matches is_architectural_interaction from filter.py.
    """
    # Cross-file calls are architectural
    if caller_file != callee_file:
        return True

    # Same file but different classes = architectural (component interaction)
    if caller_class and callee_class and caller_class != callee_class:
        return True

    # Same class = internal implementation
    return False


def stage3_decision(file_path: str,
                    depth: int,
                    method_sig: str,
                    utilities: set,
                    caller_file: str,
                    callee_file: str,
                    caller_class: str,
                    callee_class: str):
    """
    Stage 3: Stage 1 + Stage 2 + architectural boundary.
    """
    # Stage 2 first
    res, reason = stage2_decision(file_path, depth, method_sig, utilities)
    if res == "DROPPED":
        return "DROPPED", reason

    # Architectural boundary check with class info
    if is_architectural_interaction(caller_file, callee_file, caller_class, callee_class):
        return "KEPT", "S3(Architectural)"
    else:
        return "DROPPED", "S3(Internal-SameClass)"


def generate_stage3_table(trace_data, utilities):
    """
    Generate evaluation table for Stage 3 (architectural boundary).
    """
    table = []
    for idx, event in enumerate(trace_data, start=1):
        file_path = event.get("file", "")
        depth = event.get("depth", 0)
        callee = event.get("callee", "Unknown")
        caller = event.get("caller", "Unknown")
        method = event.get("method", "unknown")
        method_sig = f"{callee}.{method}"

        caller_file = event.get("caller_file", file_path)
        callee_file = file_path

        decision, reason = stage3_decision(
            file_path, depth, method_sig, utilities,
            caller_file, callee_file,
            caller, callee
        )

        should_drop = (reason is not None and decision == "DROPPED")
        conf_case = get_confusion_label(should_drop, decision)

        table.append({
            "No": idx,
            "Method": method_sig,
            "CallerClass": caller,
            "CalleeClass": callee,
            "Reason": reason,
            "Decision": decision,
            "Confusion_Matrix_Result": conf_case
        })

    return table


def print_stage3_table(table):
    print("\n" + "=" * 120)
    print("STAGE 3 EVALUATION – ARCHITECTURAL BOUNDARY CHECK (CROSS-FILE OR CROSS-CLASS)")
    print("=" * 120)
    header = (
        f"{'No':<4} | {'Method':<35} | {'CallerClass':<15} | {'CalleeClass':<15} | "
        f"{'Reason':<25} | {'Decision':<8} | {'Confusion_Matrix_Result'}"
    )
    print(header)
    print("-" * 120)
    for row in table:
        print(
            f"{row['No']:<4} | {row['Method']:<35} | {row['CallerClass']:<15} | "
            f"{row['CalleeClass']:<15} | {(row['Reason'] or '-'):<25} | "
            f"{row['Decision']:<8} | {row['Confusion_Matrix_Result']}"
        )


# ========================================================================
# STAGE 4: LAYER CLASSIFICATION
# ========================================================================

def stage4_decision(file_path: str,
                    depth: int,
                    method_sig: str,
                    utilities: set,
                    caller_file: str,
                    callee_file: str,
                    caller_class: str,
                    callee_class: str,
                    layer_label: str):
    """
    Stage 4: Stage 1 + Stage 2 + Stage 3 + layer classification.
    """
    # Stage 3 first
    res, reason = stage3_decision(
        file_path, depth, method_sig, utilities,
        caller_file, callee_file,
        caller_class, callee_class
    )

    if res == "DROPPED":
        return "DROPPED", reason

    # If kept, return the layer
    return "KEPT", layer_label


def generate_stage4_table(trace_data, utilities):
    """
    Generate evaluation table for Stage 4 (layer classification).
    """
    table = []
    for idx, event in enumerate(trace_data, start=1):
        file_path = event.get("file", "")
        depth = event.get("depth", 0)
        callee = event.get("callee", "Unknown")
        caller = event.get("caller", "Unknown")
        method = event.get("method", "unknown")
        layer = event.get("layer", "Logic_Layer")
        method_sig = f"{callee}.{method}"

        caller_file = event.get("caller_file", file_path)
        callee_file = file_path

        decision, result = stage4_decision(
            file_path, depth, method_sig, utilities,
            caller_file, callee_file,
            caller, callee,
            layer
        )

        table.append({
            "No": idx,
            "Class": callee,
            "Status": decision,
            "Result": result
        })

    return table


def print_stage4_table(table):
    print("\n" + "=" * 90)
    print("STAGE 4 EVALUATION – LAYER CLASSIFICATION")
    print("=" * 90)
    header = (
        f"{'No':<4} | {'Class':<30} | {'Status':<8} | {'Result (Layer or Drop Reason)'}"
    )
    print(header)
    print("-" * 90)
    for row in table:
        print(
            f"{row['No']:<4} | {row['Class']:<30} | {row['Status']:<8} | {row['Result']}"
        )
    print("\n")


# -------------------------------
# MAIN EXECUTION
# -------------------------------
if __name__ == "__main__":
    if not os.path.exists(RAW_TRACE_PATH):
        print(f"\n[ERROR] Trace file not found at: {RAW_TRACE_PATH}")
        print("-" * 60)
        output_dir = os.path.dirname(RAW_TRACE_PATH)
        print("[DEBUG] Files actually found in 'output' folder:")
        if os.path.exists(output_dir):
            files = os.listdir(output_dir)
            if files:
                for f in files:
                    print(f"  - {f}")
            else:
                print("  - (Folder is empty)")
        else:
            print(f"  - The directory '{output_dir}' does not exist.")
        print("-" * 60)
    else:
        with open(RAW_TRACE_PATH, "r") as f:
            trace_data = json.load(f)

        print(f"\n[INFO] Loaded {len(trace_data)} trace events")
        print(f"[INFO] Stage 1 configuration:")
        print(f"  - Filename patterns: {len(IGNORE_PATTERNS)} patterns")
        print(f"  - Fan-in threshold: {FAN_IN_THRESHOLD}")
        print(f"  - Fan-out threshold: {FAN_OUT_THRESHOLD}")
        print(f"[INFO] Stage 2 depth limit: {MAX_STACK_DEPTH}")

        # Stage 1: Utility filtering (filename + fan-in/fan-out)
        s1_table, utilities = generate_stage1_table(trace_data)
        print_stage1_table(s1_table)

        # Stage 2: Depth limiting
        s2_table = generate_stage2_table(trace_data, utilities)
        print_stage2_table(s2_table)

        # Stage 3: Architectural boundary check
        s3_table = generate_stage3_table(trace_data, utilities)
        print_stage3_table(s3_table)

        # Stage 4: Layer classification
        s4_table = generate_stage4_table(trace_data, utilities)
        print_stage4_table(s4_table)
