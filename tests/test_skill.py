"""Tests for the agent skill and the references generated for it.

The references are only worth something while they are complete. An agent
that does not find an action in them assumes it does not exist, and nobody
notices a reference falling behind by reading it.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING

import pytest
import yaml

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).parents[1]
SPOOK = ROOT / "custom_components" / "spook"
PLUGIN = ROOT / "plugins" / "spook"
SKILL = PLUGIN / "skills" / "spook"
REFERENCES = SKILL / "references"

# The Agent Skills specification caps the description at this many characters.
DESCRIPTION_LIMIT = 1024


def _generator() -> ModuleType:
    """Load the generator, which lives in a script rather than a package."""
    path = ROOT / "script" / "generate_skill.py"
    spec = importlib.util.spec_from_file_location("generate_skill", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frontmatter() -> dict[str, str]:
    """Return the frontmatter of SKILL.md."""
    text = (SKILL / "SKILL.md").read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md does not start with frontmatter"
    return yaml.safe_load(match[1])


def _headings(reference: str) -> set[str]:
    """Return the names a reference file has an entry for."""
    text = (REFERENCES / reference).read_text()
    return set(re.findall(r"^### `([a-z_]+\.[a-z_]+)`", text, re.MULTILINE))


def test_references_are_up_to_date(tmp_path: Path) -> None:
    """Regenerating changes nothing, so nobody forgot to run the generator."""
    _generator().write(tmp_path)

    generated = {path.name: path.read_text() for path in tmp_path.iterdir()}
    committed = {path.name: path.read_text() for path in REFERENCES.iterdir()}

    assert set(generated) == set(committed)
    stale = sorted(name for name in generated if generated[name] != committed[name])
    assert not stale, (
        f"out of date, run `python script/generate_skill.py`: {', '.join(stale)}"
    )


def test_skill_frontmatter() -> None:
    """The name matches the folder, and the description fits the spec."""
    frontmatter = _frontmatter()

    assert frontmatter["name"] == SKILL.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", frontmatter["name"])
    assert 0 < len(frontmatter["description"]) <= DESCRIPTION_LIMIT


def test_skill_links_to_files_that_exist() -> None:
    """A link to a reference that was renamed sends the agent nowhere."""
    text = (SKILL / "SKILL.md").read_text()
    links = re.findall(r"\]\((references/[^)]+)\)", text)

    assert links
    assert all((SKILL / link).is_file() for link in links)


def test_marketplace_points_at_the_plugin() -> None:
    """The install id is the entry name, and it has to match the plugin's."""
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())

    (entry,) = marketplace["plugins"]
    assert entry["name"] == plugin["name"]
    assert (ROOT / entry["source"]).resolve() == PLUGIN.resolve()


def test_every_action_is_in_the_references() -> None:
    """Every action in services.yaml has an entry, under its real name."""
    generator = _generator()
    domains = generator.action_domains()
    services = yaml.safe_load((SPOOK / "services.yaml").read_text())

    actions = {generator.action_name(key, domains) for key in services}
    assert len(actions) == len(services)
    assert actions == _headings("actions.md")


@pytest.mark.parametrize("kind", ["triggers", "conditions"])
def test_every_trigger_and_condition_is_in_the_references(kind: str) -> None:
    """Every trigger and condition Spook describes has an entry."""
    described = yaml.safe_load((SPOOK / f"{kind}.yaml").read_text())

    assert {f"spook.{key}" for key in described} == _headings(f"{kind}.md")


def test_every_repair_is_in_the_references() -> None:
    """Every repair Spook has a translation for has a line."""
    issues = json.loads((SPOOK / "translations" / "en.json").read_text())["issues"]
    text = (REFERENCES / "repairs.md").read_text()

    listed = set(re.findall(r"^- `([a-z_]+)`:", text, re.MULTILINE))
    assert listed == set(issues)


def test_action_names_follow_the_domain_they_are_on() -> None:
    """The services.yaml key is split on the domain, not the first underscore."""
    generator = _generator()
    domains = generator.action_domains()

    assert generator.action_name("boo", domains) == "spook.boo"
    assert (
        generator.action_name("input_select_random", domains) == "input_select.random"
    )
    assert (
        generator.action_name("homeassistant_add_label_to_entity", domains)
        == "homeassistant.add_label_to_entity"
    )
