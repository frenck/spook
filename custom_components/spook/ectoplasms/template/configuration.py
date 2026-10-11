"""Spook - Your homie."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.template.const import DOMAIN
from homeassistant.components.template.entity import AbstractTemplateEntity
from homeassistant.components.template.trigger_entity import TriggerEntity
from homeassistant.const import CONF_CONDITIONS, CONF_VARIABLES
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.template import Template

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Fired by the template integration once a reload has read the configuration
# again. Core has no constant for it, it builds the name from its domain.
EVENT_TEMPLATE_RELOADED = f"event_{DOMAIN}_reloaded"

# What the template integration adds to the configuration of a state based
# entity, next to what was written: the whole section it came from and the
# blueprint inputs, so the entity can tell which blueprint it uses. Neither is
# anything the entity renders.
_HANDED_ALONG = frozenset({"raw_blueprint_inputs", "raw_configs"})

# What a trigger based section shares between all of its entities.
_SECTION_KEYS = ("triggers", "conditions", "actions", "variables")


def as_written(value: Any) -> Any:
    """Return a validated configuration the way it was written down.

    Validating turns every template into a template object and a block of
    variables into an object of its own. Spook reads configurations as they
    are written, the way it reads a template helper or an automation, so
    those go back to what they were made from.
    """
    if isinstance(value, Template):
        return value.template
    if isinstance(value, ScriptVariables):
        return as_written(value.variables)
    if isinstance(value, Mapping):
        return {key: as_written(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_written(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class YamlTemplateEntity:
    """A template entity from the `template:` section of the configuration."""

    entity_id: str
    name: str
    # What the entity does, as written: its own configuration, and for a
    # trigger based one the triggers, conditions, actions and variables of
    # its section too.
    config: dict[str, Any]
    # The validated configurations it was read from. A reload hands every
    # entity new ones, so these tell whether it is still the same.
    sources: tuple[object, ...]

    def is_read_from(self, other: YamlTemplateEntity) -> bool:
        """Return whether both were read from the very same configuration."""
        return _same(self.sources, other.sources)


def _same(mine: tuple[object, ...], theirs: tuple[object, ...]) -> bool:
    """Return whether two sets of sources are the very same objects."""
    return len(mine) == len(theirs) and all(
        one is other for one, other in zip(mine, theirs, strict=True)
    )


def own_configuration(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return what a template entity was given itself, without its section."""
    return {key: value for key, value in config.items() if key not in _SECTION_KEYS}


def _section_and_own(own: dict[str, Any], section: dict[str, Any]) -> dict[str, Any]:
    """Return what a trigger based entity does: its section, and its own.

    An entity can have conditions and variables of its own, on top of those
    of its section. Both decide whether it updates and what its templates
    see, so they are read together.
    """
    config = own_configuration(own)

    conditions = [
        *(section.get(CONF_CONDITIONS) or []),
        *(own.get(CONF_CONDITIONS) or []),
    ]
    if conditions:
        config[CONF_CONDITIONS] = conditions

    variables = {
        **(section.get(CONF_VARIABLES) or {}),
        **(own.get(CONF_VARIABLES) or {}),
    }
    if variables:
        config[CONF_VARIABLES] = variables

    config.update(
        (key, section[key])
        for key in _SECTION_KEYS
        if key in section and key not in (CONF_CONDITIONS, CONF_VARIABLES)
    )
    return config


def _sources(entity: AbstractTemplateEntity) -> tuple[object, ...]:
    """Return the validated configurations a template entity was set up from."""
    own = getattr(entity, "_config", None)
    if isinstance(entity, TriggerEntity):
        return (own, entity.coordinator.config)
    return (own,)


@callback
def async_is_current(hass: HomeAssistant, template_entity: YamlTemplateEntity) -> bool:
    """Return whether a template entity still has what it was read from.

    Without reading it all again: that is what the sources are for.
    """
    for platform in async_get_platforms(hass, DOMAIN):
        if platform.config_entry is not None:
            continue

        entity = platform.entities.get(template_entity.entity_id)
        if isinstance(entity, AbstractTemplateEntity):
            return _same(template_entity.sources, _sources(entity))

    return False


@callback
def async_get_yaml_template_entities(
    hass: HomeAssistant,
) -> list[YamlTemplateEntity]:
    """Return the template entities set up from YAML, and what they do.

    The template integration keeps no copy of its YAML configuration around.
    Each entity is handed its own validated part, and the triggers,
    conditions, actions and variables of a trigger based section stay with
    the coordinator its entities share. So the entities are where to read it,
    as Home Assistant validated and set it up, blueprints filled in. Re-reading the
    configuration files instead would validate it all again, and that files
    issues and notifications of its own for anything that is not right.

    Template helpers made in the UI run on the same platforms, set up from a
    config entry. Those are read from the config entry instead.
    """
    entities: list[YamlTemplateEntity] = []
    for platform in async_get_platforms(hass, DOMAIN):
        if platform.config_entry is not None:
            continue

        # Taken as a snapshot, a reload can change the collection underneath.
        for entity_id, entity in list(platform.entities.items()):
            # Only the integration's own entities have a configuration to read,
            # and they keep it to themselves. There is no public way to it.
            if not isinstance(entity, AbstractTemplateEntity) or not isinstance(
                own := getattr(entity, "_config", None), Mapping
            ):
                continue

            config = as_written(
                {key: value for key, value in own.items() if key not in _HANDED_ALONG}
            )
            if isinstance(entity, TriggerEntity):
                section = entity.coordinator.config
                config = _section_and_own(
                    config,
                    as_written(
                        {key: section[key] for key in _SECTION_KEYS if key in section}
                    ),
                )

            state = hass.states.get(entity_id)
            entities.append(
                YamlTemplateEntity(
                    entity_id=entity_id,
                    name=state.name if state is not None else entity_id,
                    config=config,
                    sources=_sources(entity),
                )
            )

    return entities
