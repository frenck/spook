"""Tests for the Lovelace public www files repair."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.frontend import DATA_THEMES
from homeassistant.components.lovelace.const import ConfigNotFound
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.lovelace.repairs.public_www_files import (
    SpookRepair,
)

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE = "lovelace_public_www_files_{}"


@pytest.fixture(name="www")
def www_fixture(hass: HomeAssistant, tmp_path: Path) -> Path:
    """Return a `www` folder of this test's own.

    The configuration directory is shared by the whole session, and files
    another test left in its `www` would end up in these findings.
    """
    hass.config.config_dir = str(tmp_path)
    return tmp_path / "www"


def _write(www: Path, *names: str) -> None:
    """Create these files under `www`."""
    for name in names:
        path = www / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("here", encoding="utf-8")


def _set_dashboards(
    hass: HomeAssistant, *configs: dict[str, Any] | HomeAssistantError
) -> None:
    """Install dashboards with these configs, or the error loading one raises."""

    def dashboard(
        url_path: str, config: dict[str, Any] | HomeAssistantError
    ) -> SimpleNamespace:
        async def async_load(*, force: bool) -> dict[str, Any]:
            del force
            if isinstance(config, HomeAssistantError):
                raise config
            return config

        return SimpleNamespace(url_path=url_path, config={}, async_load=async_load)

    hass.data["lovelace"] = SimpleNamespace(
        dashboards={
            f"dashboard-{index}": dashboard(f"dashboard-{index}", config)
            for index, config in enumerate(configs)
        }
    )


async def _async_inspect(hass: HomeAssistant) -> SpookRepair:
    """Run one inspection, cleanup included, and return the repair."""
    repair = SpookRepair(hass)
    repair._dashboards = hass.data["lovelace"].dashboards  # noqa: SLF001
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    return repair


def _issue(issue_registry: ir.IssueRegistry, folder: str) -> ir.IssueEntry | None:
    """Return the issue about this folder, if there is one."""
    return issue_registry.async_get_issue(DOMAIN, _ISSUE.format(folder))


async def test_files_an_integration_left_are_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a folder of files nobody put up on purpose is reported."""
    await hass.async_add_executor_job(
        _write,
        www,
        *(f"printer/cover_{index:02}.png" for index in range(12)),
        "printer/jobs/latest.3mf",
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    issue = _issue(issue_registry, "printer")
    assert issue
    assert issue.translation_key == "lovelace_public_www_files"
    assert issue.translation_placeholders
    assert issue.translation_placeholders["folder"] == "/local/printer/"
    assert issue.translation_placeholders["count"] == "13"
    # Only the first few are listed, in a stable order.
    assert issue.translation_placeholders["files"] == "\n".join(
        f"- `/local/printer/cover_{index:02}.png`" for index in range(10)
    )


async def test_files_straight_in_www_are_reported_together(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test loose files share one issue, and loose code is left alone.

    A folder that happens to be called `www` gets an issue of its own.
    """
    await hass.async_add_executor_job(
        _write, www, "snapshot.jpg", "notes.txt", "my-card.js", "www/cover.png"
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    issue = _issue(issue_registry, ".")
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["folder"] == "/local/"
    assert issue.translation_placeholders["files"] == (
        "- `/local/notes.txt`\n- `/local/snapshot.jpg`"
    )
    issue = _issue(issue_registry, "www")
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["folder"] == "/local/www/"


async def test_what_is_put_up_on_purpose_is_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test the Marketplace, cards, hidden files and linked files are left alone."""
    await hass.async_add_executor_job(
        _write,
        www,
        "community/some-card/some-card.js",
        "community/some-card/preview.png",
        "manual-card/manual-card.js",
        "manual-card/icons/logo.svg",
        ".DS_Store",
        "floorplan/.hidden/backup.png",
        "floorplan/ground floor.png",
        "floorplan/first.png",
        "floorplan/legend.png",
        "floorplan/notes.png",
        # Names a link cannot be cut out of by looking for where it ends.
        "floorplan/plan(1).png",
        "floorplan/attic (2).png",
        "backgrounds/night.jpg",
    )
    hass.data[DATA_THEMES] = {
        "dark": {
            "lovelace-background": 'center / cover url("/local/backgrounds/night.jpg")'
        }
    }
    _set_dashboards(
        hass,
        {
            "views": [
                {
                    "cards": [
                        {
                            "type": "picture-elements",
                            "image": "/local/floorplan/ground%20floor.png?v=2",
                        },
                        {
                            "type": "custom:fancy-card",
                            "layers": [
                                {
                                    "src": "https://ha.example.com/local/floorplan/first.png"
                                }
                            ],
                        },
                        {
                            "type": "markdown",
                            "content": (
                                "![Legend](/local/floorplan/legend.png) "
                                '<img src="/local/floorplan/notes.png">'
                                '<img src="/local/floorplan/plan(1).png">'
                            ),
                        },
                        {"type": "picture", "image": "/local/floorplan/attic (2).png"},
                    ]
                }
            ]
        },
    )

    await _async_inspect(hass)

    assert not [
        issue_id
        for domain, issue_id in issue_registry.issues
        if domain == DOMAIN and issue_id.startswith("lovelace_public_www_files")
    ]


@pytest.mark.usefixtures("www")
async def test_no_www_folder_is_a_no_op(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a configuration without a `www` folder raises nothing."""
    _set_dashboards(hass)

    await _async_inspect(hass)

    assert _issue(issue_registry, ".") is None


async def test_issue_goes_once_the_files_do(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test the issue is cleaned up when the folder is emptied."""
    await hass.async_add_executor_job(_write, www, "printer/cover.png")
    _set_dashboards(hass)

    repair = await _async_inspect(hass)
    assert _issue(issue_registry, "printer")

    await hass.async_add_executor_job((www / "printer" / "cover.png").unlink)
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    assert _issue(issue_registry, "printer") is None


async def test_ignoring_a_folder_outlasts_new_files(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test an ignored folder stays ignored when files are added to it.

    An integration writing here keeps adding files, and ignoring it is a
    decision about the folder, not about the files that were there then.
    """
    await hass.async_add_executor_job(_write, www, "printer/cover_1.png")
    _set_dashboards(hass)

    repair = await _async_inspect(hass)
    issue_registry.async_ignore(DOMAIN, _ISSUE.format("printer"), ignore=True)

    await hass.async_add_executor_job(_write, www, "printer/cover_2.png")
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    issue = _issue(issue_registry, "printer")
    assert issue
    assert issue.dismissed_version is not None
    assert issue.translation_placeholders
    assert issue.translation_placeholders["count"] == "2"


async def test_a_dashboard_without_a_stored_config_is_no_reason_to_stop(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test the generated Overview, which has nothing stored, is passed over."""
    await hass.async_add_executor_job(_write, www, "printer/cover.png")
    _set_dashboards(hass, ConfigNotFound())

    await _async_inspect(hass)

    assert _issue(issue_registry, "printer")


async def test_an_unreadable_dashboard_skips_the_round(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test nothing is reported, or cleaned up, while a dashboard is unreadable.

    Its links are unknown, so any file could be one it shows. A fresh repair
    stands in for a restart, which only knows the issues from the registry.
    """
    await hass.async_add_executor_job(_write, www, "printer/cover.png")
    _set_dashboards(hass)
    await _async_inspect(hass)

    await hass.async_add_executor_job(_write, www, "camera/snapshot.jpg")
    _set_dashboards(hass, HomeAssistantError("Broken YAML"))
    await _async_inspect(hass)

    assert _issue(issue_registry, "printer")
    assert _issue(issue_registry, "camera") is None
    assert "Spook could not read dashboard dashboard-0" in caplog.text


async def test_the_old_default_dashboard_is_passed_over(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a leftover of the old default dashboard cannot stop every round.

    Home Assistant keeps it under no name next to the real one, and nobody
    can open it, so its file being broken is nobody's problem to fix.
    """
    await hass.async_add_executor_job(_write, www, "printer/cover.png")
    _set_dashboards(hass, {}, HomeAssistantError("Leftover"))
    dashboards = hass.data["lovelace"].dashboards
    dashboards["lovelace"] = dashboards.pop("dashboard-0")
    dashboards[None] = dashboards.pop("dashboard-1")

    await _async_inspect(hass)

    assert _issue(issue_registry, "printer")


async def test_a_folder_that_keeps_filling_is_counted_not_kept(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test all files are counted, while only the first by name are kept.

    An integration that stores every snapshot or print can leave tens of
    thousands behind. They are written here out of order, as a folder hands
    them out in no order either.
    """
    await hass.async_add_executor_job(
        _write,
        www,
        *(f"printer/cover_{index:03}.png" for index in reversed(range(250))),
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    issue = _issue(issue_registry, "printer")
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["count"] == "250"
    assert issue.translation_placeholders["files"] == "\n".join(
        f"- `/local/printer/cover_{index:03}.png`" for index in range(10)
    )


def test_a_component_loading_is_no_reason_to_look() -> None:
    """Test the repair does not look again for every component that loads.

    Hundreds load while Home Assistant starts, and each look walks all of
    the `www` folder.
    """
    assert EVENT_COMPONENT_LOADED not in SpookRepair.inspect_events


async def test_a_customized_entity_picture_is_in_use(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a picture given to an entity with `customize:` is in use. #2158.

    Its sibling, which nothing shows, is still reported.
    """
    await hass.async_add_executor_job(
        _write, www, "example-icons/status.png", "example-icons/unused.png"
    )
    await async_process_ha_core_config(
        hass,
        {
            "customize": {
                "input_boolean.example": {
                    "entity_picture": "/local/example-icons/status.png"
                }
            }
        },
    )
    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"example": {}}}
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    issue = _issue(issue_registry, "example-icons")
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["count"] == "1"
    assert issue.translation_placeholders["files"] == (
        "- `/local/example-icons/unused.png`"
    )


async def test_a_folder_of_entity_pictures_all_in_use_is_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a folder is not reported when every file in it is a picture. #2158."""
    await hass.async_add_executor_job(
        _write, www, "example-icons/status.png", "example-icons/unused.png"
    )
    await async_process_ha_core_config(
        hass,
        {
            "customize": {
                "input_boolean.example": {
                    "entity_picture": "/local/example-icons/status.png"
                },
                "input_boolean.other": {
                    "entity_picture": "/local/example-icons/unused.png"
                },
            }
        },
    )
    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"example": {}, "other": {}}}
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    assert _issue(issue_registry, "example-icons") is None


async def test_an_entity_picture_an_integration_sets_is_in_use(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a picture an integration gives its entity is in use. #2160."""
    await hass.async_add_executor_job(_write, www, "waste/paper.png")
    hass.states.async_set(
        "sensor.waste_collection",
        "paper",
        {"entity_picture": "/local/waste/paper.png?v=3", "days": 2},
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    assert _issue(issue_registry, "waste") is None


async def test_a_notification_image_in_an_automation_is_in_use(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test an image a notification sends along is in use. #2161."""
    await hass.async_add_executor_job(_write, www, "icons/doorbell.png")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "alias": "Doorbell",
                "triggers": {"trigger": "event", "event_type": "doorbell"},
                "actions": {
                    "action": "notify.mobile_app_phone",
                    "data": {
                        "message": "Somebody is at the door",
                        "data": {
                            "image": "https://ha.example.com/local/icons/doorbell.png"
                        },
                    },
                },
            }
        },
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    assert _issue(issue_registry, "icons") is None


async def test_a_templated_link_clears_the_folder_it_points_into(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a link built by a template leaves its whole folder alone. #2161.

    Which file it ends up at is only known when it runs. Other folders are
    still reported.
    """
    await hass.async_add_executor_job(
        _write, www, "icons/washer.png", "icons/dryer.png", "printer/cover.png"
    )
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "alias": "Appliance done",
                "triggers": {"trigger": "event", "event_type": "appliance_done"},
                "actions": {
                    "action": "notify.mobile_app_phone",
                    "data": {
                        "message": "Done",
                        "data": {
                            "image": "/local/icons/{{ trigger.event.data.kind }}.png"
                        },
                    },
                },
            }
        },
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    assert _issue(issue_registry, "icons") is None
    assert _issue(issue_registry, "printer")


async def test_a_template_building_onto_a_folder_clears_it(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a template joining the file name onto a folder clears that folder."""
    await hass.async_add_executor_job(_write, www, "icons/washer.png")
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "appliance_done": {
                    "sequence": {
                        "action": "notify.mobile_app_phone",
                        "data": {
                            "message": "Done",
                            "data": {"image": "{{ '/local/icons/' ~ kind ~ '.png' }}"},
                        },
                    }
                }
            }
        },
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    assert _issue(issue_registry, "icons") is None


async def test_a_templated_link_into_no_known_folder_skips_the_round(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a template choosing the folder, or a loose file, silences the round.

    It can point at any file in `www`, so nothing can be said about any of
    them. Issues raised before go too: this is no passing state.
    """
    await hass.async_add_executor_job(_write, www, "printer/cover.png", "loose.png")
    _set_dashboards(hass)
    repair = await _async_inspect(hass)
    assert _issue(issue_registry, "printer")

    hass.states.async_set(
        "sensor.picture", "on", {"entity_picture": "/local/{{ folder }}/a.png"}
    )
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    assert _issue(issue_registry, "printer") is None
    assert _issue(issue_registry, ".") is None


async def test_a_templated_loose_file_skips_the_round(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a template choosing a file straight in `www` silences the round."""
    await hass.async_add_executor_job(_write, www, "printer/cover.png")
    hass.states.async_set(
        "sensor.picture", "on", {"entity_picture": "/local/{{ name }}.png"}
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    assert _issue(issue_registry, "printer") is None


async def test_a_template_next_to_a_plain_link_clears_nothing_more(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a template elsewhere in the same text leaves the link a plain one.

    A notification showing a picture and a value, the most common message
    there is, would otherwise silence the repair for everyone writing one.
    """
    await hass.async_add_executor_job(_write, www, "doorbell.png", "loose.png")
    hass.states.async_set(
        "sensor.picture",
        "on",
        {"message": "![](/local/doorbell.png) {{ states('sensor.visitor') }}"},
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    issue = _issue(issue_registry, ".")
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["files"] == "- `/local/loose.png`"


async def test_a_template_behind_the_file_name_clears_only_that_file(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a template in the query of a link leaves the link a plain one.

    A picture that changes is given a different address each time, so the
    browser fetches it again. Which file it is does not change with it.
    """
    await hass.async_add_executor_job(
        _write, www, "doorbell.png", "loose.png", "printer/cover.png"
    )
    hass.states.async_set(
        "sensor.picture",
        "on",
        {"entity_picture": "/local/doorbell.png?v={{ now().timestamp() }}"},
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    issue = _issue(issue_registry, ".")
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["files"] == "- `/local/loose.png`"
    assert _issue(issue_registry, "printer")


async def test_a_templated_link_clears_a_folder_named_the_way_a_url_is(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a templated link clears a folder whose name it has to encode."""
    await hass.async_add_executor_job(
        _write, www, "my icons/rain.png", "printer/cover.png"
    )
    hass.states.async_set(
        "sensor.picture",
        "on",
        {"entity_picture": "/local/my%20icons/{{ kind }}.png"},
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    assert _issue(issue_registry, "my icons") is None
    assert _issue(issue_registry, "printer")


async def test_a_templated_link_is_decoded_only_once(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a templated link clears the folder it names, and no lookalike.

    A folder can have a `%` in its name. The link into it encodes that, and
    decoding it twice would end up at another folder.
    """
    await hass.async_add_executor_job(
        _write, www, "my%20icons/rain.png", "my icons/cover.png"
    )
    hass.states.async_set(
        "sensor.picture",
        "on",
        {"entity_picture": "/local/my%2520icons/{{ kind }}.png"},
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    assert _issue(issue_registry, "my%20icons") is None
    assert _issue(issue_registry, "my icons")


async def test_a_link_in_a_script_is_in_use(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a file a script links to is in use."""
    await hass.async_add_executor_job(_write, www, "sounds/chime.mp3")
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "chime": {
                    "sequence": {
                        "action": "media_player.play_media",
                        "target": {"entity_id": "media_player.kitchen"},
                        "data": {
                            "media_content_id": "/local/sounds/chime.mp3",
                            "media_content_type": "music",
                        },
                    }
                }
            }
        },
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    assert _issue(issue_registry, "sounds") is None


async def test_a_link_in_config_entry_options_is_in_use(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a file a helper made in the UI links to is in use.

    Looked at in the entry itself, as a helper that fails to load still
    shows it once it does.
    """
    await hass.async_add_executor_job(_write, www, "pictures/boiler.png")
    MockConfigEntry(
        domain="template",
        options={"template_type": "sensor", "picture": "/local/pictures/boiler.png"},
    ).add_to_hass(hass)
    _set_dashboards(hass)

    await _async_inspect(hass)

    assert _issue(issue_registry, "pictures") is None
