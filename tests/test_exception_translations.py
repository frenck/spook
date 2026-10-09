"""Tests that Spook's translated errors have the text they ask for.

Spook and each of its sub integrations have a domain and translations of
their own, so every error is held to the integration it is raised in.
"""

from __future__ import annotations

import ast
from functools import cache
import json
from pathlib import Path
import re

from custom_components.spook import const

SPOOK = Path(const.__file__).parent
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def _integration(path: Path) -> Path:
    """Return the folder of the integration a module belongs to."""
    parts = path.relative_to(SPOOK).parts
    if parts[0] == "integrations" and len(parts) > 1:
        sub_integration = SPOOK / "integrations" / parts[1]
        if (sub_integration / "manifest.json").exists():
            return sub_integration
    return SPOOK


@cache
def _exceptions(integration: Path) -> dict[str, dict[str, str]]:
    """Return the error texts of an integration, in English."""
    translations = json.loads((integration / "translations" / "en.json").read_text())
    return translations.get("exceptions", {})


def _integrations() -> list[Path]:
    """Return Spook and each of its sub integrations."""
    return [
        SPOOK,
        *sorted(
            manifest.parent for manifest in SPOOK.glob("integrations/*/manifest.json")
        ),
    ]


def _own_domain_names(tree: ast.Module, path: Path) -> set[str]:
    """Return the names a module gives the domain of its own integration.

    Many modules import the domain of the integration their action belongs
    to as `DOMAIN`, and Spook's as `SPOOK_DOMAIN`. A sub integration can
    import Spook's too. Only the one from the integration's own `const.py`
    counts here, so a relative import is followed to the file it names.
    """
    own_constants = _integration(path) / "const.py"
    names = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ImportFrom) and node.level):
            continue
        package = path.parent
        for _ in range(node.level - 1):
            package = package.parent
        if package / f"{node.module}.py" != own_constants:
            continue
        names.update(
            alias.asname or alias.name for alias in node.names if alias.name == "DOMAIN"
        )
    return names


def _possible_keys(key: ast.expr) -> list[str] | None:
    """Return each translation key an error can ask for, None if unclear.

    Written out, or a choice between keys that are. Anything picked in a way
    this cannot follow is reported, rather than trusted.
    """
    if isinstance(key, ast.Constant) and isinstance(key.value, str):
        return [key.value]
    if isinstance(key, ast.IfExp):
        body, orelse = _possible_keys(key.body), _possible_keys(key.orelse)
        if body is not None and orelse is not None:
            return body + orelse
    return None


def _raised_translations() -> list[tuple[str, Path, str, set[str] | None]]:
    """Return each translated error Spook raises.

    As where it is, the integration it is raised in, its translation key, and
    the placeholders it passes, or None when those are not written out where
    it is raised.
    """
    found = []
    for path in sorted(SPOOK.rglob("*.py")):
        tree = ast.parse(path.read_text())
        own_domain = _own_domain_names(tree, path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            domain = keywords.get("translation_domain")
            key = keywords.get("translation_key")
            if not (
                isinstance(domain, ast.Name)
                and domain.id in own_domain
                and key is not None
            ):
                continue

            keys = _possible_keys(key)
            if keys is None:
                found.append(
                    (
                        f"{path.relative_to(SPOOK)}:{node.lineno}",
                        _integration(path),
                        "<run time>",
                        None,
                    )
                )
                continue

            placeholders: set[str] | None = set()
            if (given := keywords.get("translation_placeholders")) is not None:
                placeholders = (
                    {
                        item.value
                        for item in given.keys
                        if isinstance(item, ast.Constant)
                    }
                    if isinstance(given, ast.Dict)
                    else None
                )
            found.extend(
                (
                    f"{path.relative_to(SPOOK)}:{node.lineno}",
                    _integration(path),
                    each,
                    placeholders,
                )
                for each in keys
            )
    return found


def test_every_error_uses_its_own_texts() -> None:
    """Test a translated error never names another integration's domain.

    Many modules import their integration's `DOMAIN` from Home Assistant and
    Spook's as `SPOOK_DOMAIN`. An error passing the wrong one looks for its
    text in an integration that does not have it, and shows the bare key.
    """
    problems = []
    for path in sorted(SPOOK.rglob("*.py")):
        tree = ast.parse(path.read_text())
        own_domain = _own_domain_names(tree, path)
        problems.extend(
            f"{path.relative_to(SPOOK)}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for keyword in node.keywords
            if keyword.arg == "translation_domain"
            and not (
                isinstance(keyword.value, ast.Name) and keyword.value.id in own_domain
            )
        )

    assert not problems


def test_every_raised_error_has_its_text() -> None:
    """Test each error asks for a text that exists, with the same placeholders.

    A missing text shows people the bare translation key. A placeholder that
    does not match leaves `{area_id}` in the message, or drops the one thing
    that says what went wrong.
    """
    problems = []
    for where, integration, key, placeholders in _raised_translations():
        texts = _exceptions(integration)
        if key not in texts:
            problems.append(f"{where}: no text for {key}")
            continue
        wanted = set(PLACEHOLDER.findall(texts[key]["message"]))
        if placeholders is not None and placeholders != wanted:
            problems.append(f"{where}: {key} passes {placeholders}, wants {wanted}")

    assert not problems


def test_every_text_is_used() -> None:
    """Test no error text outlives the errors that used it."""
    raised = _raised_translations()
    for integration in _integrations():
        used = {
            key
            for _where, raised_in, key, _placeholders in raised
            if raised_in == integration
        }

        assert set(_exceptions(integration)) == used, integration.name
