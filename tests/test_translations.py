"""Tests for translation files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

COMPONENT_PATH = Path("custom_components/spook")
PLACEHOLDER_PATTERN = re.compile(r"\{[^{}]+\}")


def _translation_paths() -> list[Path]:
    """Return every directory in Spook that ships translations.

    Discovered rather than listed, so a new sub-integration is covered the
    moment it gets a translations directory.
    """
    return sorted(COMPONENT_PATH.glob("**/translations"))


def _walk_translation_strings(
    base: dict[str, Any],
    translation: dict[str, Any],
    path: str = "",
) -> list[str]:
    """Return translation strings with mismatched placeholders."""
    mismatches: list[str] = []

    for key, base_value in base.items():
        key_path = f"{path}.{key}" if path else key

        if key not in translation:
            continue

        translation_value = translation[key]
        if isinstance(base_value, dict) and isinstance(translation_value, dict):
            mismatches.extend(
                _walk_translation_strings(base_value, translation_value, key_path)
            )
            continue

        if not isinstance(base_value, str) or not isinstance(translation_value, str):
            continue

        expected = set(PLACEHOLDER_PATTERN.findall(base_value))
        actual = set(PLACEHOLDER_PATTERN.findall(translation_value))
        if expected != actual:
            mismatches.append(
                f"{key_path}: expected {sorted(expected)}, got {sorted(actual)}"
            )

    return mismatches


def _blank_strings(translation: dict[str, Any], path: str = "") -> list[str]:
    """Return the paths of every string in the file that has no content."""
    blanks: list[str] = []

    for key, value in translation.items():
        key_path = f"{path}.{key}" if path else key

        if isinstance(value, dict):
            blanks.extend(_blank_strings(value, key_path))
            continue

        if isinstance(value, str) and not value.strip():
            blanks.append(key_path)

    return blanks


def test_translation_placeholders_match_english() -> None:
    """Test translation placeholders match the English source strings."""
    mismatches = []

    for translations_path in _translation_paths():
        english = json.loads(
            (translations_path / "en.json").read_text(encoding="utf-8")
        )

        for translation_file in sorted(translations_path.glob("*.json")):
            if translation_file.name == "en.json":
                continue

            translation = json.loads(translation_file.read_text(encoding="utf-8"))
            mismatches.extend(
                f"{translation_file}: {mismatch}"
                for mismatch in _walk_translation_strings(english, translation)
            )

    assert not mismatches, "\n".join(mismatches)


def test_translations_hold_no_blank_strings() -> None:
    """Test no translation file carries a string without content.

    Home Assistant loads English first and then overlays the requested
    language with a plain dictionary update. An empty string is a value, not
    a missing key, so it wins: the label renders blank instead of falling
    back to English. A string nobody has translated yet belongs out of the
    file, not in it as "".
    """
    blanks = [
        f"{translation_file}: {key}"
        for translations_path in _translation_paths()
        for translation_file in sorted(translations_path.glob("*.json"))
        for key in _blank_strings(
            json.loads(translation_file.read_text(encoding="utf-8"))
        )
    ]

    assert not blanks, f"{len(blanks)} blank strings found:\n" + "\n".join(blanks)
