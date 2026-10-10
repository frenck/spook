"""Test fixtures for Spook."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant_custom_component.common import get_test_config_dir
from pytest_homeassistant_custom_component.syrupy import HomeAssistantSnapshotExtension

from homeassistant import config_entries, loader, setup
from homeassistant.helpers import translation

from custom_components.spook.const import DOMAIN

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion

    from homeassistant.core import HomeAssistant
    from homeassistant.loader import Integration


@pytest.fixture(autouse=True)
def allow_unreleased_spook(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow loading the local unreleased Spook checkout in Home Assistant tests."""
    monkeypatch.delitem(loader.BLOCKED_CUSTOM_INTEGRATIONS, "spook", raising=False)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations in Home Assistant tests."""
    _ = enable_custom_integrations


@pytest.fixture
def skip_dependency_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip dependency setup for focused Spook config entry unit tests."""

    async def async_process_deps_reqs_noop(
        hass: HomeAssistant,
        config: dict[str, object],
        integration: Integration,
    ) -> None:
        """Skip dependency and requirement setup."""
        _ = hass, config, integration

    monkeypatch.setattr(
        config_entries,
        "async_process_deps_reqs",
        async_process_deps_reqs_noop,
    )
    monkeypatch.setattr(
        setup,
        "async_process_deps_reqs",
        async_process_deps_reqs_noop,
    )


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:  # pylint: disable=redefined-outer-name
    """Use the Home Assistant snapshot extension."""
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture
async def spook_translations(hass: HomeAssistant) -> None:
    """Load Spook's translations, the way Home Assistant does setting Spook up.

    A translated error takes its message from them, and only from those of an
    integration Home Assistant counts as loaded. Without both, the message is
    only its translation key, and a test cannot tell what people read.
    """
    await translation.async_load_integrations(hass, {DOMAIN})
    hass.config.components.add(DOMAIN)


@pytest.fixture(scope="session")
def private_config_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return a test config dir of this test process alone.

    The one the plugin hands out lives in the virtual environment, shared by
    every test process using it: the workers of one run, and every other
    checkout testing at the same time. The sub-integration tests link their
    code into its custom_components, and a worker relinking or another
    checkout pointing a link at its own copy makes an integration go missing
    halfway through a test, or load somebody else's code.

    The links left behind by earlier runs are not copied: they point at
    whatever checkout made them, which may not even be around anymore.
    """
    config_dir = tmp_path_factory.mktemp("config")

    def _skip_links(directory: str, names: list[str]) -> set[str]:
        return {name for name in names if (Path(directory) / name).is_symlink()}

    shutil.copytree(
        get_test_config_dir(),
        config_dir,
        ignore=_skip_links,
        dirs_exist_ok=True,
    )
    return config_dir


@pytest.fixture
def hass_config_dir(private_config_dir: Path) -> str:  # pylint: disable=redefined-outer-name
    """Give Home Assistant the config dir of this test process."""
    return str(private_config_dir)
