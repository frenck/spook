"""Tests for Spook ectoplasm discovery contracts."""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
import re
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
from custom_components.spook.websocket import (
    DATA_WEBSOCKET_COMMANDS,
    AbstractSpookWebSocketCommand,
    async_setup_websocket_commands,
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
WEBSOCKET_MODULES = _discovered_modules("ectoplasms/*/websocket/*.py")

# The naming rule of the websocket module's docstring: `spook/<area>/<verb>`,
# or `spook/<name>`, in lower snake case.
WEBSOCKET_COMMAND_NAME = re.compile(r"spook(/[a-z][a-z0-9]*(_[a-z0-9]+)*){1,2}")


def test_discovery_finds_ectoplasm_modules() -> None:
    """Test discovery finds modules to avoid vacuous contract test passes."""
    assert SERVICE_MODULES, "No service modules discovered"
    assert REPAIR_MODULES, "No repair modules discovered"
    assert TOOL_MODULES, "No tool modules discovered"
    assert WEBSOCKET_MODULES, "No websocket command modules discovered"


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


async def test_tool_discovery_finds_every_module(hass: HomeAssistant) -> None:
    """The tools found at runtime are the modules on disk, no more, no fewer."""
    await async_setup_spook_tools(hass)

    # Lists, not sets: a module found twice would be a tool handed out twice.
    assert sorted(tool.__module__ for tool in hass.data[DATA_TOOLS]) == sorted(
        _module_name(module_file) for module_file in TOOL_MODULES
    )


@pytest.mark.parametrize(
    "name", ["spook/info", "spook/settings/get", "spook/repairs/list_ignored"]
)
def test_websocket_command_name_rule_takes(name: str) -> None:
    """The naming rule takes the shapes its docstring promises."""
    assert WEBSOCKET_COMMAND_NAME.fullmatch(name)


@pytest.mark.parametrize(
    "name",
    [
        "spook",
        "spook/",
        "spook/Info",
        "spook/repairs-list",
        "spook/repairs/list/ignored",
        "spook/repairs//list",
        "spook/_info",
        "spook/info_",
        "homeassistant/info",
        "spook_info",
    ],
)
def test_websocket_command_name_rule_refuses(name: str) -> None:
    """The naming rule refuses what is not lower snake case under spook/."""
    assert not WEBSOCKET_COMMAND_NAME.fullmatch(name)


@pytest.mark.parametrize("module_file", WEBSOCKET_MODULES, ids=_module_name)
def test_websocket_modules_expose_spook_websocket_command(module_file: Path) -> None:
    """Every discovered websocket module exposes a concrete Spook command class."""
    command = _import_module(module_file).SpookWebSocketCommand

    assert isinstance(command, type)
    assert issubclass(command, AbstractSpookWebSocketCommand)
    assert not inspect.isabstract(command)

    assert WEBSOCKET_COMMAND_NAME.fullmatch(command.command), (
        f"{command.command} does not follow the naming rule"
    )

    # No default to fall back on: every command says for itself whether a
    # user without admin rights may call it.
    assert any(
        "admin_only" in vars(cls)
        for cls in command.__mro__[
            : command.__mro__.index(AbstractSpookWebSocketCommand)
        ]
    ), f"{command.command} does not say whether it is for administrators only"
    assert isinstance(command.admin_only, bool)


def test_websocket_command_names_are_unique() -> None:
    """No two commands share a name, as Home Assistant keeps only the last."""
    names = [
        _import_module(module_file).SpookWebSocketCommand.command
        for module_file in WEBSOCKET_MODULES
    ]

    assert len(names) == len(set(names))


async def test_websocket_discovery_finds_every_module(hass: HomeAssistant) -> None:
    """The commands found at runtime are the modules on disk, no more, no fewer."""
    await async_setup_websocket_commands(hass)

    assert sorted(
        command.__module__ for command in hass.data[DATA_WEBSOCKET_COMMANDS].values()
    ) == sorted(_module_name(module_file) for module_file in WEBSOCKET_MODULES)
