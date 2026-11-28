"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.automation import DOMAIN, BaseAutomationEntity
from homeassistant.const import CONF_ALIAS, CONF_ENABLED, CONF_ID, CONF_PLATFORM
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError, TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.template import Template

from ....const import DOMAIN as SPOOK_DOMAIN
from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall, ServiceResponse

ATTR_SKIP_CONDITION = "skip_condition"
ATTR_TRIGGER = "trigger"
ATTR_TRIGGER_DATA = "trigger_data"
ATTR_VARIABLES = "variables"

CONF_TRIGGER = "trigger"
CONF_TRIGGER_VARIABLES = "trigger_variables"
CONF_TRIGGERS = "triggers"
CONF_VARIABLES = "variables"

# What the trace and the logbook say the run was set off by, where a real
# trigger puts something like "state of binary_sensor.front_door".
DESCRIPTION = "action automation.run"

# The same as Home Assistant validates `enabled:` on a trigger with.
ENABLED_SCHEMA = vol.Any(cv.boolean, cv.template)


@dataclass(frozen=True)
class AutomationTrigger:
    """One trigger of an automation, where Home Assistant numbers it."""

    idx: str
    config: dict[str, Any]
    enabled: bool

    @property
    def id(self) -> str:
        """Return its trigger ID, which is its position when it was given none."""
        return self.config.get(CONF_ID, self.idx)


class SpookService(AbstractSpookEntityComponentService[BaseAutomationEntity]):
    """Automation service that runs one as if one of its triggers fired.

    Home Assistant's own `automation.trigger` runs the actions with a trigger
    that is not one: no `trigger.id`, so an automation that picks what to do
    by the trigger that fired cannot be run from a script, a button or a
    test. This one names the trigger, and the run gets the `trigger` variable
    that trigger would have handed it.

    It asks the automation itself to run, not `automation.trigger`. Home
    Assistant can hold a lock on the automation while this action runs, and
    a second automation action called from inside it can end up waiting on
    that same lock.
    """

    domain = DOMAIN
    service = "run"
    supports_response = SupportsResponse.OPTIONAL
    schema = {
        vol.Optional(ATTR_TRIGGER): cv.string,
        vol.Optional(ATTR_TRIGGER_DATA, default=dict): dict,
        vol.Optional(ATTR_VARIABLES, default=dict): dict,
        vol.Optional(ATTR_SKIP_CONDITION, default=False): cv.boolean,
    }

    async def async_handle_service(
        self,
        entity: BaseAutomationEntity,
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle the service call."""
        trigger = self._pick_trigger(entity, call.data.get(ATTR_TRIGGER))

        run_variables: dict[str, Any] = {
            **call.data[ATTR_VARIABLES],
            ATTR_TRIGGER: {
                CONF_ID: trigger.id,
                "idx": trigger.idx,
                CONF_ALIAS: trigger.config.get(CONF_ALIAS),
                CONF_PLATFORM: trigger.config[CONF_PLATFORM],
                "description": DESCRIPTION,
                **call.data[ATTR_TRIGGER_DATA],
            },
        }

        # A trigger can bring variables of its own, which Home Assistant adds
        # to the run when that trigger fires. Rendered the same way, they
        # never overwrite what is there already, so the caller's win.
        if CONF_VARIABLES in trigger.config:
            run_variables = cv.SCRIPT_VARIABLES_SCHEMA(
                trigger.config[CONF_VARIABLES]
            ).async_render(self.hass, run_variables)

        result = await entity.async_trigger(
            run_variables,
            context=call.context,
            skip_condition=call.data[ATTR_SKIP_CONDITION],
        )

        # The automation hands nothing back for every way a run can end
        # before its actions are done: conditions not met, an error on the
        # way, or its mode turning a second run away.
        return {"ran": result is not None}

    def _pick_trigger(
        self,
        entity: BaseAutomationEntity,
        trigger_id: str | None,
    ) -> AutomationTrigger:
        """Return the trigger to run the automation by, or refuse."""
        triggers = self._triggers(entity)
        enabled = [trigger for trigger in triggers if trigger.enabled]
        placeholders = {
            "entity_id": entity.entity_id,
            "trigger": str(trigger_id),
            "triggers": ", ".join(trigger.id for trigger in enabled),
        }

        # Nothing that could fire, so nothing to stand in for, whatever was
        # asked for.
        if not enabled:
            raise ServiceValidationError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="automation_run_no_triggers",
                translation_placeholders=placeholders,
            )

        if trigger_id is None:
            if len(enabled) == 1:
                return enabled[0]

            # Several, and no way to tell which one is meant. Spook does not
            # guess.
            raise ServiceValidationError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="automation_run_trigger_required",
                translation_placeholders=placeholders,
            )

        if not (matching := [t for t in triggers if t.id == trigger_id]):
            raise ServiceValidationError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="automation_run_unknown_trigger",
                translation_placeholders=placeholders,
            )

        # Several triggers can share an ID. They tell the actions the same
        # thing, so the first one that can fire is as good as any.
        if not (matching := [trigger for trigger in matching if trigger.enabled]):
            raise ServiceValidationError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="automation_run_trigger_disabled",
                translation_placeholders=placeholders,
            )

        return matching[0]

    def _triggers(self, entity: BaseAutomationEntity) -> list[AutomationTrigger]:
        """Return the triggers of an automation, numbered like Home Assistant does.

        Read from the configuration the automation was made from, which for
        a blueprint is the one with the inputs filled in. Home Assistant's own
        trigger validation flattens a `triggers:` list nested in the list,
        and the position in what comes out is the trigger's `trigger.idx`.
        """
        raw_config = entity.raw_config or {}
        # Older configurations still call the list `trigger`.
        raw_triggers = raw_config.get(CONF_TRIGGERS, raw_config.get(CONF_TRIGGER, []))

        return [
            AutomationTrigger(
                idx=str(index),
                config=config,
                enabled=self._is_enabled(entity, config),
            )
            for index, config in enumerate(cv.TRIGGER_SCHEMA(raw_triggers))
        ]

    def _is_enabled(self, entity: BaseAutomationEntity, config: dict[str, Any]) -> bool:
        """Return if a trigger is one Home Assistant set up to fire.

        A templated `enabled:` is rendered the way Home Assistant does when it
        sets the triggers up: with only the automation's trigger variables,
        and no states to read. So it gives the answer it gave then, and one
        that fails to render counts as off, as it does there.
        """
        enabled = ENABLED_SCHEMA(config.get(CONF_ENABLED, True))
        if not isinstance(enabled, Template):
            return bool(enabled)

        this = None
        if state := self.hass.states.get(entity.entity_id):
            this = state.as_dict()
        variables: dict[str, Any] = {"this": this}

        raw_config = entity.raw_config or {}
        try:
            if CONF_TRIGGER_VARIABLES in raw_config:
                variables = cv.SCRIPT_VARIABLES_SCHEMA(
                    raw_config[CONF_TRIGGER_VARIABLES]
                ).async_render(self.hass, variables, limited=True)
            return bool(enabled.async_render(variables, limited=True))
        except TemplateError:
            return False
