"""Spook - Your homie. Serve the files Spook's frontends are built into.

The dashboard bundle and the panel are built from `frontend/` in the
repository, into the `static` directory next to this module. A release
builds them, a checkout has them only after `npm run build`. Without them,
Spook carries on as a backend, and nothing is served.

Served with cache headers, so a browser asks for each file once a month at
most. The entry files keep their names, so what loads one puts the version
of Spook in its URL. The rest have a hash of their content in their name.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

from homeassistant.components.http import StaticPathConfig
from homeassistant.util.hass_dict import HassKey

from .const import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

STATIC_PATH: Final = Path(__file__).parent / "static"

# Under `/api/`, where the frontend's service worker never caches anything,
# so a browser always gets what Home Assistant serves.
STATIC_URL: Final = "/api/spook/static"

# Whether the files are served in this process. Home Assistant has no way to
# take a route back, and serving the same path again adds a second route
# that is never reached. So once, kept across reloads of Spook.
DATA_STATIC_FILES_SERVED: HassKey[bool] = HassKey("spook_static_files_served")


async def async_setup_static_files(hass: HomeAssistant) -> None:
    """Serve the built frontends of Spook, if there are any."""
    if DATA_STATIC_FILES_SERVED in hass.data:
        return

    if not await hass.async_add_executor_job(STATIC_PATH.is_dir):
        LOGGER.debug(
            "No frontend of Spook is built in %s, so there is nothing to serve",
            STATIC_PATH,
        )
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(STATIC_PATH), cache_headers=True)]
    )
    hass.data[DATA_STATIC_FILES_SERVED] = True
