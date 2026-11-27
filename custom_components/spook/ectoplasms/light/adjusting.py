"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components.light import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL
from homeassistant.exceptions import Unauthorized, UnknownUser
from homeassistant.helpers.service import async_extract_entity_ids

from ...core_compat import async_extract_excluded_entity_ids
from ...services import AbstractSpookService
from . import async_is_light_group

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import ServiceCall


class AbstractAdjustLightService(AbstractSpookService):
    """Shared half of the actions that adjust lights already on.

    These hand the work on to `light.turn_on`, which does what a light needs
    done first: brightness from percentages, colours a light can show. That
    makes them plain actions that find their own lights, rather than entity
    actions. Home Assistant runs an entity action holding its platform's
    lock, and `light.turn_on` waits for that same lock, so on a platform that
    does one call at a time the two would wait on each other for ever.
    """

    domain = DOMAIN

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Adjust every light the call is aimed at, all at once."""
        may_control = await self._async_permission_check(call)

        if call.data.get(ATTR_ENTITY_ID) == ENTITY_MATCH_ALL:
            # Everything, which for somebody with limited rights means
            # everything they may control, the rest passed over quietly.
            # Less what the target excludes, the way Home Assistant does it
            # for its own actions.
            #
            # Groups are left out: every light in one is on this list by
            # itself already. All a group would add is a way back to the very
            # lights the target excluded.
            excluded = async_extract_excluded_entity_ids(call)
            targets = {
                state.entity_id
                for state in self.hass.states.async_all(DOMAIN)
                if state.entity_id not in excluded
                and not async_is_light_group(state)
                and (
                    may_control is None or may_control(state.entity_id, POLICY_CONTROL)
                )
            }
        else:
            referenced = await async_extract_entity_ids(call)

            # All of it checked before anything is touched. Run one light at
            # a time, the ones allowed would already have changed by the time
            # one that is not refused the lot.
            if may_control is not None:
                for entity_id in referenced:
                    if not may_control(entity_id, POLICY_CONTROL):
                        raise Unauthorized(
                            context=call.context,
                            entity_id=entity_id,
                            permission=POLICY_CONTROL,
                        )

            targets = {
                entity_id
                for entity_id in referenced
                if entity_id.startswith(f"{DOMAIN}.")
            }

        await asyncio.gather(
            *(self.async_adjust(entity_id, call) for entity_id in sorted(targets))
        )

    async def _async_permission_check(
        self, call: ServiceCall
    ) -> Callable[[str, str], bool] | None:
        """Return the check for who called, or nothing when anything goes.

        What Home Assistant does for an entity action, which these used to
        be: an administrator, or an automation with nobody behind it, may
        control every light; anybody else what their rights allow.
        """
        if not call.context.user_id:
            return None

        user = await self.hass.auth.async_get_user(call.context.user_id)
        if user is None:
            raise UnknownUser(context=call.context)
        if user.is_admin:
            return None
        return user.permissions.check_entity

    async def async_adjust(self, entity_id: str, call: ServiceCall) -> None:
        """Adjust the lights behind one target."""
        raise NotImplementedError
