"""`trigger.entity_id` and `this.entity_id` are variables, not entities.

A triggered automation is handed `trigger`, a template entity is handed `this`.
Reported as unknown entities twice, #823 and #1468, and both times it was put
down to templates, which is why neither went anywhere.

Templates were never it. Written without the braces, as
`entity_id: trigger.entity_id`, Home Assistant puts them in the automation's own
`referenced_entities` and hands them straight over, past everything here that
reads configuration.

So these pin two separate things. That they are turned away at the last gate,
which is where the reported bug lives and where anything Home Assistant supplies
turns up. And that nothing picks them out of a template either, which holds
today only because neither is a domain Home Assistant knows, off a list that
grows every release and was never chosen with these in mind.
"""

# pylint: disable=wrong-import-order
# pylint: disable=protected-access
from __future__ import annotations

import re
from typing import TYPE_CHECKING

import yaml
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.setup import async_setup_component

from custom_components.spook import action_extraction, template_extraction
from custom_components.spook.action_extraction import (
    async_extract_entities_from_value,
)
from custom_components.spook.ectoplasms.automation.repairs.unknown_entity_references import (
    extract_entities_from_automation_config,
)
from custom_components.spook.dashboard_extraction import (
    extract_entities_from_dashboard_node,
)
from custom_components.spook.entity_filtering import async_filter_known_entity_ids
from custom_components.spook.template_extraction import (
    async_filter_known_entity_ids_with_templates,
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


# Written out here rather than read from the code under test. Reading the very
# set these tests are about means that taking an entry out of it takes it out
# of the yardstick too, and every assertion below keeps passing while the thing
# it guards is broken.
_THE_PLACEHOLDERS = frozenset({"trigger.entity_id", "this.entity_id"})


def _named(found: set[str]) -> set[str]:
    """Return anything reported that is one of the placeholders."""
    return {e for e in found if e in _THE_PLACEHOLDERS}


def test_the_yardstick_still_matches_the_code() -> None:
    """The copy above is deliberate, so say when it stops describing reality.

    A third placeholder worth excluding should be added to both. This failing
    is the reminder, not a bug in itself.
    """
    assert set(template_extraction.NEVER_AN_ENTITY) == _THE_PLACEHOLDERS


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


async def test_home_assistant_handing_them_over_does_not_count_either(
    hass: HomeAssistant,
) -> None:
    """Which is how this actually happens, and what both reports were.

    Written without the braces, `entity_id: trigger.entity_id` rather than
    `{{ trigger.entity_id }}`, Home Assistant puts them in the automation's own
    `referenced_entities`. Spook seeds from that set, so they arrive already
    past everything that reads configuration, and `valid_entity_id` waves them
    through because it asks whether a string is shaped like an entity ID, not
    whether anything answers to it.
    """
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "Literal trigger variable",
                    "id": "literal_trigger",
                    "triggers": [
                        {"trigger": "state", "entity_id": "binary_sensor.smoke"},
                    ],
                    "actions": [
                        {
                            "action": "light.turn_on",
                            "target": {"entity_id": "trigger.entity_id"},
                        },
                    ],
                },
                {
                    "alias": "Literal this variable",
                    "id": "literal_this",
                    "triggers": [
                        {"trigger": "state", "entity_id": "binary_sensor.smoke"},
                    ],
                    "conditions": [
                        {
                            "condition": "state",
                            "entity_id": "this.entity_id",
                            "state": "on",
                        },
                    ],
                    "actions": [{"action": "light.turn_on"}],
                },
            ],
        },
    )
    await hass.async_block_till_done()

    component = hass.data[DATA_INSTANCES]["automation"]
    entities = list(component.entities)
    assert entities, "no automations were set up, so this proves nothing"

    # Home Assistant really does hand them over. Without this the test could
    # pass by the pseudo-IDs never turning up in the first place.
    handed_over = set()
    for entity in entities:
        handed_over |= {str(e) for e in entity.referenced_entities}
    assert handed_over & set(template_extraction.NEVER_AN_ENTITY), (
        f"Home Assistant stopped reporting these, so this test is now testing "
        f"nothing: {sorted(handed_over)}"
    )

    for entity in entities:
        unknown = await async_filter_known_entity_ids_with_templates(
            hass,
            entity_ids=set(entity.referenced_entities),
            known_entity_ids={"binary_sensor.smoke"},
        )
        assert not _named(unknown), f"{entity.name} reported {sorted(unknown)}"


async def test_the_entity_dict_form_does_not_smuggle_them_in(
    hass: HomeAssistant,
) -> None:
    """`{"entity": "..."}` is a shape a target can take, and it went straight in."""
    found = await async_extract_entities_from_value(
        hass,
        [{"entity": "trigger.entity_id"}, {"entity": "light.real_one"}],
    )

    assert not _named(found)
    assert "light.real_one" in found, "the dict form stopped working altogether"


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


