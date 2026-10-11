"""Tests for the Lovelace unknown themes repair."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.components.frontend import DATA_THEMES
from homeassistant.components.lovelace.const import ConfigNotFound
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.spook.ectoplasms.lovelace.repairs.unknown_theme_references import (
    SpookRepair,
)
import pytest
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE = "lovelace_unknown_theme_references_lovelace"

# The themes every test starts with, as they would be in `configuration.yaml`.
# One light and dark, one dark only, so the variants are covered too.
_THEMES = {
    "Midnight": {"primary-color": "#000033"},
    "Sunrise": {
        "modes": {
            "light": {"primary-color": "#ffaa00"},
            "dark": {"primary-color": "#aa5500"},
        },
    },
}


@pytest.fixture(autouse=True)
async def frontend_with_themes(hass: HomeAssistant, tmp_path: Path) -> None:
    """Set up the frontend with its themes, the way Home Assistant does.

    The frontend's files are not installed for the tests, so it is pointed at
    an empty development checkout instead. Themes do not care either way.
    """
    (tmp_path / "hass_frontend").mkdir()
    assert await async_setup_component(
        hass,
        "frontend",
        {"frontend": {"development_repo": str(tmp_path), "themes": _THEMES}},
    )


def _dashboard(config: dict[str, Any] | None) -> SimpleNamespace:
    """Return the default dashboard with this config, or none stored."""

    async def async_load(*, force: bool) -> dict[str, Any]:
        """Return the dashboard config."""
        del force
        if config is None:
            raise ConfigNotFound
        return config

    return SimpleNamespace(
        url_path="lovelace", config={"title": "Overview"}, async_load=async_load
    )


def _with(*cards: Any, **view: Any) -> dict[str, Any]:
    """Return a dashboard with these cards on its second view."""
    return {
        "views": [
            {"path": "home", "cards": []},
            {"path": "night", "cards": list(cards), **view},
        ]
    }


def _bulleted(*themes: str) -> str:
    """Return the list of themes as the issue puts it."""
    return "\n".join(f"- `{theme}`" for theme in themes)


async def _async_settle(hass: HomeAssistant) -> None:
    """Let the repair's debouncer run what was asked of it."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()


async def _async_activate(hass: HomeAssistant, config: dict[str, Any]) -> SpookRepair:
    """Activate the repair on a house with one dashboard, and let it look."""
    hass.data["lovelace"] = SimpleNamespace(dashboards={"lovelace": _dashboard(config)})

    repair = SpookRepair(hass)
    await repair.async_activate()
    await _async_settle(hass)
    return repair


async def _async_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    config: dict[str, Any],
) -> str | None:
    """Return the themes the issue on this dashboard lists, if there is one.

    The look is run straight rather than through the debouncer, so a look
    that trips over something fails the test instead of only being logged.
    """
    repair = SpookRepair(hass)
    repair._dashboards = {"lovelace": _dashboard(config)}  # noqa: SLF001
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    if (issue := async_issue_about(issue_registry, _ISSUE)) is None:
        return None
    assert issue.translation_placeholders
    return issue.translation_placeholders["themes"]


