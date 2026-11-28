"""Tests for remembering an ignore on a repair about one thing.

Some repairs raise an issue about one thing and nothing more: an area, a
floor, a label, a blueprint, a resource, a folder. Ignoring such an issue is
about that thing. It has to outlast the issue going for a while, just like
an ignore on a list of findings does.
"""

# A repair cleans up after itself in a private method, and that is exactly
# where an ignore used to get lost.
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components import blueprint
from homeassistant.components.blueprint import Blueprint
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.helpers import (
    area_registry as ar,
    entity_registry as er,
    floor_registry as fr,
    issue_registry as ir,
    label_registry as lr,
)

from custom_components.spook.const import DOMAIN
from custom_components.spook.dismissals import DATA_DISMISSALS, async_setup_dismissals
from custom_components.spook.ectoplasms.homeassistant.repairs import (
    empty_areas,
    empty_floors,
    unused_blueprints,
    unused_labels,
)
from custom_components.spook.ectoplasms.lovelace.repairs import (
    duplicate_resources,
    public_www_files,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

    from custom_components.spook.repairs import AbstractSpookRepair

# Comfortably past the grace period of a new area, floor or label.
_AGED = timedelta(days=2)


class _Haunting:
    """One repair, and how to make what it reports come and go.

    Each `haunt` makes one thing the repair reports, and returns what the
    issue is filed under.
    """

    repair_class: type[AbstractSpookRepair]

    def __init__(self, hass: HomeAssistant, tmp_path: Path) -> None:
        """Hold on to Home Assistant, and set up what the repair reads."""
        self.hass = hass
        self.tmp_path = tmp_path

    def repair(self) -> AbstractSpookRepair:
        """Return the repair, ready to look."""
        return self.repair_class(self.hass)

    async def haunt(self, name: str) -> str:
        """Make one thing the repair reports."""
        raise NotImplementedError

    async def take_away(self, owner: str) -> None:
        """Make what the repair reported about this thing go away."""
        raise NotImplementedError

    async def bring_back(self, owner: str) -> None:
        """Make it come back."""
        raise NotImplementedError


class _EmptyArea(_Haunting):
    """An area with nothing in it; an entity in it takes the finding away."""

    repair_class = empty_areas.SpookRepair

    async def haunt(self, name: str) -> str:
        """Create an area."""
        return ar.async_get(self.hass).async_create(name).id

    async def take_away(self, owner: str) -> None:
        """Put an entity in the area."""
        entity_registry = er.async_get(self.hass)
        entry = entity_registry.async_get_or_create("light", "hue", owner)
        entity_registry.async_update_entity(entry.entity_id, area_id=owner)

    async def bring_back(self, owner: str) -> None:
        """Take the entity out again."""
        entity_registry = er.async_get(self.hass)
        entity_id = entity_registry.async_get_entity_id("light", "hue", owner)
        assert entity_id
        entity_registry.async_update_entity(entity_id, area_id=None)


class _EmptyFloor(_Haunting):
    """A floor without areas; an area on it takes the finding away."""

    repair_class = empty_floors.SpookRepair

    async def haunt(self, name: str) -> str:
        """Create a floor."""
        return fr.async_get(self.hass).async_create(name).floor_id

    async def take_away(self, owner: str) -> None:
        """Put an area on the floor."""
        area = ar.async_get(self.hass).async_get_or_create(f"Room on {owner}")
        ar.async_get(self.hass).async_update(area.id, floor_id=owner)

    async def bring_back(self, owner: str) -> None:
        """Take the area off the floor again."""
        area_registry = ar.async_get(self.hass)
        for area in ar.async_entries_for_floor(area_registry, owner):
            area_registry.async_update(area.id, floor_id=None)


class _UnusedLabel(_Haunting):
    """A label on nothing; putting it on an entity takes the finding away."""

    repair_class = unused_labels.SpookRepair

    async def haunt(self, name: str) -> str:
        """Create a label."""
        return lr.async_get(self.hass).async_create(name).label_id

    async def take_away(self, owner: str) -> None:
        """Put the label on an entity."""
        entity_registry = er.async_get(self.hass)
        entry = entity_registry.async_get_or_create("light", "hue", owner)
        entity_registry.async_update_entity(entry.entity_id, labels={owner})

    async def bring_back(self, owner: str) -> None:
        """Take the label off again."""
        entity_registry = er.async_get(self.hass)
        entity_id = entity_registry.async_get_entity_id("light", "hue", owner)
        assert entity_id
        entity_registry.async_update_entity(entity_id, labels=set())


class _FakeDomainBlueprints:  # pylint: disable=too-few-public-methods
    """Just enough of core's DomainBlueprints to be looked at."""

    def __init__(self) -> None:
        """Start without blueprints."""
        self.blueprints: dict[str, Any] = {}
        self.blueprint_folder = Path("/nonexistent")

    async def async_get_blueprints(self) -> dict[str, Any]:
        """Return the blueprints."""
        return self.blueprints


def _blueprint(name: str) -> Blueprint:
    """Return a minimal automation blueprint."""
    return Blueprint(
        {"blueprint": {"name": name, "domain": "automation"}},
        expected_domain="automation",
        schema=BLUEPRINT_SCHEMA,
    )


class _UnusedBlueprint(_Haunting):
    """A blueprint nothing uses; taking the file away takes the finding away."""

    repair_class = unused_blueprints.SpookRepair

    def __init__(self, hass: HomeAssistant, tmp_path: Path) -> None:
        """Install blueprints of this test's own."""
        super().__init__(hass, tmp_path)
        self.blueprints = _FakeDomainBlueprints()
        self.removed: dict[str, Blueprint] = {}
        hass.data[blueprint.DOMAIN] = {"automation": self.blueprints}

    async def haunt(self, name: str) -> str:
        """Add a blueprint."""
        path = f"{name.lower()}.yaml"
        self.blueprints.blueprints[path] = _blueprint(name)
        return f"automation:{path}"

    async def take_away(self, owner: str) -> None:
        """Remove the blueprint."""
        path = owner.removeprefix("automation:")
        self.removed[path] = self.blueprints.blueprints.pop(path)

    async def bring_back(self, owner: str) -> None:
        """Put the blueprint back."""
        path = owner.removeprefix("automation:")
        self.blueprints.blueprints[path] = self.removed.pop(path)


class _FakeResources:
    """Just enough of the storage-mode resource collection to be looked at."""

    def __init__(self) -> None:
        """Start without resources."""
        self.items: list[dict[str, str]] = []

    def async_items(self) -> list[dict[str, str]]:
        """Return the resources."""
        return self.items

    async def async_get_info(self) -> dict[str, int]:
        """Pretend to load them, the way the real collection does."""
        return {"resources": len(self.items)}


class _DuplicateResource(_Haunting):
    """A resource listed twice; one copy less takes the finding away."""

    repair_class = duplicate_resources.SpookRepair

    def __init__(self, hass: HomeAssistant, tmp_path: Path) -> None:
        """Install resources of this test's own."""
        super().__init__(hass, tmp_path)
        self.resources = _FakeResources()
        hass.data["lovelace"] = SimpleNamespace(resources=self.resources)

    def _add(self, url: str) -> None:
        """List a resource once more."""
        self.resources.items.append(
            {"id": str(len(self.resources.items)), "url": url, "type": "module"}
        )

    async def haunt(self, name: str) -> str:
        """List a resource twice."""
        url = f"/local/{name.lower()}.js"
        self._add(url)
        self._add(url)
        return f"module|{url}"

    async def take_away(self, owner: str) -> None:
        """Remove one of the copies."""
        url = owner.removeprefix("module|")
        copy = next(item for item in self.resources.items if item["url"] == url)
        self.resources.items.remove(copy)

    async def bring_back(self, owner: str) -> None:
        """List it twice again."""
        self._add(owner.removeprefix("module|"))


class _PublicWwwFiles(_Haunting):
    """A folder in `www` with a file nobody links to; removing it clears it."""

    repair_class = public_www_files.SpookRepair

    def __init__(self, hass: HomeAssistant, tmp_path: Path) -> None:
        """Give this test a `www` of its own, and no dashboards."""
        super().__init__(hass, tmp_path)
        hass.config.config_dir = str(tmp_path)
        hass.data["lovelace"] = SimpleNamespace(dashboards={})

    def repair(self) -> AbstractSpookRepair:
        """Return the repair, with the dashboards it would get on activating."""
        repair = public_www_files.SpookRepair(self.hass)
        repair._dashboards = {}
        return repair

    def _snapshot(self, owner: str) -> Path:
        """Return the file that makes the folder reported."""
        return self.tmp_path / "www" / owner / "snapshot.jpg"

    async def haunt(self, name: str) -> str:
        """Leave a file in a folder of `www`."""
        owner = name.lower()
        await self.bring_back(owner)
        return owner

    async def take_away(self, owner: str) -> None:
        """Remove the file."""
        await self.hass.async_add_executor_job(self._snapshot(owner).unlink)

    async def bring_back(self, owner: str) -> None:
        """Leave the file there again."""

        def _write() -> None:
            snapshot = self._snapshot(owner)
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_text("here", encoding="utf-8")

        await self.hass.async_add_executor_job(_write)


_EVERY_REPAIR = pytest.mark.parametrize(
    "haunting_class",
    [
        _EmptyArea,
        _EmptyFloor,
        _UnusedLabel,
        _UnusedBlueprint,
        _DuplicateResource,
        _PublicWwwFiles,
    ],
    ids=[
        "empty_areas",
        "empty_floors",
        "unused_labels",
        "unused_blueprints",
        "lovelace_duplicate_resources",
        "lovelace_public_www_files",
    ],
)


@pytest.fixture(autouse=True)
def _aged_blueprints(monkeypatch: pytest.MonkeyPatch) -> None:
    """Treat every blueprint file as old, so the grace period never hides it."""
    monkeypatch.setattr(unused_blueprints, "_file_mtime", lambda _path: 0.0)


@pytest.fixture(name="haunting")
def haunting_fixture(
    hass: HomeAssistant,
    tmp_path: Path,
    haunting_class: type[_Haunting],
) -> _Haunting:
    """Return the repair under test, and how to haunt it."""
    return haunting_class(hass, tmp_path)


def _issue(
    issue_registry: ir.IssueRegistry, repair: AbstractSpookRepair, owner: str
) -> ir.IssueEntry | None:
    """Return the issue about this one thing, if there is one."""
    return issue_registry.async_get_issue(DOMAIN, f"{repair.repair}_{owner}")


def _ignore(
    hass: HomeAssistant,
    repair: AbstractSpookRepair,
    owner: str,
    *,
    ignore: bool = True,
) -> None:
    """Press ignore on the issue about this one thing, or take it back."""
    ir.async_ignore_issue(hass, DOMAIN, f"{repair.repair}_{owner}", ignore=ignore)


async def _raised(
    freezer: FrozenDateTimeFactory, haunting: _Haunting
) -> tuple[AbstractSpookRepair, str]:
    """Have one thing reported, and return the repair and what it is filed under."""
    owner = await haunting.haunt("Attic")
    freezer.tick(_AGED)

    repair = haunting.repair()
    await repair._async_inspect_with_cleanup()

    return repair, owner


async def _away_and_back(
    haunting: _Haunting,
    repair: AbstractSpookRepair,
    owner: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Make the finding go, so the issue goes, and bring it back."""
    await haunting.take_away(owner)
    await repair._async_inspect_with_cleanup()
    assert _issue(issue_registry, repair, owner) is None, "the issue did not go"

    await haunting.bring_back(owner)
    await repair._async_inspect_with_cleanup()


@_EVERY_REPAIR
async def test_an_ignore_outlasts_the_issue(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    haunting: _Haunting,
) -> None:
    """Test an ignored issue about one thing comes back ignored.

    Home Assistant keeps an ignore on the issue, and Spook deletes the issue
    the moment the finding is gone. A floor that briefly had an area on it,
    or a folder emptied and filled again, came back as news.
    """
    await async_setup_dismissals(hass)
    repair, owner = await _raised(freezer, haunting)
    _ignore(hass, repair, owner)

    await _away_and_back(haunting, repair, owner, issue_registry)

    issue = _issue(issue_registry, repair, owner)
    assert issue
    assert issue.dismissed_version is not None, "it came back as news"


@_EVERY_REPAIR
async def test_taking_the_ignore_back_outlasts_the_issue(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    haunting: _Haunting,
) -> None:
    """Test an ignore taken back stays taken back once the issue returns."""
    await async_setup_dismissals(hass)
    repair, owner = await _raised(freezer, haunting)
    _ignore(hass, repair, owner)
    _ignore(hass, repair, owner, ignore=False)

    await _away_and_back(haunting, repair, owner, issue_registry)

    issue = _issue(issue_registry, repair, owner)
    assert issue
    assert issue.dismissed_version is None


@_EVERY_REPAIR
async def test_an_ignore_from_before_is_written_down(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    haunting: _Haunting,
) -> None:
    """Test an issue ignored on an older Spook keeps its ignore after updating.

    Older versions left this to Home Assistant alone, so the only record is
    the mark on the issue. The issue ID is the same as it was, so the mark is
    still there, and the first look writes it down.
    """
    repair, owner = await _raised(freezer, haunting)
    _ignore(hass, repair, owner)

    # Spook updated: dismissals arrive, and know nothing yet.
    hass.data.pop(DATA_DISMISSALS, None)
    await async_setup_dismissals(hass)
    dismissals = hass.data[DATA_DISMISSALS]
    assert dismissals.async_dismissed(repair.repair, owner) == set()

    repair = haunting.repair()
    await repair._async_inspect_with_cleanup()
    assert dismissals.async_dismissed(repair.repair, owner) == {owner}

    await _away_and_back(haunting, repair, owner, issue_registry)

    issue = _issue(issue_registry, repair, owner)
    assert issue
    assert issue.dismissed_version is not None


@_EVERY_REPAIR
async def test_an_ignore_is_about_that_one_thing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    haunting: _Haunting,
) -> None:
    """Test ignoring one thing leaves another one of the same repair alone."""
    await async_setup_dismissals(hass)
    repair, attic = await _raised(freezer, haunting)
    _ignore(hass, repair, attic)

    cellar = await haunting.haunt("Cellar")
    freezer.tick(_AGED)
    await repair._async_inspect_with_cleanup()
    await _away_and_back(haunting, repair, cellar, issue_registry)

    issue = _issue(issue_registry, repair, cellar)
    assert issue
    assert issue.dismissed_version is None
    assert hass.data[DATA_DISMISSALS].async_dismissed(repair.repair, cellar) == set()


async def test_the_issue_id_stays_what_it_was(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    tmp_path: Path,
) -> None:
    """Test the issue ID is not fingerprinted.

    An ignore made on an older Spook is only on the issue, under the ID it
    had then. Another ID would leave that ignore behind on an issue nobody
    raises anymore.
    """
    await async_setup_dismissals(hass)
    _repair, owner = await _raised(freezer, _EmptyArea(hass, tmp_path))

    assert owner == "attic"
    assert {
        issue_id for domain, issue_id in issue_registry.issues if domain == DOMAIN
    } == {"empty_areas_attic"}
