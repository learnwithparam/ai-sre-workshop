"""Read design/tokens.json and render the CSS the workbook and the guide import.

    python scripts/tokens.py        writes design/tokens.css (make tokens)

tests/test_house.py fails when the file on disk differs from what this renders, so the
copy cannot drift from the source without the gate saying so.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MINIMUM_RATIO = {"AA": 4.5, "AAA": 7.0, "AA-large": 3.0}


def tokens() -> dict:
    return json.loads((ROOT / "design/tokens.json").read_text())


def _channel(hex_value: str, at: int) -> float:
    value = int(hex_value[at : at + 2], 16) / 255
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def luminance(hex_value: str) -> float:
    """Relative luminance, WCAG 2.1 definition."""
    return 0.2126 * _channel(hex_value, 1) + 0.7152 * _channel(hex_value, 3) + 0.0722 * _channel(hex_value, 5)


def contrast_ratio(foreground: str, background: str) -> float:
    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def render_css(t: dict, surface: str) -> str:
    lines = [
        f"/* Generated from design/tokens.json for the {surface} surface. Do not edit.",
        " * Change design/tokens.json and run `make tokens`. A stale copy fails make check. */",
        ":root {",
    ]
    for name, token in t["color"].items():
        lines.append(f"\t--c-{name}: {token['value']}; /* {token['use']} */")
    for name, token in t["font"].items():
        lines.append(f"\t--font-{name}: {token['value']};")
    for name, value in t["size"].items():
        lines.append(f"\t--{name}: {value};")
    for name, value in t["page"].items():
        if not name.startswith("$"):
            lines.append(f"\t--page-{name}: {value}{'' if name == 'canvas' else 'mm'};")
    for name, value in t["space"].items():
        lines.append(f"\t--space-{name}: {value};")
    for name, value in t["radius"].items():
        lines.append(f"\t--radius-{name}: {value};")
    lines += ["}", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    t = tokens()
    for surface in t["surfaces"]:
        path = ROOT / surface["out"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_css(t, surface["name"]))
        print(f"wrote {surface['out']}")