async def test_card_with_a_missing_theme_creates_an_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a card naming a theme that is gone is reported, by the view it is on."""
    # A theme that exists on the first view, so the edit link has to skip it.
    config = _with({"type": "entities", "theme": "Midnight Blue", "entities": []})
    config["views"][0]["cards"] = [
        {"type": "entities", "theme": "Midnight", "entities": []}
    ]
    repair = await _async_activate(hass, config)
    await repair.async_deactivate()

    issue = async_issue_about(issue_registry, _ISSUE)
    assert issue
    assert issue.translation_key == "lovelace_unknown_theme_references"
    assert issue.translation_placeholders == {
        "themes": "- `Midnight Blue`",
        "dashboard": "Overview",
        "edit": "/lovelace/night?edit=1",
    }


async def test_every_card_that_puts_on_a_theme_is_checked(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test each core card that calls `applyThemesOnElement` is read."""
    # Each card type next to the frontend card whose `applyThemesOnElement`
    # call puts on its theme. Written out here, not taken from the code, so
    # a card dropped there fails this test.
    theme_applied_by = {
        "alarm-panel": "hui-alarm-panel-card",
        "button": "hui-button-card",
        "calendar": "hui-calendar-card",
        "entities": "hui-entities-card",
        "entity": "hui-entity-card",
        "entity-button": "hui-button-card",
        "gauge": "hui-gauge-card",
        "glance": "hui-glance-card",
        "humidifier": "hui-humidifier-card",
        "light": "hui-light-card",
        "logbook": "hui-logbook-card",
        "markdown": "hui-markdown-card",
        "media-control": "hui-media-control-card",
        "picture": "hui-picture-card",
        "picture-elements": "hui-picture-elements-card",
        "picture-entity": "hui-picture-entity-card",
        "picture-glance": "hui-picture-glance-card",
        "plant-status": "hui-plant-status-card",
        "sensor": "hui-entity-card",
        "shopping-list": "hui-todo-list-card",
        "statistic": "hui-statistic-card",
        "thermostat": "hui-thermostat-card",
        "todo-list": "hui-todo-list-card",
        "weather-forecast": "hui-weather-forecast-card",
    }

    assert await _async_reported(
        hass,
        issue_registry,
        _with(*({"type": kind, "theme": f"Gone {kind}"} for kind in theme_applied_by)),
    ) == "\n".join(f"- `Gone {kind}`" for kind in sorted(theme_applied_by))


async def test_cards_that_ignore_a_theme_are_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a theme on a card that never puts one on is not reported.

    The tile card and the stacks have no theme to put on, so a name there
    that is gone changes nothing.
    """
    assert (
        await _async_reported(
            hass,
            issue_registry,
            _with(
                {"type": "tile", "entity": "light.bed", "theme": "Gone"},
                {"type": "vertical-stack", "theme": "Gone", "cards": []},
                {"type": "heading", "theme": "Gone"},
            ),
        )
        is None
    )


async def test_cards_only_containers_put_on_are_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a `cards` or `card` key on a card that holds no cards is not read.

    Only the stacks, the grid, the conditional and the entity filter card put
    on the cards they hold. Any other card leaves such a key alone.
    """
    assert (
        await _async_reported(
            hass,
            issue_registry,
            _with(
                {
                    "type": "entities",
                    "entities": [],
                    "cards": [{"type": "markdown", "theme": "Gone"}],
                    "card": {"type": "markdown", "theme": "Gone"},
                },
                {
                    "type": "grid",
                    "cards": [],
                    "card": {"type": "markdown", "theme": "Gone"},
                },
                {
                    "type": "conditional",
                    "conditions": [],
                    "cards": [{"type": "markdown", "theme": "Gone"}],
                },
            ),
        )
        is None
    )


