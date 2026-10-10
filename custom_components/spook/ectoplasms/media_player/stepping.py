"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.media_player import (
    DOMAIN,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)

from ...services import AbstractSpookEntityComponentService
from ...setpoints import CONF_STEP, moved_setpoint

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

_SILENT = 0.0
_FULL = 1.0
_PERCENT = 100

# A volume runs from 0 to 1, so two decimals would be whole percents, and a
# step from 0.456 would land on 0.51. Four keeps the step as asked, and still
# rounds away float noise.
_DECIMALS = 4


class AbstractStepVolumeService(AbstractSpookEntityComponentService[MediaPlayerEntity]):
    """Shared half of stepping a media player's volume up and down.

    Home Assistant's own `media_player.volume_up` takes the step the player
    decides on, or presses the player's own button, so how far it goes is
    not up to whoever asks. Here it is: the step is required, in percent,
    like the light actions' brightness steps. Not only whole ones: a volume
    is no whole number, and 2.5 percent is a fine step to ask for.
    """

    domain = DOMAIN
    required_features = [MediaPlayerEntityFeature.VOLUME_SET]
    schema = {
        vol.Required(CONF_STEP): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=100, min_included=False)
        ),
    }

    #: Which way this one goes.
    direction: int

    async def async_handle_service(
        self,
        entity: MediaPlayerEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        if (volume := entity.volume_level) is None:
            return

        moved = moved_setpoint(
            volume,
            self.direction * call.data[CONF_STEP] / _PERCENT,
            _SILENT,
            _FULL,
            _DECIMALS,
        )
        if moved is None:
            return

        # Straight to the player, not through `media_player.volume_set`,
        # which would wait on the lock this action already holds on a
        # platform that does one call at a time.
        await entity.async_set_volume_level(moved)
