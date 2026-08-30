"""`trigger.entity_id` and `this.entity_id` are variables, not entities.

A triggered automation is handed `trigger`, a template entity is handed `this`,
and `{{ device_name(trigger.entity_id) }}` is the ordinary way to write either.
Reported as an unknown entity twice, #823 and #1468, and neither time was it
reproducible.

Nothing here has ever picked them up, because neither `trigger` nor `this` is a
domain Home Assistant knows. Which is the trouble: that list grows every release
and nobody chose it as the thing keeping these out. These tests pin the answer
rather than the accident.
"""

# pylint: disable=wrong-import-order
# pylint: disable=protected-access
from __future__ import annotations

import re
from typing import TYPE_CHECKING

import yaml

from custom_components.spook import action_extraction, template_extraction
from custom_components.spook.action_extraction import (
    async_extract_entities_from_value,
)
from custom_components.spook.ectoplasms.automation.repairs.unknown_entity_references import (
    extract_entities_from_automation_config,
)

if TYPE_CHECKING:
    import pytest

    from homeassistant.core import HomeAssistant

# Every way somebody writes one of these, and one real entity alongside so the
# checks below cannot pass by finding nothing at all.
_WRITTEN_AS = [
    "trigger.entity_id",
    "this.entity_id",
    "{{ trigger.entity_id }}",
    "{{ this.entity_id }}",
    "{{ device_name(trigger.entity_id) }}",
    "{{ device_name('trigger.entity_id') }}",
    "{{ state_attr(this.entity_id, 'friendly_name') }}",
    "{{ expand(trigger.entity_id) }}",
    "{{ device_name(trigger.entity_id) }} and {{ states('sensor.real_one') }}",
]

# The automation from #1468, cut down to the part that matters.
_SMOKE_ALARM = """
alias: Notify if Smoke Alarm
triggers:
  - entity_id:
      - binary_sensor.room1_smoke
      - binary_sensor.room2_smoke
    trigger: state
    to:
      - "on"
actions:
  - action: notify.mobile_app_foo_bar
    data:
      message: "{{ device_name(trigger.entity_id) }} detected SMOKE!"
      title: "Fire Alert @ {{ area_name(trigger.entity_id) }}"
mode: restart
"""


def _named(found: set[str]) -> set[str]:
    """Return anything reported that is one of the two variables."""
    return {e for e in found if e in template_extraction.NEVER_AN_ENTITY}


async def test_no_way_of_writing_them_reads_as_an_entity(
    hass: HomeAssistant,
) -> None:
    """However they are written, in a template or bare in a config value."""
    for written in _WRITTEN_AS:
        found = await async_extract_entities_from_value(hass, written)
        assert not _named(found), f"{written!r} was read as an entity: {sorted(found)}"

    # The real entity in the last one still comes through, so the loop above is
    # not passing by finding nothing anywhere.
    assert "sensor.real_one" in await async_extract_entities_from_value(
        hass,
        _WRITTEN_AS[-1],
    )


async def test_the_automation_from_the_issue_reports_only_its_sensors(
    hass: HomeAssistant,
) -> None:
    """#1468, as pasted. Six smoke detectors and a template naming the one that went."""
    found = await extract_entities_from_automation_config(
        hass,
        yaml.safe_load(_SMOKE_ALARM),
    )

    assert found == {"binary_sensor.room1_smoke", "binary_sensor.room2_smoke"}


async def test_they_stay_out_even_if_the_domains_ever_let_them_in(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Which is the whole point of naming them rather than leaving it to luck.

    `trigger` and `this` are kept out today by not being domains Home Assistant
    knows. That list is `Platform` plus a handful, it grows every release, and
    nothing about it was chosen with these in mind. So: let them through it, and
    check they are still turned away.
    """
    domains = [*template_extraction.KNOWN_DOMAINS, "trigger", "this"]
    pattern = r"(?:" + "|".join(domains) + r")\." + template_extraction._OBJECT_ID  # noqa: SLF001

    monkeypatch.setattr(
        template_extraction,
        "COMPILED_ENTITY_ID_TEMPLATE_PATTERNS",
        tuple(
            re.compile(
                p.pattern.replace(template_extraction.ENTITY_ID_PATTERN, pattern),
                re.IGNORECASE,
            )
            for p in template_extraction.COMPILED_ENTITY_ID_TEMPLATE_PATTERNS
        ),
    )
    monkeypatch.setattr(
        action_extraction,
        "_ENTITY_ID_RE",
        re.compile(rf"^{pattern}$"),
    )
    template_extraction._extract_entity_candidates_from_template.cache_clear()  # noqa: SLF001

    for written in _WRITTEN_AS:
        found = await async_extract_entities_from_value(hass, written)
        assert not _named(found), f"{written!r} got through: {sorted(found)}"

    template_extraction._extract_entity_candidates_from_template.cache_clear()  # noqa: SLF001
