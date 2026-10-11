"""Tests for template lookups by area, floor or label that find nothing.

`area_entities`, `floor_areas`, `label_entities` and friends hand back an
empty list when they find no area, floor or label for what they are given.
The unknown area, floor and label repairs of automations and scripts report
a literal like that, resolved the way each lookup resolves it.
"""

# pylint: disable=wrong-import-order,protected-access
# ruff: noqa: SLF001
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.entity_filtering import (
    async_template_areas_not_found,
    async_template_floors_not_found,
    async_template_labels_not_found,
)
import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Which repair reports what each lookup finds nothing for.
_KIND_OF = {
    "area_devices": "area",
    "area_entities": "area",
    "floor_areas": "floor",
    "floor_entities": "floor",
    "label_areas": "label",
    "label_devices": "label",
    "label_entities": "label",
}

_NOT_FOUND = {
    "area": async_template_areas_not_found,
    "floor": async_template_floors_not_found,
    "label": async_template_labels_not_found,
}

# Replaced by the ID of the device in the living room once it exists.
_DEVICE = "DEVICE"


@pytest.fixture
async def house(hass: HomeAssistant) -> str:
    """Build a house where every lookup that finds something finds a lot.

    Upstairs holds the living room, and an area called Attic. The floor
    called Attic holds the loft. The floor called Garage holds the
    workshop, and an area called Garage sits on no floor. The living room,
    a lamp and its device carry the Christmas lights label.

    Returns the ID of the device in the living room.
    """
    area_registry = ar.async_get(hass)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    floor_registry = fr.async_get(hass)
    label_registry = lr.async_get(hass)

    label = label_registry.async_create("Christmas Lights")
    upstairs = floor_registry.async_create("Upstairs", aliases={"Boven"})
    attic = floor_registry.async_create("Attic")
    garage = floor_registry.async_create("Garage")

    living_room = area_registry.async_create(
        "Living Room",
        aliases={"Lounge"},
        floor_id=upstairs.floor_id,
        labels={label.label_id},
    )
    area_registry.async_create("Attic", floor_id=upstairs.floor_id)
    loft = area_registry.async_create("Loft", floor_id=attic.floor_id)
    workshop = area_registry.async_create("Workshop", floor_id=garage.floor_id)
    area_registry.async_create("Garage")

    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "lamp")}
    )
    device_registry.async_update_device(
        device.id, area_id=living_room.id, labels={label.label_id}
    )
    for area, name in ((living_room, "kitchen"), (loft, "loft"), (workshop, "bench")):
        lamp = entity_registry.async_get_or_create(
            "light",
            "test",
            name,
            device_id=device.id if name == "kitchen" else None,
            original_name=name.title(),
        )
        entity_registry.async_update_entity(
            lamp.entity_id, area_id=area.id, labels={label.label_id}
        )

    return device.id


async def _unknown(
    hass: HomeAssistant,
    domain: str,
    kind: str,
    template: str,
    extra: dict[str, Any] | None = None,
) -> set[str]:
    """Set up a real automation or script using a template, and ask the repair.

    Anything in `extra`, like variables or disabled steps, goes into its
    configuration as well.
    """
    sequence = [
        {
            "action": "persistent_notification.create",
            "data": {"message": template},
        },
        *(extra or {}).pop("steps", []),
    ]
    if domain == "automation":
        config = {
            "automation": {
                "id": "lookup",
                "alias": "lookup",
                "triggers": [{"trigger": "event", "event_type": "go"}],
                "actions": sequence,
                **(extra or {}),
            }
        }
    else:
        config = {"script": {"lookup": {"sequence": sequence, **(extra or {})}}}

    assert await async_setup_component(hass, domain, config)
    await hass.async_block_till_done()

    module = importlib.import_module(
        f"custom_components.spook.ectoplasms.{domain}.repairs.unknown_{kind}_references"
    )
    repair = module.SpookRepair(hass)
    await repair._async_setup_inspection()
    return await repair._async_compute_unknown_references(
        hass.data[domain].get_entity(f"{domain}.lookup")
    )


