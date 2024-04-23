"""Spook - Your homie."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from homeassistant.components.input_select import DOMAIN, InputSelect

from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService[InputSelect]):
    """Input select entity service, shuffling the positions.

    These changes are not permanent, and will be lost when input select entities
    are loaded/changed, or when Home Assistant is restarted.
    """

    domain = DOMAIN
    service = "shuffle"

    async def async_handle_service(
        self,
        entity: InputSelect,
        call: ServiceCall,  # noqa: ARG002
    ) -> None:
        """Handle the service call."""
        # pylint: disable-next=protected-access
        random.shuffle(entity._attr_options)  # noqa: SLF001
        entity.async_write_ha_state()
