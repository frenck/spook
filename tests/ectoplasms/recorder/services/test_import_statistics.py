"""Tests for the recorder import statistics service."""
# pylint: disable=redefined-outer-name

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.recorder import DOMAIN
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import (
    STATISTIC_UNIT_TO_UNIT_CONVERTER,
)
from homeassistant.core import Context, HomeAssistant

from custom_components.spook.ectoplasms.recorder.services import import_statistics

if TYPE_CHECKING:
    from homeassistant.components.recorder.models import (
        StatisticData,
        StatisticMetaData,
    )

    from tests.common import MockUser


@pytest.fixture
def recorder_import_statistics_service(hass: HomeAssistant) -> None:
    """Register the Spook recorder import statistics service."""
    hass.config.components.add(DOMAIN)
    import_statistics.SpookService(hass).async_register()


@pytest.mark.usefixtures("recorder_import_statistics_service")
async def test_import_statistics_service_sets_required_metadata(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the import statistics service sets required metadata fields."""
    calls: list[tuple[StatisticMetaData, list[StatisticData]]] = []

    def mock_import_statistics(
        _hass: HomeAssistant,
        metadata: StatisticMetaData,
        statistics: list[StatisticData],
    ) -> None:
        """Mock importing internal statistics."""
        calls.append((metadata, statistics))

    monkeypatch.setattr(
        import_statistics,
        "async_import_statistics",
        mock_import_statistics,
    )

    stats = [{"start": datetime(2026, 1, 1, tzinfo=UTC), "mean": 21.0}]

    await hass.services.async_call(
        DOMAIN,
        "import_statistics",
        {
            "has_mean": True,
            "has_sum": False,
            "source": DOMAIN,
            "statistic_id": "sensor.temperature",
            "unit_of_measurement": "°C",
            "stats": stats,
        },
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    metadata, imported_stats = calls[0]

    assert metadata["mean_type"] is StatisticMeanType.ARITHMETIC
    assert metadata["unit_class"] == STATISTIC_UNIT_TO_UNIT_CONVERTER["°C"].UNIT_CLASS
    assert "has_mean" not in metadata
    assert imported_stats == [{**stats[0], "last_reset": None}]


@pytest.mark.usefixtures("recorder_import_statistics_service")
async def test_import_statistics_service_sets_no_mean_metadata(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the import statistics service sets no mean metadata."""
    calls: list[dict[str, Any]] = []

    def mock_add_external_statistics(
        _hass: HomeAssistant,
        metadata: StatisticMetaData,
        _statistics: list[StatisticData],
    ) -> None:
        """Mock importing external statistics."""
        calls.append(dict(metadata))

    monkeypatch.setattr(
        import_statistics,
        "async_add_external_statistics",
        mock_add_external_statistics,
    )

    await hass.services.async_call(
        DOMAIN,
        "import_statistics",
        {
            "has_mean": False,
            "has_sum": True,
            "source": "spook",
            "statistic_id": "spook:total",
            "stats": [{"start": datetime(2026, 1, 1, tzinfo=UTC), "sum": 42.0}],
        },
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert calls[0]["mean_type"] is StatisticMeanType.NONE
    assert calls[0]["unit_class"] == STATISTIC_UNIT_TO_UNIT_CONVERTER[None].UNIT_CLASS
    assert "has_mean" not in calls[0]