# Each lookup, what it is handed, and whether it finds nothing.
_LOOKUPS = [
    # By area ID, or by name or alias in any case and spacing.
    *(
        (function, value, False)
        for function in ("area_entities", "area_devices")
        for value in ("living_room", "Living Room", "living room", "LivingRoom")
    ),
    ("area_entities", "Lounge", False),
    ("area_devices", "LOUNGE", False),
    ("area_entities", "Kitchen", True),
    ("area_devices", "Kitchen", True),
    # An ID is not a name: in another case it is neither.
    ("area_entities", "Living_Room", True),
    # Only areas. An entity or device in one is taken as an area ID.
    ("area_entities", "light.test_kitchen", True),
    ("area_devices", "light.test_kitchen", True),
    ("area_entities", _DEVICE, True),
    ("area_devices", _DEVICE, True),
    # By floor ID, or by name or alias in any case and spacing.
    *(
        (function, value, False)
        for function in ("floor_areas", "floor_entities")
        for value in ("upstairs", "Upstairs", "UP STAIRS", "Boven", "boven")
    ),
    ("floor_areas", "Basement", True),
    ("floor_entities", "Basement", True),
    # An area on a floor, by name or alias, is taken as a floor ID.
    ("floor_areas", "Living Room", True),
    ("floor_entities", "Lounge", True),
    # So is a floor name that an area on a floor has too. Its ID works.
    ("floor_areas", "Attic", True),
    ("floor_entities", "Attic", True),
    ("floor_areas", "attic", False),
    ("floor_entities", "attic", False),
    # An area by that name on no floor leaves the floor name be.
    ("floor_areas", "Garage", False),
    ("floor_entities", "garage", False),
    # An entity or device never finds a floor.
    ("floor_areas", "light.test_kitchen", True),
    ("floor_entities", _DEVICE, True),
    # By label ID, or by name in any case and spacing.
    *(
        (function, value, False)
        for function in ("label_areas", "label_devices", "label_entities")
        for value in ("christmas_lights", "Christmas Lights", "christmaslights")
    ),
    ("label_areas", "Holiday", True),
    ("label_devices", "Holiday", True),
    ("label_entities", "Holiday", True),
    ("label_entities", "light.test_kitchen", True),
]


@pytest.mark.parametrize("lookup", _LOOKUPS)
async def test_premise(
    hass: HomeAssistant, house: str, lookup: tuple[str, str, bool]
) -> None:
    """Test the premise: Home Assistant finds nothing for exactly these."""
    function, value, nothing = lookup
    value = value.replace(_DEVICE, house)

    rendered = Template(f"{{{{ {function}('{value}') }}}}", hass).async_render()

    assert (rendered == []) is nothing


@pytest.mark.parametrize("lookup", _LOOKUPS)
async def test_value_is_resolved_like_core(
    hass: HomeAssistant, house: str, lookup: tuple[str, str, bool]
) -> None:
    """Each value is resolved the way the lookup resolves it, IDs included.

    The repairs leave out known IDs on their own as well, so this asks the
    resolving itself.
    """
    function, value, nothing = lookup
    value = value.replace(_DEVICE, house)

    not_found = _NOT_FOUND[_KIND_OF[function]](hass, {value})

    assert not_found == ({value} if nothing else set())


@pytest.mark.parametrize("domain", ["automation", "script"])
@pytest.mark.parametrize("lookup", _LOOKUPS)
async def test_lookup_that_finds_nothing_is_reported(
    hass: HomeAssistant,
    house: str,
    domain: str,
    lookup: tuple[str, str, bool],
) -> None:
    """A literal the lookup finds nothing for is reported, and only that."""
    function, value, nothing = lookup
    value = value.replace(_DEVICE, house)

    unknown = await _unknown(
        hass, domain, _KIND_OF[function], f"{{{{ {function}('{value}') }}}}"
    )

    assert unknown == ({value} if nothing else set())


@pytest.mark.parametrize("domain", ["automation", "script"])
@pytest.mark.parametrize(
    ("kind", "template"),
    [
        ("area", "{{ area_entities('Ghost') }}"),
        ("area", '{{ area_devices ( "Ghost" ) | list }}'),
        ("area", "{{ area_entities(area_id_or_name='Ghost') }}"),
        ("area", "{{ ('Ghost') | area_entities }}"),
        ("area", "{{ 'Ghost' | area_devices() }}"),
        ("floor", "{{ 'Ghost' | floor_areas }}"),
        ("floor", "{{ floor_entities('Ghost') | count }}"),
        ("label", "{{ 'Ghost' | label_entities }}"),
        ("label", "{{ label_devices('Ghost') }}"),
        ("label", "{{ label_areas(label_id_or_name='Ghost') }}"),
        # A name of the template's own hides the function, not the filter.
        ("area", "{% set area_entities = 1 %}{{ 'Ghost' | area_entities }}"),
        (
            "label",
            "{% macro label_entities(x) %}{% endmacro %}{{ 'Ghost' | label_entities }}",
        ),
    ],
)
@pytest.mark.usefixtures("house")
async def test_literal_is_read_in_every_form(
    hass: HomeAssistant, domain: str, kind: str, template: str
) -> None:
    """Called, by keyword, or as a filter, a literal is read."""
    assert await _unknown(hass, domain, kind, template) == {"Ghost"}


