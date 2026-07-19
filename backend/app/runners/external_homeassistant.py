"""
Runner for Home Assistant core (applications/external_homeassistant/homeassistant).

Mirrors pre_evaluation_external_homeassistant.py: it does NOT boot the full HA
app, only instantiates a bare HomeAssistant("") core object and exercises 8 short
synthetic async scenarios (set state, register/call a service, fire an event,
attach a listener, etc.).

Differences from the original one-shot script (needed for a long-lived server):
  - A fresh HomeAssistant("") is created per run.
  - await hass.async_stop() runs at the end of EVERY run (in a finally), not just
    at the end of a whole config loop, so background tasks don't leak across
    repeated live requests.
"""
import asyncio
import os
import sys

from .base import PROJECT_ROOT, RunOutcome, finalize, new_tracer
from src.filter import ArchitectureFilter

# --- Put the vendored HA package dir FIRST on the path (once) ---
# This is load-bearing, not incidental: the tracer's Stage 1a ignore list drops
# anything under "site-packages", so importing the pip-installed homeassistant
# would cause the filter to strip HA entirely as library noise (verified: the
# diagram collapses to 0 arrows). Importing the vendored copy makes HA's code
# "application code" by path, so it is traced. Keep this import path.
_HA_DIR = os.path.join(str(PROJECT_ROOT), 'applications', 'external_homeassistant')
if _HA_DIR not in sys.path:
    sys.path.insert(0, _HA_DIR)

from homeassistant.core import HomeAssistant, CoreState  # noqa: E402
from homeassistant.const import (  # noqa: E402
    EVENT_HOMEASSISTANT_START,
    EVENT_STATE_CHANGED,
)


# =============================================================================
# The 8 scenarios (copied from pre_evaluation_external_homeassistant.py)
# =============================================================================
async def _s1_startup(hass):
    hass.state = CoreState.starting
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()


async def _s2_set_state(hass):
    hass.states.async_set("sensor.temperature", "22", {"unit": "°C"})
    await hass.async_block_till_done()


async def _s3_register_service(hass):
    async def handle_light(call):
        entity_id = call.data.get("entity_id")
        hass.states.async_set(entity_id, "on")

    hass.services.async_register("light", "turn_on", handle_light)
    await hass.async_block_till_done()


async def _s4_call_service(hass):
    await hass.services.async_call(
        "light", "turn_on",
        {"entity_id": "light.living_room", "brightness": 255},
    )


async def _s5_fire_event(hass):
    hass.bus.async_fire("automation_triggered", {"rule": "motion_detected"})
    await hass.async_block_till_done()


async def _s6_state_listener(hass):
    def on_state_change(event):
        _ = event.data.get("old_state")
        _ = event.data.get("new_state")

    hass.bus.async_listen(EVENT_STATE_CHANGED, on_state_change)
    hass.states.async_set("binary_sensor.door", "open")
    await hass.async_block_till_done()


async def _s7_multiple_states(hass):
    hass.states.async_set("sensor.humidity", "65", {"unit": "%"})
    hass.states.async_set("sensor.pressure", "1013", {"unit": "hPa"})
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()


async def _s8_service_chain(hass):
    async def handle_scene(call):
        scene = call.data.get("scene")
        hass.states.async_set(f"scene.{scene}", "active")

    hass.services.async_register("scene", "turn_on", handle_scene)
    await hass.services.async_call("scene", "turn_on", {"scene": "movie_time"})
    await hass.services.async_call("light", "turn_on", {"entity_id": "light.tv_backlight"})
    await hass.async_block_till_done()


_SCENARIOS = [
    ("01_Startup", _s1_startup),
    ("02_SetState", _s2_set_state),
    ("03_RegisterService", _s3_register_service),
    ("04_CallService", _s4_call_service),
    ("05_FireEvent", _s5_fire_event),
    ("06_StateListener", _s6_state_listener),
    ("07_MultipleStates", _s7_multiple_states),
    ("08_ServiceChain", _s8_service_chain),
]


class ExternalHomeAssistantRunner:
    def run(self, filter_engine: ArchitectureFilter) -> RunOutcome:
        tracer = new_tracer(filter_engine)
        warnings = []

        async def _exercise():
            hass = HomeAssistant("")
            tracer.start_trace()
            try:
                for name, scenario in _SCENARIOS:
                    try:
                        await scenario(hass)
                    except Exception as e:  # noqa: BLE001
                        warnings.append(f"{name}: {type(e).__name__}: {e}")
            finally:
                # Stop tracing (+ post-processing) BEFORE cleanup, so async_stop
                # isn't captured; then always tear the instance down.
                finalize(tracer)
                try:
                    await hass.async_stop()
                except Exception as e:  # noqa: BLE001
                    warnings.append(f"async_stop: {type(e).__name__}: {e}")

        # run() executes inside a worker thread (anyio.to_thread); each thread can
        # own its own event loop via asyncio.run().
        asyncio.run(_exercise())

        return RunOutcome(tracer=tracer, warnings=warnings)
