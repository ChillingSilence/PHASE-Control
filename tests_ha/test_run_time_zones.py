"""A run names its time zone, and the first ZoneInfo for a name reads the time zone database from
disk: Home Assistant's review of the Marketplace submission (hacs/default#13655) found the run store
doing that on the event loop. Here a real Home Assistant registers a run, imports one from another
time zone and refuses names that are no time zone, while every time zone file the process opens is
noted with whether the event loop opened it."""

import re
import sys
import threading
import zoneinfo

import pytest
from homeassistant.exceptions import HomeAssistantError
from test_setup_entry import _install

DOMAIN = "crop_steering"
ROOM = "room:"
RUN = {"name": "Trial A", "start_date": "2026-05-01", "end_date": "2026-07-31"}
# A time zone nothing else here, or in Home Assistant, reads.
ELSEWHERE = "Pacific/Chatham"
_listening = []


def _audit(event, args):
    if event == "open" and _listening and "zoneinfo" in str(args[0]):
        for note in _listening:
            note(str(args[0]))


@pytest.fixture
def zone_files(hass):
    """Each time zone file opened from here on, as (path, opened on the event loop)."""
    if not getattr(_audit, "added", False):
        # An audit hook cannot be removed again; this one notes nothing unless a test listens.
        sys.addaudithook(_audit)
        _audit.added = True
    files = []

    def note(path):
        files.append((path, threading.get_ident() == hass.loop_thread_id))

    _listening.append(note)
    yield files
    _listening.remove(note)


async def _runs(hass, service, **data):
    return await hass.services.async_call(
        DOMAIN, service, {"room_id": ROOM, **data}, blocking=True, return_response=True
    )


async def test_time_zones_are_read_off_the_event_loop(hass, zone_files):
    zoneinfo.ZoneInfo.clear_cache(only_keys=[ELSEWHERE])  # so the import reads its file
    await _install(hass)
    saved = await _runs(hass, "runs_save", expected_revision=0, record=RUN)
    run = dict(saved["runs"][0], id="elsewhere", time_zone=ELSEWHERE)
    imported = await _runs(hass, "runs_import", expected_revision=1, runs=[run])
    assert [r["time_zone"] for r in imported["runs"]] == [hass.config.time_zone, ELSEWHERE]
    assert [path for path, _ in zone_files if path.endswith(ELSEWHERE)], zone_files  # was read
    assert [path for path, on_loop in zone_files if on_loop] == []  # none on the event loop


@pytest.mark.parametrize("name", ["Mars/Olympus", "../etc/passwd", "/etc/localtime"])
async def test_a_run_in_no_time_zone_is_refused(hass, name):
    # Before Home Assistant 2026.11, async_get_time_zone raises ValueError for a malformed name.
    await _install(hass)
    saved = await _runs(hass, "runs_save", expected_revision=0, record=RUN)
    run = dict(saved["runs"][0], id="nowhere", time_zone=name)
    with pytest.raises(HomeAssistantError, match=re.escape(f"Unknown time zone: {name}")):
        await _runs(hass, "runs_import", expected_revision=1, runs=[run])
