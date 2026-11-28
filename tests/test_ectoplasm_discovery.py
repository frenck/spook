"""Tests for Spook ectoplasm discovery contracts."""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from custom_components.spook.const import DOMAIN
from custom_components.spook.llm_tools import (
    DATA_TOOLS,
    AbstractSpookTool,
    async_setup_spook_tools,
)
from custom_components.spook.repairs import AbstractSpookRepairBase
from custom_components.spook.services import (
    AbstractSpookServiceBase,
)

if TYPE_CHECKING:
    from types import ModuleType

    from homeassistant.core import HomeAssistant

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
TOOL_MODULES = _discovered_modules("ectoplasms/*/tools/*.py")


def test_discovery_finds_ectoplasm_modules() -> None:
    """Test discovery finds modules to avoid vacuous contract test passes."""
    assert SERVICE_MODULES, "No service modules discovered"
    assert REPAIR_MODULES, "No repair modules discovered"
    assert TOOL_MODULES, "No tool modules discovered"


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


def test_services_wait_for_their_domain() -> None:
    """Every service on somebody else's domain is waited for.

    Every kind of Spook service registers only once its domain is set up.
    Most wait for a domain that turns up later, but naming it in the manifest
    is what has it there from the start, so the action is in place before
    anything calls it. One on Spook's own platforms does not wait at all.
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

        if service_class.domain not in waited_for:
            unwaited.add(service_class.domain)

    assert not unwaited, (
        f"Services for {sorted(unwaited)}, which the manifest does not wait "
        f"for. Spook may be set up first and skip them for good."
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


@pytest.mark.parametrize("module_file", TOOL_MODULES, ids=_module_name)
def test_tool_modules_expose_spook_tool(module_file: Path) -> None:
    """Every discovered tool module exposes a concrete Spook tool class."""
    tool = _import_module(module_file).SpookTool

    assert isinstance(tool, type)
    assert issubclass(tool, AbstractSpookTool)
    assert not inspect.isabstract(tool)

    assert tool.name == f"{DOMAIN}__{module_file.stem}"
    assert tool.domain == module_file.parent.parent.name
    assert tool.description

    # Home Assistant's default is the worst case: a tool that may change and
    # delete anything, anywhere. Every tool says what it really does.
    assert any(
        "annotations" in vars(cls)
        for cls in tool.__mro__[: tool.__mro__.index(AbstractSpookTool)]
    ), f"{tool.name} does not say whether it is read only"


def test_tool_names_are_unique() -> None:
    """No two tools share a name, as a model picks them by it."""
    names = [_import_module(module_file).SpookTool.name for module_file in TOOL_MODULES]

    assert len(names) == len(set(names))


def test_there_are_two_doors() -> None:
    """Exactly two doors: one that only reads, one that changes things.

    Two, so a client that only allows what reads can still open one of them.
    """
    tools = [_import_module(module_file).SpookTool for module_file in TOOL_MODULES]
    doors = [tool for tool in tools if tool.is_door]

    assert len(doors) == 2  # noqa: PLR2004
    assert sorted(door.annotations.read_only for door in doors) == [False, True]
    assert not any(door.in_front for door in doors)
    assert not any(door.prompt_hint for door in doors)


def test_every_tool_behind_a_door_has_exactly_one() -> None:
    """Every tool that is not in the front is reached through one door, by kind."""
    tools = [_import_module(module_file).SpookTool for module_file in TOOL_MODULES]
    doors = [tool for tool in tools if tool.is_door]

    for tool in tools:
        if tool.in_front or tool.is_door:
            continue

        through = [
            door
            for door in doors
            if door.annotations.read_only == tool.annotations.read_only
        ]
        assert len(through) == 1, f"{tool.name} is not behind exactly one door"


def test_prompt_hints_name_their_own_tool() -> None:
    """A hint is for a tool in the front, and names the tool it is about."""
    for module_file in TOOL_MODULES:
        tool = _import_module(module_file).SpookTool
        if tool.prompt_hint is None:
            continue

        assert tool.in_front, f"{tool.name} has a hint, but is not in the front"
        assert tool.name in tool.prompt_hint


async def test_tool_discovery_finds_every_module(hass: HomeAssistant) -> None:
    """The tools found at runtime are the modules on disk, no more, no fewer."""
    await async_setup_spook_tools(hass)

    # Lists, not sets: a module found twice would be a tool handed out twice.
    assert sorted(tool.__module__ for tool in hass.data[DATA_TOOLS]) == sorted(
        _module_name(module_file) for module_file in TOOL_MODULES
    )