async def test_view_and_section_themes_are_checked(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the view's own theme, its sections and its sidebar's are read."""
    config = {
        "views": [
            {"path": "home", "cards": []},
            {
                "path": "night",
                "type": "sections",
                "theme": "Gone view",
                "sections": [
                    {
                        "type": "grid",
                        "theme": "Gone section",
                        "cards": [{"type": "markdown", "theme": "Gone card"}],
                    },
                    # No type is a grid section.
                    {"theme": "Gone untyped section", "cards": []},
                ],
                "sidebar": {
                    "sections": [{"type": "grid", "theme": "Gone sidebar section"}]
                },
            },
        ]
    }

    assert await _async_reported(hass, issue_registry, config) == _bulleted(
        "Gone card",
        "Gone section",
        "Gone sidebar section",
        "Gone untyped section",
        "Gone view",
    )


async def test_sections_inside_a_section_are_checked(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a section in a section, and its cards, are read like any other."""
    config = {
        "views": [
            {
                "path": "home",
                "type": "sections",
                "sections": [
                    {
                        "type": "grid",
                        "sections": [
                            {
                                "type": "grid",
                                "theme": "Gone inner section",
                                "cards": [
                                    {"type": "markdown", "theme": "Gone inner card"}
                                ],
                            },
                            {"strategy": {"type": "x"}, "theme": "Strategy"},
                        ],
                    },
                    {
                        "type": "custom:my-section",
                        "sections": [{"type": "grid", "theme": "Custom's own"}],
                    },
                ],
            },
        ]
    }

    assert await _async_reported(hass, issue_registry, config) == _bulleted(
        "Gone inner card",
        "Gone inner section",
    )


async def test_only_what_the_view_layout_draws_is_checked(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test leftovers of another view layout are left alone.

    A panel view draws its first card. A masonry or sidebar view draws no
    sections, header or footer. A sections view only shows its loose cards
    while editing, to be moved into a section.
    """
    leftovers = {
        "sections": [{"type": "grid", "theme": "Leftover section"}],
        "sidebar": {"sections": [{"type": "grid", "theme": "Leftover sidebar"}]},
        "header": {"card": {"type": "markdown", "theme": "Leftover header"}},
        "footer": {"card": {"type": "markdown", "theme": "Leftover footer"}},
    }
    config = {
        "views": [
            {
                "path": "home",
                "panel": True,
                "cards": [
                    {"type": "markdown", "theme": "Gone panel card"},
                    {"type": "markdown", "theme": "Second panel card"},
                ],
                **leftovers,
            },
            {
                "path": "masonry",
                "type": "masonry",
                "cards": [{"type": "markdown", "theme": "Gone masonry card"}],
                **leftovers,
            },
            {
                "path": "sidebar",
                "type": "sidebar",
                "cards": [{"type": "markdown", "theme": "Gone sidebar card"}],
                **leftovers,
            },
            {
                "path": "sections",
                "type": "sections",
                "sections": [],
                "cards": [{"type": "markdown", "theme": "Imported card"}],
            },
            {
                "path": "unknown",
                "type": "no-such-layout",
                "cards": [{"type": "markdown", "theme": "Error card"}],
                **leftovers,
            },
        ]
    }

    assert await _async_reported(hass, issue_registry, config) == _bulleted(
        "Gone masonry card",
        "Gone panel card",
        "Gone sidebar card",
    )


async def test_nested_cards_are_checked(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test cards inside stacks, grids, conditionals and headers are read."""
    config = {
        "views": [
            {
                "path": "home",
                "cards": [
                    {
                        "type": "vertical-stack",
                        "cards": [
                            {
                                "type": "grid",
                                "cards": [{"type": "button", "theme": "Gone grid"}],
                            }
                        ],
                    },
                    {
                        "type": "conditional",
                        "conditions": [],
                        "card": {"type": "gauge", "theme": "Gone conditional"},
                    },
                    {
                        "type": "horizontal-stack",
                        "cards": [{"type": "light", "theme": "Gone horizontal"}],
                    },
                ],
            },
            {
                "path": "night",
                "sections": [],
                "header": {"card": {"type": "markdown", "theme": "Gone header"}},
                "footer": {"card": {"type": "markdown", "theme": "Gone footer"}},
            },
        ]
    }

    repair = await _async_activate(hass, config)
    await repair.async_deactivate()

    issue = async_issue_about(issue_registry, _ISSUE)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["themes"] == _bulleted(
        "Gone conditional",
        "Gone footer",
        "Gone grid",
        "Gone header",
        "Gone horizontal",
    )
    assert issue.translation_placeholders["edit"] == "/lovelace/home?edit=1"


async def test_entity_filter_card_hands_its_rows_to_an_entities_card(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the entity filter's inner card is an entities card without a type."""
    assert (
        await _async_reported(
            hass,
            issue_registry,
            _with(
                {
                    "type": "entity-filter",
                    "entities": [],
                    "card": {"theme": "Gone untyped"},
                },
                {
                    "type": "entity-filter",
                    "entities": [],
                    "card": {"type": "glance", "theme": "Gone glance"},
                },
            ),
        )
        == "- `Gone glance`\n- `Gone untyped`"
    )


@pytest.mark.parametrize(
    "theme",
    [
        # The frontend's own look.
        "default",
        # Home Assistant's name for no theme at all.
        "none",
        # Themes that exist, with and without light and dark variants.
        "Midnight",
        "Sunrise",
        # No theme at all.
        "",
        None,
        42,
    ],
)
async def test_themes_that_are_there_are_fine(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    theme: Any,
) -> None:
    """Test built in names, known themes and no theme are not reported."""
    assert (
        await _async_reported(
            hass,
            issue_registry,
            _with({"type": "entities", "theme": theme, "entities": []}, theme=theme),
        )
        is None
    )


@pytest.mark.parametrize(
    "theme",
    [
        # The frontend looks a theme up exactly as written.
        "midnight",
        "Midnight ",
        "   ",
        "Default",
        "None",
        # The variants are modes inside a theme, never a theme of their own.
        "Sunrise dark",
    ],
)
async def test_a_name_off_by_a_little_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    theme: str,
) -> None:
    """Test a name the frontend does not find as written is reported."""
    assert (
        await _async_reported(
            hass,
            issue_registry,
            _with({"type": "entities", "theme": theme, "entities": []}),
        )
        == f"- `{theme}`"
    )


@pytest.mark.parametrize(
    "theme",
    [
        "{{ 'Midnight' if is_state('sun.sun', 'below_horizon') else 'Day' }}",
        "{% if night %}Midnight{% endif %}",
        "[[[ return 'Midnight' ]]]",
        "[[theme]]",
        "${vars.theme}",
    ],
)
async def test_templates_are_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    theme: str,
) -> None:
    """Test a theme that is a template is not judged."""
    assert (
        await _async_reported(
            hass,
            issue_registry,
            _with({"type": "entities", "theme": theme, "entities": []}, theme=theme),
        )
        is None
    )


async def test_custom_cards_are_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a custom card, and the core cards inside it, are not judged."""
    assert (
        await _async_reported(
            hass,
            issue_registry,
            _with(
                {"type": "custom:button-card", "theme": "Gone"},
                {
                    "type": "custom:stack-in-card",
                    "cards": [{"type": "entities", "theme": "Gone", "entities": []}],
                },
                {
                    "type": "conditional",
                    "card": {"type": "custom:mushroom-card", "theme": "Gone"},
                },
            ),
        )
        is None
    )


async def test_custom_views_and_sections_keep_their_own_theme(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a custom view or section has its own theme checked, not its cards.

    The frontend puts on the view's and the section's theme itself, whatever
    their type. What is inside them is up to the custom element.
    """
    config = {
        "views": [
            {
                "path": "home",
                "type": "custom:grid-layout",
                "theme": "Gone view",
                "cards": [{"type": "entities", "theme": "Gone card", "entities": []}],
            },
            {
                "path": "night",
                "sections": [
                    {
                        "type": "custom:layout-section",
                        "theme": "Gone section",
                        "cards": [{"type": "markdown", "theme": "Gone inside"}],
                    }
                ],
            },
        ]
    }

    assert (
        await _async_reported(hass, issue_registry, config)
        == "- `Gone section`\n- `Gone view`"
    )


async def test_only_grid_sections_have_their_content_checked(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a section of an unknown layout keeps its theme, not its content.

    The frontend only knows the grid layout, and a section without a type
    gets it. Any other type turns into an error card that draws nothing that
    is in the section, but the section wrapper still puts on its theme.
    """
    config = {
        "views": [
            {
                "path": "home",
                "type": "sections",
                "sections": [
                    {
                        "theme": "Gone untyped section",
                        "cards": [{"type": "markdown", "theme": "Gone untyped card"}],
                    },
                    {
                        "type": "masonry",
                        "theme": "Gone broken section",
                        "cards": [{"type": "markdown", "theme": "Broken card"}],
                        "sections": [{"type": "grid", "theme": "Broken inner"}],
                    },
                ],
            },
        ]
    }

    assert await _async_reported(hass, issue_registry, config) == _bulleted(
        "Gone broken section",
        "Gone untyped card",
        "Gone untyped section",
    )


async def test_strategies_are_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a dashboard, view or section run by a strategy is not judged."""
    strategy = {"type": "original-states"}

    assert (
        await _async_reported(
            hass, issue_registry, {"strategy": strategy, "views": [{"theme": "Gone"}]}
        )
        is None
    )
    assert (
        await _async_reported(
            hass,
            issue_registry,
            {
                "views": [
                    {"strategy": strategy, "theme": "Gone"},
                    {
                        "sections": [
                            {
                                "strategy": strategy,
                                "theme": "Gone",
                                "cards": [{"type": "markdown", "theme": "Gone"}],
                            }
                        ]
                    },
                ]
            },
        )
        is None
    )


async def test_reloading_themes_clears_and_raises_the_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a theme added back, then removed again, is noticed on reload."""
    repair = await _async_activate(
        hass, _with({"type": "entities", "theme": "Starlight", "entities": []})
    )
    assert async_issue_about(issue_registry, _ISSUE)

    with_starlight = {"frontend": {"themes": {**_THEMES, "Starlight": {}}}}
    with patch(
        "homeassistant.components.frontend.async_hass_config_yaml",
        return_value=with_starlight,
    ):
        await hass.services.async_call("frontend", "reload_themes", blocking=True)
    await _async_settle(hass)
    assert "Starlight" in hass.data[DATA_THEMES]
    assert async_issue_about(issue_registry, _ISSUE) is None

    with patch(
        "homeassistant.components.frontend.async_hass_config_yaml",
        return_value={"frontend": {"themes": _THEMES}},
    ):
        await hass.services.async_call("frontend", "reload_themes", blocking=True)
    await _async_settle(hass)
    assert async_issue_about(issue_registry, _ISSUE)

    await repair.async_deactivate()


async def test_saving_the_dashboard_clears_the_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test fixing the theme and saving the dashboard clears the issue."""
    card = {"type": "entities", "theme": "Gone", "entities": []}
    repair = await _async_activate(hass, _with(card))
    assert async_issue_about(issue_registry, _ISSUE)

    card["theme"] = "Midnight"
    hass.bus.async_fire("lovelace_updated", {"url_path": None})
    await _async_settle(hass)
    assert async_issue_about(issue_registry, _ISSUE) is None

    await repair.async_deactivate()


async def test_without_the_frontend_nothing_is_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test no theme is reported when there is no list of themes to check."""
    hass.data.pop(DATA_THEMES)

    card = {"type": "entities", "theme": "Gone", "entities": []}
    repair = SpookRepair(hass)
    repair._dashboards = {"lovelace": _dashboard(_with(card))}  # noqa: SLF001

    # Called straight, so a look that trips over the missing list fails here
    # instead of in the debouncer's log.
    await repair.async_inspect()

    assert async_issue_about(issue_registry, _ISSUE) is None


async def test_a_dashboard_without_a_config_is_skipped(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a dashboard with nothing stored, or stored oddly, is no problem."""
    hass.data["lovelace"] = SimpleNamespace(dashboards={"lovelace": _dashboard(None)})
    repair = SpookRepair(hass)
    await repair.async_activate()
    await _async_settle(hass)
    await repair.async_deactivate()
    assert async_issue_about(issue_registry, _ISSUE) is None

    for config in (
        {"views": "nope"},
        {"views": ["nope", {"cards": "nope", "sections": "nope", "sidebar": []}]},
        {"views": [{"header": [], "sections": ["nope", {"cards": [None]}]}]},
    ):
        assert await _async_reported(hass, issue_registry, config) is None
