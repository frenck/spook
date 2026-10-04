"""Tests for the todo.move_item action."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform
from homeassistant.exceptions import ServiceNotSupported, ServiceValidationError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.todo.services.move_item import SpookService

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback,
    )


class FakeList(TodoListEntity):
    """A to-do list that can be reordered, and keeps its order in a list."""

    _attr_should_poll = False
    _attr_supported_features = TodoListEntityFeature.MOVE_TODO_ITEM

    def __init__(self, name: str, *summaries: str) -> None:
        """Initialize the list, an item per summary, its uid the summary lowered."""
        self._attr_name = name
        self._attr_unique_id = name
        self._attr_todo_items = [
            TodoItem(
                summary=summary,
                uid=summary.lower(),
                status=TodoItemStatus.NEEDS_ACTION,
            )
            for summary in summaries
        ]

    @property
    def order(self) -> list[str]:
        """Return the titles, in the order they are in."""
        return [item.summary or "" for item in self._attr_todo_items or ()]

    async def async_move_todo_item(
        self, uid: str, previous_uid: str | None = None
    ) -> None:
        """Move an item to after another one, or to the top."""
        items = list(self._attr_todo_items or ())
        moving = next(item for item in items if item.uid == uid)
        items.remove(moving)
        index = (
            0
            if previous_uid is None
            else next(i for i, item in enumerate(items) if item.uid == previous_uid) + 1
        )
        items.insert(index, moving)
        self._attr_todo_items = items
        self.async_write_ha_state()


class FakeFixedList(FakeList):
    """A to-do list that keeps its items in an order of its own."""

    _attr_supported_features = TodoListEntityFeature(0)


async def _setup(hass: HomeAssistant, *lists: TodoListEntity) -> None:
    """Set up these lists and the action."""
    assert await async_setup_component(hass, "homeassistant", {})

    async def _setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.TODO])
        return True

    async def _setup_platform(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
        add: AddConfigEntryEntitiesCallback,
    ) -> None:
        add(list(lists))

    mock_integration(hass, MockModule("fake", async_setup_entry=_setup_entry))
    mock_platform(hass, "fake.config_flow")
    mock_platform(hass, "fake.todo", MockPlatform(async_setup_entry=_setup_platform))

    class _Flow(ConfigFlow, domain="fake"):
        """A config flow that does nothing."""

    with mock_config_flow("fake", _Flow):
        entry = MockConfigEntry(domain="fake")
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    SpookService(hass).async_register()
    await hass.async_block_till_done()


async def _move(
    hass: HomeAssistant, entity_id: str = "todo.chores", **data: Any
) -> None:
    """Move an item."""
    await hass.services.async_call(
        "todo", "move_item", {"entity_id": entity_id, **data}, blocking=True
    )


@pytest.mark.parametrize(
    ("where", "order"),
    [
        ({"position": "top"}, ["Dishes", "Bins", "Laundry"]),
        ({"position": "bottom"}, ["Bins", "Laundry", "Dishes"]),
        ({"after": "Bins"}, ["Bins", "Dishes", "Laundry"]),
    ],
)
async def test_an_item_goes_where_it_is_told(
    hass: HomeAssistant, where: dict[str, str], order: list[str]
) -> None:
    """Test the top, the bottom, and after another item."""
    chores = FakeList("chores", "Bins", "Laundry", "Dishes")
    await _setup(hass, chores)

    await _move(hass, item="Dishes", **where)

    assert chores.order == order


async def test_items_are_found_by_uid_too(hass: HomeAssistant) -> None:
    """Test a uid finds an item as well as its title, like `todo.update_item`."""
    chores = FakeList("chores", "Bins", "Laundry", "Dishes")
    await _setup(hass, chores)

    await _move(hass, item="dishes", after="bins")

    assert chores.order == ["Bins", "Dishes", "Laundry"]


@pytest.mark.parametrize(
    "data",
    [
        {"item": "Hoovering", "position": "top"},
        {"item": "Dishes", "after": "Hoovering"},
        {"item": "Dishes", "after": "Dishes"},
        {"item": "Dishes"},
    ],
)
async def test_what_cannot_be_done_is_refused(
    hass: HomeAssistant, data: dict[str, str]
) -> None:
    """Test an unknown item, an unknown place, itself, and nowhere at all."""
    chores = FakeList("chores", "Bins", "Laundry", "Dishes")
    await _setup(hass, chores)

    with pytest.raises(ServiceValidationError):
        await _move(hass, **data)

    assert chores.order == ["Bins", "Laundry", "Dishes"]


async def test_after_and_a_position_together_are_refused(
    hass: HomeAssistant,
) -> None:
    """Test saying where twice is refused."""
    await _setup(hass, FakeList("chores", "Bins", "Dishes"))

    with pytest.raises(vol.Invalid):
        await _move(hass, item="Dishes", after="Bins", position="top")


async def test_a_list_that_cannot_be_reordered_refuses(hass: HomeAssistant) -> None:
    """Test a list that keeps an order of its own says so."""
    await _setup(hass, FakeFixedList("chores", "Bins", "Dishes"))

    with pytest.raises(ServiceNotSupported):
        await _move(hass, item="Dishes", position="top")
