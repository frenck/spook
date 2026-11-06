"""Test fixtures for Spook."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant.syrupy import HomeAssistantSnapshotExtension

from homeassistant import config_entries, loader, setup
from homeassistant.helpers import translation

from custom_components.spook.const import DOMAIN

if TYPE_CHECKING:
    from pathlib import Path

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
    """Give each test process its own directory for sub-integration links."""
    return tmp_path_factory.mktemp("config")


@pytest.fixture
def hass_config_dir(private_config_dir: Path) -> str:  # pylint: disable=redefined-outer-name
    """Give Home Assistant the config dir of this test process."""
    return str(private_config_dir)
