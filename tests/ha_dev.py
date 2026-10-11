"""Let the test harness run on Home Assistant's development branch.

Home Assistant 2026.11 swaps httpx for httpx2 the moment it is imported,
and refuses when httpx is already loaded. The test harness of a released
Home Assistant imports respx, and so httpx, before it imports Home Assistant.
Loaded first with `-p tests.ha_dev`, this does the swap before either of them.
On a released Home Assistant there is no httpx2, and nothing to do.

The test harness also trails Home Assistant's own test helpers by a release.
Where those helpers lean on internals the development branch changed, this
swaps in the development branch's version until the harness catches up.
"""

from __future__ import annotations

from contextlib import suppress
import json
from typing import TYPE_CHECKING, Any

with suppress(ImportError):
    import httpx2

    httpx2.alias_httpx()

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from homeassistant.core import HomeAssistant, State


def pytest_configure() -> None:
    """Patch the harness before any test module imports from it."""
    _patch_restore_cache_helpers()


def _patch_restore_cache_helpers() -> None:
    """Fill the restore cache the way the development branch reads it.

    Home Assistant 2026.11 indexes stored states by entity registry ID
    (home-assistant/core#183906) and no longer reads `last_states`. The
    harness of 2026.10 still writes only that, so every restored state in
    a test went missing. Once the harness ships its own `_mock_restore_cache`,
    it has caught up and this steps aside.
    """
    # Imported here, not at the top, so the httpx swap above goes first.
    # pylint: disable=import-outside-toplevel
    from homeassistant.helpers import restore_state  # noqa: PLC0415
    from homeassistant.helpers.json import JSONEncoder  # noqa: PLC0415
    from homeassistant.util import dt as dt_util  # noqa: PLC0415
    from pytest_homeassistant_custom_component import common  # noqa: PLC0415

    if hasattr(common, "_mock_restore_cache") or not hasattr(
        restore_state.RestoreStateData, "_async_load_stored_states"
    ):
        return

    def mock_restore_cache_with_extra_data(
        hass: HomeAssistant,
        states: Sequence[tuple[State, Mapping[str, Any] | None]],
    ) -> None:
        """Load the states as if they were read from storage."""
        now = dt_util.utcnow()
        stored_states = [
            {
                "state": {
                    **state.as_dict(),
                    "attributes": json.loads(
                        json.dumps(state.attributes, cls=JSONEncoder)
                    ),
                },
                "extra_data": extra_data,
                "last_seen": now,
            }
            for state, extra_data in states
        ]

        # Only there on the development branch, which the guard above checks.
        # pylint: disable-next=no-member,protected-access
        restore_state.async_get(hass)._async_load_stored_states(stored_states)  # noqa: SLF001

    def mock_restore_cache(hass: HomeAssistant, states: Sequence[State]) -> None:
        """Load the states, without extra data, as if read from storage."""
        mock_restore_cache_with_extra_data(hass, [(state, None) for state in states])

    common.mock_restore_cache = mock_restore_cache
    common.mock_restore_cache_with_extra_data = mock_restore_cache_with_extra_data
