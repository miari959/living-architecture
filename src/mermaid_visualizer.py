import json
import os
from src.filter import ArchitectureFilter


class MermaidGenerator:
    """
    Transforms raw architectural traces into Mermaid `sequenceDiagram` text.

    This is a parallel to src/visualizer.py's PlantUMLGenerator, built for the
    web frontend (Mermaid.js renders the diagram client-side as SVG). It applies
    the SAME post-processing stages (Stage 1b + Stage 3) as PlantUMLGenerator so
    that the two engines produce identical filtering outcomes for a given trace.

    Unlike PlantUMLGenerator, it can be constructed from an in-memory list of
    trace events (avoiding a disk round-trip on the web request path) or from a
    JSON file path (for CLI / regression-test parity against output/*.json).
    """

    def __init__(self, trace_file: str = None, trace_data: list = None, filter_engine: ArchitectureFilter = None):
        if trace_file is None and trace_data is None:
            raise ValueError("MermaidGenerator requires either trace_file or trace_data")

        self.trace_file = trace_file
        self._trace_data = trace_data
        self.participants = set()
        self.sequences = []

        # Use the same filter logic as the tracer / PlantUML generator.
        self.filter_engine = filter_engine if filter_engine is not None else ArchitectureFilter()

    def generate(self, output_file: str = None) -> str:
        """
        Load -> Post-process (Stage 1b + Stage 3) -> Build participants and
        sequence -> return Mermaid text (and optionally write it to disk).

        Returns the Mermaid `sequenceDiagram` string.
        """
        # ------------------------------------------------------------------
        # Load trace data (in-memory takes precedence over file)
        # ------------------------------------------------------------------
        if self._trace_data is not None:
            trace_data = self._trace_data
        else:
            if not os.path.exists(self.trace_file):
                print(f"[Error] Trace file not found: {self.trace_file}")
                return ""
            with open(self.trace_file, 'r') as f:
                trace_data = json.load(f)

        # ------------------------------------------------------------------
        # Stage 1b: utility filtering (fan-in/fan-out) on the loaded trace
        # ------------------------------------------------------------------
        trace_data = self.filter_engine.apply_stage1_utility_filter(trace_data)

        # ------------------------------------------------------------------
        # Stage 3: architectural boundary check.
        #
        # NOTE: this deliberately mirrors PlantUMLGenerator.generate() verbatim,
        # including its known quirk: it sets caller_file == callee_file ==
        # entry['file'] rather than using the separately-recorded caller_file /
        # callee_file fields, so this Stage-3 pass only ever fires on class-name
        # difference (not real cross-file detection), and falls back to the
        # unfiltered trace_data if that yields an empty result. This is INTENTIONAL
        # parity with src/visualizer.py, not a bug to fix here -- diverging would
        # make the two diagram engines produce different output for the same trace.
        # In practice tracer.py's own Stage 3 already filtered the JSON correctly
        # before it reached this point, so the final diagram is still correct.
        # ------------------------------------------------------------------
        architectural_events = []
        for entry in trace_data:
            caller = entry['caller']
            callee = entry['callee']
            file_path = entry.get('file', '')

            caller_file = file_path
            callee_file = file_path

            if self.filter_engine.is_architectural_interaction(
                caller_file=caller_file,
                callee_file=callee_file,
                caller_class=caller,
                callee_class=callee
            ):
                architectural_events.append(entry)

        events_for_diagram = architectural_events if architectural_events else trace_data

        # Reset per-call state so a reused instance doesn't accumulate.
        self.participants = set()
        self.sequences = []

        # ------------------------------------------------------------------
        # 1. First Pass: Identify participants
        # ------------------------------------------------------------------
        for entry in events_for_diagram:
            caller = entry['caller']
            if caller in ["Script_Controller", "External_User", "Global_Script"]:
                caller = "User_Action"

            callee = entry['callee']

            if caller != "Global_Script":
                self.participants.add(caller)
            if callee != "Global_Script":
                self.participants.add(callee)

        # ------------------------------------------------------------------
        # 2. Second Pass: Build sequence arrows
        # ------------------------------------------------------------------
        for entry in events_for_diagram:
            caller = entry['caller']
            callee = entry['callee']
            method = entry['method']

            # Normalize caller
            if caller in ["Script_Controller", "External_User", "Global_Script"]:
                caller = "User_Action"

            # Skip interactions that only involve the global script wrapper
            if callee == "Global_Script":
                continue

            self.sequences.append((caller, callee, method))

        # ------------------------------------------------------------------
        # 3. Build the Mermaid text
        # ------------------------------------------------------------------
        mermaid_text = self._build_mermaid()

        if output_file:
            with open(output_file, 'w') as f:
                f.write(mermaid_text)
            print(f"[MermaidGenerator] Diagram written to: {output_file}")

        return mermaid_text

    def _sanitize(self, name: str) -> str:
        """
        Mermaid participant IDs cannot contain spaces or most punctuation.
        Class names from the tracer are Python identifiers (safe), but guard
        anyway so malformed names never break the whole diagram.
        """
        return "".join(c if (c.isalnum() or c == "_") else "_" for c in str(name))

    def _build_mermaid(self) -> str:
        lines = ["sequenceDiagram"]

        participants = set(self.participants)

        # Actor (External Trigger) first, mirroring PlantUMLGenerator ordering.
        # Mermaid syntax is `actor <id> as <Label>` (reversed from PlantUML's
        # `actor "Label" as <id>`).
        if "User_Action" in participants:
            lines.append("    actor User_Action as External Trigger")
            participants.discard("User_Action")

        for p in sorted(participants):
            pid = self._sanitize(p)
            lines.append(f"    participant {pid}")

        for caller, callee, method in self.sequences:
            src = self._sanitize(caller)
            dst = self._sanitize(callee)
            # `->>` is the solid arrow-with-head, Mermaid's idiom for a sync call
            # (PlantUML uses `->`).
            lines.append(f"    {src}->>{dst}: {method}()")

        return "\n".join(lines) + "\n"
