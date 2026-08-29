"""Tests for Spook ectoplasm discovery contracts."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from custom_components.spook.const import DOMAIN
from custom_components.spook.repairs import AbstractSpookRepairBase
from custom_components.spook.services import (
    AbstractSpookEntityComponentService,
    AbstractSpookServiceBase,
)

if TYPE_CHECKING:
    from types import ModuleType

SPOOK_ROOT = Path(__file__).parents[1] / "custom_components" / "spook"


def _module_name(module_file: Path) -> str:
    """Return the import path for a Spook module file."""
    return ".".join(
        (
            "custom_components",
            "spook",
            *module_file.relative_to(SPOOK_ROOT).with_suffix("").parts,
        )
    )


def _discovered_modules(pattern: str) -> list[Path]:
    """Return production-discovered modules for the given ectoplasm pattern."""
    return sorted(
        module_file
        for module_file in SPOOK_ROOT.rglob(pattern)
        if module_file.name != "__init__.py"
    )


SERVICE_MODULES = _discovered_modules("ectoplasms/*/services/*.py")
REPAIR_MODULES = _discovered_modules("ectoplasms/*/repairs/*.py")


def test_discovery_finds_ectoplasm_modules() -> None:
    """Test discovery finds modules to avoid vacuous contract test passes."""
    assert SERVICE_MODULES, "No service modules discovered"
    assert REPAIR_MODULES, "No repair modules discovered"


def _import_module(module_file: Path) -> ModuleType:
    """Import a module from a discovered module file."""
    return importlib.import_module(_module_name(module_file))


def _service_schema_key(service_class: type[Any]) -> str:
    """Return the services.yaml key expected for a Spook service class."""
    if service_class.domain == DOMAIN:
        return service_class.service
    return f"{service_class.domain}_{service_class.service}"


@pytest.mark.parametrize("module_file", SERVICE_MODULES, ids=_module_name)
def test_service_modules_expose_spook_service(module_file: Path) -> None:
    """Every discovered service module exposes a concrete Spook service class."""
    module = _import_module(module_file)

    assert hasattr(module, "SpookService")
    assert isinstance(module.SpookService, type)
    assert issubclass(module.SpookService, AbstractSpookServiceBase)


@pytest.mark.parametrize("module_file", REPAIR_MODULES, ids=_module_name)
def test_repair_modules_expose_spook_repair(module_file: Path) -> None:
    """Every discovered repair module exposes a concrete Spook repair class."""
    module = _import_module(module_file)

    assert hasattr(module, "SpookRepair")
    assert isinstance(module.SpookRepair, type)
    assert issubclass(module.SpookRepair, AbstractSpookRepairBase)


def test_entity_component_services_wait_for_their_component() -> None:
    """Every service on somebody else's entity component is waited for.

    Registering one needs that component already set up. If it is not, the
    service is skipped with a log line and never tried again, so the action
    is simply missing until the next restart. Naming the domain in the
    manifest is what makes the order certain.
    """
    manifest = json.loads((SPOOK_ROOT / "manifest.json").read_text())
    waited_for = {
        *manifest["dependencies"],
        *manifest["after_dependencies"],
        DOMAIN,
    }

    unwaited = set()
    for module_file in SERVICE_MODULES:
        service_class = _import_module(module_file).SpookService

        if not issubclass(service_class, AbstractSpookEntityComponentService):
            continue

        if service_class.domain not in waited_for:
            unwaited.add(service_class.domain)

    assert not unwaited, (
        f"Entity component services for {sorted(unwaited)}, which the manifest "
        f"does not wait for. Spook may be set up first and skip them for good."
    )


def test_service_modules_have_service_descriptions() -> None:
    """Every discovered service has a matching services.yaml entry."""
    service_descriptions = yaml.safe_load((SPOOK_ROOT / "services.yaml").read_text())
    assert isinstance(service_descriptions, dict)

    missing_descriptions = []
    for module_file in SERVICE_MODULES:
        module = _import_module(module_file)
        schema_key = _service_schema_key(module.SpookService)
        if schema_key not in service_descriptions:
            missing_descriptions.append(f"{_module_name(module_file)} -> {schema_key}")

    assert not missing_descriptions, (
        f"Missing services.yaml entries: {missing_descriptions}"
    )
