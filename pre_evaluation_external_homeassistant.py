import os
import sys
import asyncio

# Setup paths
project_root = os.getcwd()
ha_dir = os.path.join(project_root, 'applications', 'external_homeassistant')

if ha_dir not in sys.path:
    sys.path.insert(0, ha_dir)

from src.tracer import ArchitectureTracer
from src.visualizer import PlantUMLGenerator
from src.filter import ArchitectureFilter

# Import Home Assistant
try:
    from homeassistant.core import HomeAssistant, CoreState
    from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_STATE_CHANGED

    print("[Setup] Home Assistant imported successfully\n")
except ImportError as e:
    print(f"[ERROR] Cannot import Home Assistant: {e}")
    sys.exit(1)


# =============================================================================
# Test Scenarios
# =============================================================================

async def scenario_1_startup(hass):
    """System startup and initialization"""
    print("   Running: System startup")
    hass.state = CoreState.starting
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()


async def scenario_2_set_state(hass):
    """Update sensor state"""
    print("   Running: Set sensor state")
    hass.states.async_set("sensor.temperature", "22", {"unit": "°C"})
    await hass.async_block_till_done()


async def scenario_3_register_service(hass):
    """Register a new service"""
    print("   Running: Register service")

    async def handle_light(call):
        entity_id = call.data.get("entity_id")
        hass.states.async_set(entity_id, "on")

    hass.services.async_register("light", "turn_on", handle_light)
    await hass.async_block_till_done()


async def scenario_4_call_service(hass):
    """Call a service"""
    print("   Running: Call light service")
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.living_room", "brightness": 255}
    )


async def scenario_5_fire_event(hass):
    """Fire custom event"""
    print("   Running: Fire custom event")
    hass.bus.async_fire("automation_triggered", {"rule": "motion_detected"})
    await hass.async_block_till_done()


async def scenario_6_state_listener(hass):
    """Listen to state changes"""
    print("   Running: Attach state listener")

    def on_state_change(event):
        old = event.data.get("old_state")
        new = event.data.get("new_state")

    hass.bus.async_listen(EVENT_STATE_CHANGED, on_state_change)
    hass.states.async_set("binary_sensor.door", "open")
    await hass.async_block_till_done()


async def scenario_7_multiple_states(hass):
    """Update multiple entities"""
    print("   Running: Update multiple states")
    hass.states.async_set("sensor.humidity", "65", {"unit": "%"})
    hass.states.async_set("sensor.pressure", "1013", {"unit": "hPa"})
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()


async def scenario_8_service_chain(hass):
    """Chain multiple service calls"""
    print("   Running: Service call chain")

    async def handle_scene(call):
        scene = call.data.get("scene")
        hass.states.async_set(f"scene.{scene}", "active")

    hass.services.async_register("scene", "turn_on", handle_scene)

    await hass.services.async_call("scene", "turn_on", {"scene": "movie_time"})
    await hass.services.async_call("light", "turn_on", {"entity_id": "light.tv_backlight"})
    await hass.async_block_till_done()


# =============================================================================
# Main Evaluation
# =============================================================================

async def run_evaluation():
    print("=" * 80)
    print("HOME ASSISTANT EVALUATION")
    print("=" * 80)

    configs = [
        {"id": "0", "name": "Stage0_Before_Filtering", "s1": False, "s2": False, "s3": False, "s4": False},
        {"id": "1", "name": "Stage1", "s1": True, "s2": False, "s3": False, "s4": False},
        {"id": "2", "name": "Stage2", "s1": True, "s2": True, "s3": False, "s4": False},
        {"id": "3", "name": "Stage3", "s1": True, "s2": True, "s3": True, "s4": False},
        {"id": "4", "name": "Stage4", "s1": True, "s2": True, "s3": True, "s4": True},
    ]

    scenarios = [
        ("01_Startup", scenario_1_startup),
        ("02_SetState", scenario_2_set_state),
        ("03_RegisterService", scenario_3_register_service),
        ("04_CallService", scenario_4_call_service),
        ("05_FireEvent", scenario_5_fire_event),
        ("06_StateListener", scenario_6_state_listener),
        ("07_MultipleStates", scenario_7_multiple_states),
        ("08_ServiceChain", scenario_8_service_chain),
    ]

    for config in configs:
        print(f"\n>>> Testing: {config['name']}")

        my_filter = ArchitectureFilter(
            stage1=config['s1'],
            stage2=config['s2'],
            stage3=config['s3'],
            stage4=config['s4']
        )

        tracer = ArchitectureTracer(custom_filter=my_filter)
        hass = HomeAssistant("")

        tracer.start_trace()

        for name, scenario_func in scenarios:
            try:
                await scenario_func(hass)
            except Exception as e:
                print(f"   Warning: {name} - {e}")

        json_file = f"output/homeassistant_{config['name']}.json"
        tracer.stop_trace(json_file)

        puml_file = f"output/homeassistant_{config['name']}.puml"
        print(f"[Visualizer] Generating diagram: {puml_file}")

        viz = PlantUMLGenerator(json_file)
        viz.generate(puml_file)

        await hass.async_stop()

    print("\n" + "=" * 80)
    print("Evaluation complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_evaluation())
