"""The room's irrigation strategy, sensor.crop_steering_strategy_plan, is a real entity. Home
Assistant's review of the Marketplace submission (hacs/default#13655) found it written with
hass.states.async_set, with no entity behind it: no registry entry or unique id, on no device, and
nobody could rename or disable it. It keeps its entity id, which the controller app, health.py and
run_store.py read."""

from datetime import datetime, timedelta

from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from ha_testing import async_fire_time_changed
from test_setup_entry import _install

DOMAIN = "crop_steering"
PLAN = "sensor.crop_steering_strategy_plan"
DESCRIPTOR = "sensor.crop_steering_engine_config"  # on the room's device
KILL = "switch.crop_steering_engine_enabled"


async def test_the_irrigation_strategy_is_an_entity_on_the_rooms_device(hass):
    entry = await _install(hass)
    registry = er.async_get(hass)
    item = registry.async_get(PLAN)
    assert item is not None  # a state written by hand has no registry entry
    assert (item.platform, item.unique_id) == (DOMAIN, f"{DOMAIN}_{entry.entry_id}_strategy_plan")
    assert item.config_entry_id == entry.entry_id
    assert item.device_id == registry.async_get(DESCRIPTOR).device_id
    assert item.original_name == "Irrigation strategy"
    state = hass.states.get(PLAN)
    assert state.state == "draft"
    assert state.name.endswith("Irrigation strategy")  # after the room's name, as Feed plan
    assert (state.attributes["snapshot_version"], state.attributes["room_id"]) == (1, "room:")


async def test_each_publish_reaches_the_entity_and_a_new_name_stays(hass):
    await _install(hass)
    er.async_get(hass).async_update_entity(PLAN, name="Strategy for the controller")
    await hass.async_block_till_done()
    before = hass.states.get(PLAN).attributes["updated_at"]
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))  # the minute's tick
    await hass.async_block_till_done()
    state = hass.states.get(PLAN)
    assert state.attributes["updated_at"] != before
    assert state.name.endswith("Strategy for the controller")


async def test_the_controller_finds_the_snapshot_for_its_room(hass, controller_for):
    await _install(hass)
    c, _fake, _clock = controller_for({"enable_flag": KILL})
    room = c.rooms[0]
    # As if a strategy had run: then a missing, stale or other room's snapshot is an error of its
    # own. This one is found, fresh and this room's, and a draft holds.
    room.strategy_required = True
    c._load_strategy_snapshot(room, datetime.now())
    assert room.strategy_snapshot["error"] == "Strategy is held; no current active snapshot"
