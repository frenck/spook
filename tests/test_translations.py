"""Tests for translation files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

TRANSLATIONS_PATH = Path("custom_components/spook/translations")
PLACEHOLDER_PATTERN = re.compile(r"\{[^{}]+\}")


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


def test_translation_placeholders_match_english() -> None:
    """Test translation placeholders match the English source strings."""
    english = json.loads((TRANSLATIONS_PATH / "en.json").read_text(encoding="utf-8"))
    mismatches = []

    for translation_file in sorted(TRANSLATIONS_PATH.glob("*.json")):
        if translation_file.name == "en.json":
            continue

        translation = json.loads(translation_file.read_text(encoding="utf-8"))
        mismatches.extend(
            f"{translation_file.name}: {mismatch}"
            for mismatch in _walk_translation_strings(english, translation)
        )

    assert not mismatches, "\n".join(mismatches)
