"""Spook - Your homie."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)
from homeassistant.helpers.service import _load_services_file, async_set_service_schema
from homeassistant.loader import async_get_integration

from ....services import AbstractSpookService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

MAX_ENTITIES_LIMIT = 50000


class SpookService(AbstractSpookService):
    """Home Assistant service to list filtered entities."""

    domain = DOMAIN
    service = "list_filtered_entities"
    supports_response = SupportsResponse.ONLY

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize and set up dynamic schema hook."""
        super().__init__(hass)
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, self._on_started_set_schema
        )

    async def _on_started_set_schema(self, _event: Event) -> None:
        """Set service schema with live domain and integration options."""
        base_schema = await self._load_base_schema()
        if not base_schema:
            return

        domains = self._collect_live_domains()
        options = [
            {
                "value": d,
                "label": d.replace("_", " ").title(),
            }
            for d in sorted(domains)
        ]

        integration_domains = self._collect_live_integration_domains()
        integration_options: list[dict[str, str]] = []
        for d in sorted(integration_domains):
            label = d
            integration = None
            try:
                integration = await async_get_integration(self.hass, d)
            except (LookupError, ValueError, RuntimeError):  # pragma: no cover
                integration = None
            if integration is not None and getattr(integration, "name", None):
                label = integration.name
            integration_options.append({"value": d, "label": label})

        schema = self._inject_domain_options(base_schema, options)
        schema = self._inject_integration_options(schema, integration_options)
        async_set_service_schema(
            self.hass, domain=self.domain, service=self.service, schema=schema
        )

    async def _load_base_schema(self) -> dict[str, Any] | None:
        """Load base services.yaml and return our service schema block."""
        integration = await async_get_integration(self.hass, "spook")
        services = await self.hass.async_add_executor_job(
            _load_services_file, self.hass, integration
        )
        block = services.get("homeassistant_list_filtered_entities")
        return block if isinstance(block, dict) else None

    def _collect_live_domains(self) -> set[str]:
        """Collect domains from the entity registry and state machine."""
        domains: set[str] = set()
        entity_registry = er.async_get(self.hass)
        for entry in entity_registry.entities.values():
            ent_id = getattr(entry, "entity_id", "")
            if isinstance(ent_id, str) and "." in ent_id:
                domains.add(ent_id.split(".", 1)[0])
        for state in self.hass.states.async_all():
            ent_id = getattr(state, "entity_id", "")
            if isinstance(ent_id, str) and "." in ent_id:
                domains.add(ent_id.split(".", 1)[0])
        return domains

    def _inject_domain_options(
        self, schema: dict[str, Any], options: list[dict[str, str]]
    ) -> dict[str, Any]:
        """Return a new schema with domains selector options replaced."""
        new_schema: dict[str, Any] = dict(schema)
        fields = dict(new_schema.get("fields", {}))
        domains_field = dict(fields.get("domains", {}))
        selector = dict(domains_field.get("selector", {}))
        select = dict(selector.get("select", {}))

        select["options"] = options
        selector["select"] = select
        domains_field["selector"] = selector
        fields["domains"] = domains_field
        new_schema["fields"] = fields
        return new_schema

    def _collect_live_integration_domains(self) -> set[str]:
        """Collect integration domains from entity registry and config entries."""
        domains: set[str] = set()
        entity_registry = er.async_get(self.hass)
        for entry in entity_registry.entities.values():
            platform = getattr(entry, "platform", None)
            if isinstance(platform, str) and platform:
                domains.add(platform)
        if hasattr(self.hass, "config_entries") and hasattr(
            self.hass.config_entries, "async_entries"
        ):
            for cfg in self.hass.config_entries.async_entries():  # type: ignore[attr-defined]
                dom = getattr(cfg, "domain", None)
                if isinstance(dom, str) and dom:
                    domains.add(dom)
        return domains

    def _inject_integration_options(
        self, schema: dict[str, Any], options: list[dict[str, str]]
    ) -> dict[str, Any]:
        """Return a new schema with integrations selector options replaced."""
        new_schema: dict[str, Any] = dict(schema)
        fields = dict(new_schema.get("fields", {}))
        integrations_field = dict(fields.get("integrations", {}))
        selector = dict(integrations_field.get("selector", {}))
        select = dict(selector.get("select", {}))

        select["options"] = options
        selector["select"] = select
        integrations_field["selector"] = selector
        fields["integrations"] = integrations_field
        new_schema["fields"] = fields
        return new_schema

    async def async_handle_service(self, call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        filters, values, limit = self._parse_service_call(call)
        matching_entities = self._find_matching_entities(filters, values, limit)
        return self._format_response(matching_entities)

    def _parse_service_call(
        self, call: ServiceCall
    ) -> tuple[dict[str, Any], list[str], int]:
        """Parse and validate service call parameters."""
        search = call.data.get("search", "")
        areas = call.data.get("areas", [])
        devices = call.data.get("devices", [])
        domains = call.data.get("domains", [])
        integrations = call.data.get("integrations", [])
        status = call.data.get("status", [])
        label_id = call.data.get("label_id", [])
        values = call.data.get("values", [])
        limit = call.data.get("limit")

        # Apply safety cap
        if limit is None or limit > MAX_ENTITIES_LIMIT:
            limit = MAX_ENTITIES_LIMIT

        filters = {
            "search": search,
            "areas": areas,
            "devices": devices,
            "domains": domains,
            "integrations": integrations,
            "status": status,
            "labels": label_id,
        }

        return filters, values, limit

    def _find_matching_entities(
        self,
        filters: dict[str, Any],
        values: list[str],
        limit: int,
    ) -> list[str | dict[str, Any]]:
        """Find entities matching the filter criteria."""
        entity_registry = er.async_get(self.hass)
        matching_entities: list[str | dict[str, Any]] = []

        registry_entity_ids: set[str] = set()
        for entity_entry in entity_registry.entities.values():
            registry_entity_ids.add(entity_entry.entity_id)
            entity_data = self._get_entity_data(entity_entry)

            item = self._append_if_match(entity_entry, entity_data, filters, values)
            if item is not None:
                matching_entities.append(item)
                if len(matching_entities) >= limit:
                    return matching_entities

        for state in self.hass.states.async_all():
            if state.entity_id in registry_entity_ids:
                continue

            entry, entity_data = self._get_state_only_entity_data(state.entity_id)

            item = self._append_if_match(entry, entity_data, filters, values)
            if item is not None:
                matching_entities.append(item)
                if len(matching_entities) >= limit:
                    return matching_entities

        return matching_entities

    def _append_if_match(
        self,
        entity_entry: Any,
        entity_data: dict[str, Any],
        filters: dict[str, Any],
        values: list[str],
    ) -> str | dict[str, Any] | None:
        """Return item to append if it matches search and filters, else None."""
        if not self._matches_search(
            entity_entry, filters.get("search", ""), entity_data
        ):
            return None
        if not self._entity_matches_filters(entity_entry, entity_data, filters):
            return None

        if values:
            return self._build_entity_result(entity_entry, entity_data, values)
        return entity_entry.entity_id

    def _get_entity_data(self, entity_entry: er.RegistryEntry) -> dict[str, Any]:
        """Get comprehensive entity data."""
        data: dict[str, Any] = {}
        if hasattr(entity_entry, "original_name") and entity_entry.original_name:
            data["name"] = entity_entry.original_name
        data["device_id"] = entity_entry.device_id
        device_registry = dr.async_get(self.hass)
        if (
            device := device_registry.async_get(entity_entry.device_id)
        ) and device.name:
            data["device_name"] = device.name
        area_registry = ar.async_get(self.hass)
        area_id = entity_entry.area_id
        if not area_id and entity_entry.device_id:
            device_registry = dr.async_get(self.hass)
            if device := device_registry.async_get(entity_entry.device_id):
                area_id = device.area_id

        if area_id and (area := area_registry.async_get_area(area_id)):
            data["area_id"] = area.id
            data["area_name"] = area.name
        data["integration_name"] = self._get_integration_name(entity_entry)
        data["status"] = self._get_status_info(entity_entry)
        data["icon"] = self._get_entity_icon(entity_entry)
        created_at = getattr(entity_entry, "created_at", None)
        data["created"] = (
            created_at.isoformat() if isinstance(created_at, datetime) else created_at
        )

        modified_at = getattr(entity_entry, "modified_at", None)
        data["modified"] = (
            modified_at.isoformat()
            if isinstance(modified_at, datetime)
            else modified_at
        )
        data["labels"] = self._get_entity_labels(entity_entry)

        return data

    def _get_entity_labels(
        self, entity_entry: er.RegistryEntry
    ) -> list[dict[str, str]]:
        """Get labels for entity (only if labels exist and are supported)."""
        if (
            hasattr(lr, "async_get")
            and hasattr(entity_entry, "labels")
            and entity_entry.labels
        ):
            try:
                label_registry = lr.async_get(self.hass)
                return [
                    {"label_id": label.label_id, "label_name": label.name}
                    for label_id in entity_entry.labels
                    if (label := label_registry.async_get_label(label_id))
                ]
            except AttributeError:
                pass
        return []

    def _get_state_only_entity_data(
        self, entity_id: str
    ) -> tuple[SimpleNamespace, dict[str, Any]]:
        """Build minimal entry/data for state-only entities."""
        state = self.hass.states.get(entity_id)
        domain = entity_id.split(".", 1)[0]
        entry = SimpleNamespace(
            entity_id=entity_id,
            platform=domain,
        )

        data: dict[str, Any] = {}
        status: dict[str, Any] = {}

        if state is not None and state.state not in ("unavailable", "unknown"):
            status["available"] = True
        if state is not None and state.state == "unknown":
            status["unknown"] = True
        if state is not None:
            attrs = getattr(state, "attributes", None)
            if isinstance(attrs, dict) and attrs.get("restored", False):
                status["not_provided"] = True
        status["unmanageable"] = True
        data["status"] = status
        data["labels"] = []
        data["icon"] = None
        data["created"] = None
        data["modified"] = None
        data["integration_name"] = None
        return entry, data

    def _get_integration_name(self, entity_entry: er.RegistryEntry) -> str | None:
        """Get integration name from config entry."""
        if not entity_entry.config_entry_id:
            return None

        config_entries = self.hass.config_entries
        if hasattr(config_entries, "async_get_entry"):
            config_entry = config_entries.async_get_entry(entity_entry.config_entry_id)
        else:
            # Fallback to private access if public method not available
            config_entry = getattr(config_entries, "_entries", {}).get(
                entity_entry.config_entry_id
            )

        return config_entry.title if config_entry else None

    def _get_status_info(self, entity_entry: er.RegistryEntry) -> dict[str, Any]:
        """Get status information for entity."""
        state = self.hass.states.get(entity_entry.entity_id)
        status = {}
        if entity_entry.disabled_by:
            status["disabled_by"] = entity_entry.disabled_by

        if entity_entry.hidden_by:
            status["hidden_by"] = entity_entry.hidden_by

        if state is not None and state.state not in ("unavailable", "unknown"):
            status["available"] = True

        if state is not None and state.state == "unknown":
            status["unknown"] = True
        if state is not None:
            attrs = getattr(state, "attributes", None)
            if isinstance(attrs, dict) and attrs.get("restored", False):
                status["not_provided"] = True
        if getattr(entity_entry, "readonly", False):
            status["unmanageable"] = True

        return status

    def _get_entity_icon(self, entity_entry: er.RegistryEntry) -> str | None:
        """Get entity icon from registry (user-defined or integration default)."""
        return entity_entry.icon or getattr(entity_entry, "original_icon", None)

    def _matches_search(
        self,
        entity_entry: Any,
        search_term: str,
        entity_data: dict[str, Any],
    ) -> bool:
        """Check if entity matches search term."""
        if not search_term:
            return True

        search_lower = search_term.lower()
        search_fields = [
            entity_entry.entity_id,
            entity_entry.platform or "",
            entity_data.get("name") or "",
            entity_data.get("device_name") or "",
            entity_data.get("area_name") or "",
            entity_data.get("integration_name") or "",
        ]
        search_fields.extend(self._status_terms(entity_data.get("status")))
        for field in search_fields:
            if search_lower in field.lower():
                return True
        return self._labels_match(search_lower, entity_data.get("labels", []))

    def _status_terms(self, status: dict[str, Any] | None) -> list[str]:
        """Return extra searchable terms derived from status."""
        if not status:
            return []
        terms: list[str] = []
        if status.get("unmanageable"):
            terms.extend(("unmanageable", "readonly"))
        if status.get("not_provided"):
            terms.extend(("not_provided", "restored"))
        if status.get("disabled_by"):
            terms.append("disabled")
        if status.get("hidden_by"):
            terms.append("hidden")
        if status.get("available"):
            terms.append("available")
        else:
            terms.append("unavailable")
        return terms

    def _labels_match(
        self, search_lower: str, labels: list[dict[str, str]] | None
    ) -> bool:
        """Return True if any label name matches the search."""
        if not labels:
            return False
        for label in labels:
            name = label.get("label_name")
            if name and search_lower in name.lower():
                return True
        return False

    def _entity_matches_filters(
        self,
        entity_entry: er.RegistryEntry,
        entity_data: dict[str, Any],
        filters: dict[str, Any],
    ) -> bool:
        """Check if entity matches all filter criteria."""
        if not self._matches_basic_filters(entity_entry, entity_data, filters):
            return False
        return self._matches_status_filter(entity_data, filters.get("status", []))

    def _matches_basic_filters(
        self,
        entity_entry: er.RegistryEntry,
        entity_data: dict[str, Any],
        filters: dict[str, Any],
    ) -> bool:
        """Check areas, devices, domains, integrations, labels (OR within type)."""
        areas = filters.get("areas")
        if areas and entity_data.get("area_id") not in areas:
            return False
        devices = filters.get("devices")
        if devices and entity_data.get("device_id") not in devices:
            return False
        if domains := filters.get("domains"):
            entity_domain = entity_entry.entity_id.split(".", 1)[0]
            if entity_domain not in domains:
                return False
        integrations = filters.get("integrations")
        if integrations and entity_entry.platform not in integrations:
            return False
        if labels_filter := filters.get("labels"):
            entity_label_ids = {
                label["label_id"] for label in entity_data.get("labels", [])
            }
            if not entity_label_ids.intersection(labels_filter):
                return False

        return True

    def _matches_status_filter(
        self, entity_data: dict[str, Any], status_filters: list[str]
    ) -> bool:
        """Check if entity matches status filter criteria."""
        if not status_filters:
            return True

        entity_status = entity_data["status"]
        status_checks = {
            "available": lambda s: s.get("available", False),
            "unavailable": lambda s: not s.get("available", False),
            "enabled": lambda s: not s.get("disabled_by"),
            "disabled": lambda s: bool(s.get("disabled_by")),
            "visible": lambda s: not s.get("hidden_by"),
            "hidden": lambda s: bool(s.get("hidden_by")),
            "not_provided": lambda s: s.get("not_provided", False),
            "unmanageable": lambda s: s.get("unmanageable", False),
        }
        return any(
            status_checks.get(status_filter, lambda _: False)(entity_status)
            for status_filter in status_filters
        )

    def _build_entity_result(
        self,
        entity_entry: er.RegistryEntry,
        entity_data: dict[str, Any],
        values: list[str],
    ) -> dict[str, Any]:
        """Build entity result with requested values."""
        result = {"entity_id": entity_entry.entity_id}
        value_mapping = {
            "name": lambda: entity_data.get("name"),
            "device": lambda: (
                entity_data.get("device_id")
                and {
                    "device_id": entity_data["device_id"],
                    "device_name": entity_data["device_name"],
                }
            ),
            "area": lambda: (
                entity_data.get("area_id")
                and {
                    "area_id": entity_data["area_id"],
                    "area_name": entity_data["area_name"],
                }
            ),
            "integration": lambda: {
                "integration_name": entity_data.get("integration_name")
            },
            "status": lambda: entity_data.get("status"),
            "icon": lambda: entity_data.get("icon"),
            "created": lambda: entity_data.get("created"),
            "modified": lambda: entity_data.get("modified"),
            "labels": lambda: entity_data.get("labels"),
        }

        for value in values:
            if value in value_mapping:
                data = value_mapping[value]()
                if data is not None:
                    if isinstance(data, dict):
                        result.update(data)
                    else:
                        result[value] = data

        return result

    def _format_response(
        self, matching_entities: list[str | dict[str, Any]]
    ) -> ServiceResponse:
        """Format the final service response."""
        if matching_entities and isinstance(matching_entities[0], dict):
            dict_entities = [e for e in matching_entities if isinstance(e, dict)]
            dict_entities.sort(key=lambda entity: str(entity.get("entity_id", "")))
            matching_entities[:] = dict_entities
        else:
            string_entities = [e for e in matching_entities if isinstance(e, str)]
            string_entities.sort()
            matching_entities[:] = string_entities

        return {
            "count": len(matching_entities),
            "entities": matching_entities,
        }
