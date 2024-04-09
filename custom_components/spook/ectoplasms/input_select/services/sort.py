"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.input_select import DOMAIN, InputSelect

from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService[InputSelect]):
    """Input select entity service, sorting the positions.

    These changes are not permanent, and will be lost when input select entities
    are loaded/changed, or when Home Assistant is restarted.
    """

    domain = DOMAIN
    service = "sort"

    async def async_handle_service(
        self,
        entity: InputSelect,
        call: ServiceCall,  # noqa: ARG002
    ) -> None:
        """Handle the service call."""
        # pylint: disable-next=protected-access
        entity._attr_options.sort()  # noqa: SLF001
        entity.async_write_ha_state()
