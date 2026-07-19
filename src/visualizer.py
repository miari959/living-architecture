import json
import os
import datetime
from collections import OrderedDict
from src.filter import ArchitectureFilter


class PlantUMLGenerator:
    """
    Responsible for transforming raw architectural traces into visual diagrams.
    Applies post-processing stages (Stage 1b and Stage 3) before generating PlantUML.
    """

    def __init__(self, trace_file: str):
        self.trace_file = trace_file
        self.participants = set()
        self.sequences = []
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Use the same filter logic as the tracer
        self.filter_engine = ArchitectureFilter()

    def generate(self, output_file: str):
        """
        Load -> Post-process (Stage 1b + Stage 3) -> Build participants and sequence -> Write PUML -> Render PNG.
        """
        if not os.path.exists(self.trace_file):
            print(f"[Error] Trace file not found: {self.trace_file}")
            return

        with open(self.trace_file, 'r') as f:
            trace_data = json.load(f)

        # ------------------------------------------------------------------
        # Stage 1b: utility filtering (fan-in/fan-out) on the loaded trace
        # ------------------------------------------------------------------
        trace_data = self.filter_engine.apply_stage1_utility_filter(trace_data)

        # ------------------------------------------------------------------
        # Stage 3: architectural boundary check (cross-file rule)
        # We filter interactions here before building the diagram.
        # NOTE: At the moment we only have one "file" field per event, which
        #       likely corresponds to the callee file. For now, we treat this
        #       as both caller_file and callee_file. When you later extend the
        #       tracer to record caller_file separately, you can replace this.
        # ------------------------------------------------------------------
        architectural_events = []
        for entry in trace_data:
            caller = entry['caller']
            callee = entry['callee']
            file_path = entry.get('file', '')

            caller_file = file_path      # TODO: replace with real caller_file once available
            callee_file = file_path      # currently both the same, so Stage 3 will treat all as non-architectural

            # At the moment this will return False for same-file calls.
            # Once you extend the trace to distinguish caller_file/callee_file,
            # this will start to filter by real boundaries.
            if self.filter_engine.is_architectural_interaction(
                caller_file=caller_file,
                callee_file=callee_file,
                caller_class=caller,
                callee_class=callee
            ):
                architectural_events.append(entry)

        # For now, if architectural_events is empty (because caller_file==callee_file),
        # fall back to the filtered trace_data so the diagram is not blank.
        events_for_diagram = architectural_events if architectural_events else trace_data

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

            arrow = f'{caller} -> {callee} : {method}()'
            self.sequences.append(arrow)

        # ------------------------------------------------------------------
        # 3. Write to PUML file and 4. Render PNG
        # ------------------------------------------------------------------
        self._write_puml(output_file)
        self._render_png(output_file)

    def _write_puml(self, output_file: str):
        with open(output_file, 'w') as f:
            # --- HEADER & STYLING ---
            f.write("@startuml\n")
            f.write("skinparam style strictuml\n")
            f.write("skinparam sequenceMessageAlign center\n")
            f.write("skinparam participantPadding 10\n")
            f.write("skinparam boxPadding 10\n")

            f.write("skinparam sequence {\n")
            f.write("    ArrowColor Black\n")
            f.write("    ActorBorderColor Black\n")
            f.write("    LifeLineBorderColor Black\n")
            f.write("    ParticipantBorderColor Black\n")
            f.write("    ParticipantBackgroundColor White\n")
            f.write("    ActorBackgroundColor White\n")
            f.write("}\n")

            f.write("title Living Architecture - Dynamic Analysis Trace\n")
            f.write("header Generated by Architecture Recovery Tool\n")
            f.write(f"footer Generated: {self.timestamp}\n\n")

            # Scientific Standard: Actors (Triggers) on the left, Systems on the right.

            # 1. Force "User_Action" to be the first actor
            if "User_Action" in self.participants:
                f.write('actor "External Trigger" as User_Action\n')
                self.participants.remove("User_Action")

            # 2. List remaining system components
            for p in sorted(self.participants):
                f.write(f'participant "{p}"\n')

            f.write("\n")

            # --- SEQUENCE LOGIC ---
            for seq in self.sequences:
                f.write(f"{seq}\n")

            f.write("\n")

            # --- SCIENTIFIC LEGEND ---
            f.write("legend right\n")
            f.write("  | **Visual Element** | **Type** | **Description** |\n")
            f.write("  | <$user> | Actor | External Trigger or User Action |\n")
            f.write("  | <size:10>[Rect]</size> | Participant | System Class, Module |\n")
            f.write("  | -> | Sync Call | Direct Function or Method Invocation |\n")
            f.write("  | -->> | Return | (Implicit) Control flow returns to caller |\n")
            f.write("endlegend\n")

            f.write("@enduml\n")
            print(f"[Visualizer] PUML Diagram generated at: {output_file}")

    def _render_png(self, puml_path: str):
        """
        Tries to convert the generated .puml file into a .png image.
        """
        if not puml_path.endswith(".puml"):
            return

        png_path = puml_path.replace(".puml", ".png")

        try:
            from plantuml import PlantUML

            print(f"[Visualizer] Converting to PNG (sending to PlantUML server)...")
            server = PlantUML(url='http://www.plantuml.com/plantuml/img/')
            server.processes_file(puml_path)

            if os.path.exists(png_path):
                print(f"[SUCCESS] PNG Image saved at: {png_path}")
            else:
                print(f"[WARNING] PNG file was not created. Check internet connection?")

        except ImportError:
            print("[INFO] 'plantuml' library not found. To generate PNGs, run: pip install plantuml")
        except Exception as e:
            print(f"[WARNING] PNG Rendering failed: {e}")
            print(">> Note: If the diagram is massive (like raw Home Assistant), this is expected behavior.")