@pytest.mark.parametrize("domain", ["automation", "script"])
@pytest.mark.parametrize(
    ("kind", "template"),
    [
        # Worked out while running.
        ("area", "{{ area_entities('Gho' ~ 'st') }}"),
        ("area", "{{ area_entities('Gho' 'st') }}"),
        ("area", "{{ 'x' 'Ghost' | area_entities }}"),
        ("area", "{% set room = 'Ghost' %}{{ area_entities(room) }}"),
        ("floor", "{{ floor_areas(area_id('Ghost')) }}"),
        ("label", "{{ ('Ghost' | lower) | label_entities }}"),
        # Not the lookup: another function, a method, text, a string.
        ("area", "{{ my_area_entities('Ghost') }}"),
        ("area", "{{ AREA_ENTITIES('Ghost') }}"),
        ("area", "{{ this.area_entities('Ghost') }}"),
        ("floor", "{{ this . floor_areas('Ghost') }}"),
        ("label", "label_entities('Ghost') {{ 1 }}"),
        ("label", "{{ \"label_entities('Ghost')\" }}"),
        ("label", "{% raw %}{{ label_entities('Ghost') }}{% endraw %}"),
        # A name of the template's own, by the same name.
        (
            "area",
            "{% macro area_entities(x) %}{% endmacro %}{{ area_entities('Ghost') }}",
        ),
        ("floor", "{% set floor_areas = namespace() %}{{ floor_areas('Ghost') }}"),
        (
            "label",
            "{% for label_devices in [] %}{% endfor %}{{ label_devices('Ghost') }}",
        ),
        # They take one value and nothing more, so these fail.
        ("area", "{{ area_entities('Ghost', 'x') }}"),
        ("area", "{{ area_entities(name='Ghost') }}"),
        ("floor", "{{ 'Ghost' | floor_areas('x') }}"),
        # None of them is a test, and a dotted filter is another one.
        ("label", "{{ 'x' is label_entities('Ghost') }}"),
        ("label", "{{ 'Ghost' | label_entities.x }}"),
    ],
)
@pytest.mark.usefixtures("house")
async def test_lookup_that_is_not_a_literal_is_not_read(
    hass: HomeAssistant, domain: str, kind: str, template: str
) -> None:
    """Only a whole literal handed to the very lookup is read."""
    assert await _unknown(hass, domain, kind, template) == set()


# Each place a configuration gives its templates a name, as the domain it
# goes with and what goes into its configuration.
_NAMES = ("area_entities", "floor_areas", "label_entities")
_GIVEN_NAMES = pytest.mark.parametrize(
    ("domain", "extra"),
    [
        ("automation", {"variables": dict.fromkeys(_NAMES, 1)}),
        ("script", {"variables": dict.fromkeys(_NAMES, 1)}),
        ("script", {"fields": {name: {} for name in _NAMES}}),
    ],
    ids=["automation variables", "script variables", "script fields"],
)


@_GIVEN_NAMES
@pytest.mark.parametrize(
    ("kind", "template"),
    [
        ("area", "{{ area_entities('Ghost') }}"),
        ("floor", "{{ floor_areas('Ghost') }}"),
        ("label", "{{ label_entities('Ghost') }}"),
    ],
)
@pytest.mark.usefixtures("house")
async def test_lookup_called_by_a_name_the_configuration_gives_is_not_read(
    hass: HomeAssistant,
    domain: str,
    extra: dict[str, Any],
    kind: str,
    template: str,
) -> None:
    """A call by a name the configuration took over is not Home Assistant's."""
    assert await _unknown(hass, domain, kind, template, extra) == set()


@_GIVEN_NAMES
@pytest.mark.parametrize(
    ("kind", "template"),
    [
        ("area", "{{ 'Ghost' | area_entities }}"),
        ("floor", "{{ 'Ghost' | floor_areas }}"),
        ("label", "{{ 'Ghost' | label_entities }}"),
    ],
)
@pytest.mark.usefixtures("house")
async def test_lookup_filter_the_configuration_names_is_read(
    hass: HomeAssistant,
    domain: str,
    extra: dict[str, Any],
    kind: str,
    template: str,
) -> None:
    """A name the configuration gives hides no filter: Jinja keeps those apart."""
    assert await _unknown(hass, domain, kind, template, extra) == {"Ghost"}


@pytest.mark.parametrize("domain", ["automation", "script"])
@pytest.mark.parametrize(
    ("kind", "function"),
    [("area", "area_entities"), ("floor", "floor_areas"), ("label", "label_entities")],
)
@pytest.mark.usefixtures("house")
async def test_lookup_only_in_a_disabled_step_is_left_out(
    hass: HomeAssistant, domain: str, kind: str, function: str
) -> None:
    """A disabled step does nothing, so what only it looks up is not reported."""
    disabled = {
        "enabled": False,
        "action": "persistent_notification.create",
        "data": {"message": f"{{{{ {function}('Parked') }}}}"},
    }

    unknown = await _unknown(
        hass,
        domain,
        kind,
        f"{{{{ {function}('Ghost') }}}}",
        {"steps": [disabled]},
    )

    assert unknown == {"Ghost"}


@pytest.mark.parametrize("domain", ["automation", "script"])
def test_floor_repair_looks_again_when_areas_change(domain: str) -> None:
    """A floor lookup goes through areas first, so a renamed area matters."""
    module = importlib.import_module(
        f"custom_components.spook.ectoplasms.{domain}.repairs.unknown_floor_references"
    )

    assert ar.EVENT_AREA_REGISTRY_UPDATED in module.SpookRepair.inspect_events