async def test_a_dashboard_does_not_report_them_either(
    hass: HomeAssistant,
) -> None:
    """Dashboards go through a filter of their own.

    `async_filter_known_entity_ids` is a separate function from the one
    automations use. Guarding only the automation side left this reported, and
    I had it fixed on paper for a while on the strength of them looking alike.

    Written outside a `filter:` here on purpose. The card it was reported from
    is no longer walked into at all, so a placeholder written anywhere else is
    what still reaches this gate, and this gate is what is being tested.
    """
    card = yaml.safe_load(
        """
        type: entities
        entities:
          - entity: this.entity_id
          - entity: sensor.real_one
        """,
    )

    extracted = extract_entities_from_dashboard_node(card)
    assert "this.entity_id" in extracted, (
        "the walk stopped collecting it, so this no longer tests the filter"
    )

    unknown = async_filter_known_entity_ids(
        hass,
        entity_ids=extracted,
        known_entity_ids={"sensor.real_one"},
    )

    assert not _named(unknown), f"a dashboard reported {sorted(unknown)}"


async def test_the_card_from_the_auto_entities_report_stays_quiet(
    hass: HomeAssistant,
) -> None:
    """The exact card from #1538, reported after the fix had already shipped.

    It was already quiet, but only by luck of the last gate: the walk does
    descend into `options:` inside a `filter:`, because that block is real
    card configuration rather than a matcher. So the placeholder is collected
    here and the filter is the only thing stopping it, which is worth pinning
    against the shape somebody actually wrote.
    """
    card = yaml.safe_load(
        """
        type: custom:auto-entities
        card:
          card:
            type: grid
            columns: 1
          card_param: cards
        filter:
          include:
            - options:
                type: custom:bubble-card
                card_type: button
                tap_action: toggle
                entity_id: this.entity_id
              entity_id: scene.szenen*
        """,
    )

    extracted = extract_entities_from_dashboard_node(card)
    assert "this.entity_id" in extracted, (
        "the walk stopped collecting it, so this no longer tests the filter"
    )

    unknown = async_filter_known_entity_ids(
        hass,
        entity_ids=extracted,
        known_entity_ids=set(),
    )

    assert "this.entity_id" not in unknown, f"a dashboard reported {sorted(unknown)}"


async def test_a_dashboard_still_reports_an_entity_that_really_is_gone(
    hass: HomeAssistant,
) -> None:
    """So the check above cannot pass by the dashboard filter reporting nothing."""
    unknown = async_filter_known_entity_ids(
        hass,
        entity_ids={"this.entity_id", "sensor.long_gone"},
        known_entity_ids={"sensor.real_one"},
    )

    assert unknown == {"sensor.long_gone"}


async def test_the_card_placeholder_from_the_discord_report_stays_quiet(
    hass: HomeAssistant,
) -> None:
    """`config.entity` is what a custom row calls its own entity.

    Reported on Discord against 5.2.0. Not from a template: inside one it was
    always safe, because `states(config.entity)` is a variable rather than a
    quoted string. It reaches the repair by being written into an `entity:`
    field, which is how these cards say "whichever entity this row is".
    """
    card = yaml.safe_load(
        """
        type: custom:auto-entities
        filter:
          include:
            - options:
                type: custom:template-entity-row
                entity: config.entity
              entity_id: sensor.afval*
        """,
    )

    extracted = extract_entities_from_dashboard_node(card)
    assert "config.entity" not in extracted, "the dashboard walk collected it"

    unknown = async_filter_known_entity_ids(
        hass,
        entity_ids=extracted,
        known_entity_ids=set(),
    )

    assert "config.entity" not in unknown, f"a dashboard reported {sorted(unknown)}"


async def test_a_template_using_the_card_placeholder_was_never_the_problem(
    hass: HomeAssistant,
) -> None:
    """Written inside a template it is a variable, and nothing here reads one.

    Worth pinning, because both people who reported this were looking at their
    templates, and that is not where it came from.
    """
    card = yaml.safe_load(
        """
        type: custom:template-entity-row
        entity: sensor.real_one
        state: "{{ states(config.entity) }}"
        secondary: "{% if is_state(config.entity, 'on') %}on{% endif %}"
        """,
    )

    extracted = extract_entities_from_dashboard_node(card)
    assert "config.entity" not in extracted

    unknown = async_filter_known_entity_ids(
        hass,
        entity_ids=extracted,
        known_entity_ids={"sensor.real_one"},
    )

    assert not unknown


async def test_the_card_placeholder_is_only_exempt_in_dashboards(
    hass: HomeAssistant,
) -> None:
    """`config.entity` means something to a card and nothing anywhere else.

    Nine repairs read `NEVER_AN_ENTITY`, so putting it there would have made a
    literal `config.entity` in a scene or a customization go unreported, and
    there it is a dangling reference like any other. The exemption belongs to
    the walk that knows it is looking at a dashboard.
    """
    assert "config.entity" not in async_filter_known_entity_ids(
        hass,
        entity_ids=extract_entities_from_dashboard_node(
            {"type": "custom:template-entity-row", "entity": "config.entity"}
        ),
        known_entity_ids=set(),
    )

    # Anywhere else it is still an entity nobody has.
    assert "config.entity" in async_filter_known_entity_ids(
        hass,
        entity_ids={"config.entity"},
        known_entity_ids=set(),
    )
