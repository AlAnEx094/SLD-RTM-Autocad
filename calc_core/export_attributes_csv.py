from __future__ import annotations

from pathlib import Path
from typing import Any
import math


def load_mapping(path: str | Path) -> dict:
    mapping_path = Path(path)
    text = mapping_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        data = _parse_simple_yaml(text, mapping_path)
    else:
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"Mapping root must be a dict: {mapping_path}")
    return data


def build_rows_from_payload(payload: dict, mapping: dict) -> dict[str, list[list[str]]]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    if not isinstance(mapping, dict):
        raise ValueError("mapping must be a dict")

    panel_cfg = _require_mapping_section(mapping, "panel")
    circuits_cfg = _require_mapping_section(mapping, "circuits")
    sections_cfg = _require_mapping_section(mapping, "sections")

    panel_guid = _require_guid(_get_path_value(payload, "panel.panel_id"), "panel.panel_id")
    panel_rows = _build_panel_rows(payload, panel_cfg, panel_guid)

    circuits_rows = _build_circuits_rows(payload, circuits_cfg)
    sections_rows = _build_sections_rows(payload, sections_cfg)

    return {
        "panel": panel_rows,
        "circuits": circuits_rows,
        "sections": sections_rows,
    }


def _require_mapping_section(mapping: dict, key: str) -> dict:
    section = mapping.get(key)
    if not isinstance(section, dict):
        raise ValueError(f"Mapping section '{key}' is required and must be a dict")
    attrs = section.get("attributes")
    if not isinstance(attrs, dict):
        raise ValueError(f"Mapping '{key}.attributes' must be a dict")
    return section


def _build_panel_rows(payload: dict, panel_cfg: dict, panel_guid: str) -> list[list[str]]:
    attrs = panel_cfg["attributes"]
    rows: list[list[str]] = []
    for attr, path in attrs.items():
        value = _get_path_value(payload, str(path))
        rows.append([panel_guid, str(attr), _format_value(str(path), value)])
    return rows


def _build_circuits_rows(payload: dict, circuits_cfg: dict) -> list[list[str]]:
    attrs = circuits_cfg["attributes"]
    circuits = payload.get("circuits", [])
    if not isinstance(circuits, list):
        raise ValueError("payload.circuits must be a list")
    rows: list[list[str]] = []
    for circuit in circuits:
        if not isinstance(circuit, dict):
            raise ValueError("payload.circuits[] must be dicts")
        guid = _require_guid(circuit.get("circuit_id"), "circuits[].circuit_id")
        for attr, path in attrs.items():
            value = _get_path_value(circuit, str(path))
            rows.append([guid, str(attr), _format_value(str(path), value)])
    return rows


def _build_sections_rows(payload: dict, sections_cfg: dict) -> list[list[str]]:
    attrs = sections_cfg["attributes"]
    modes = sections_cfg.get("modes")
    if not isinstance(modes, list) or not modes:
        raise ValueError("Mapping 'sections.modes' must be a non-empty list")
    sections = payload.get("bus_sections", [])
    if not isinstance(sections, list):
        raise ValueError("payload.bus_sections must be a list")

    rows: list[list[str]] = []
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("payload.bus_sections[] must be dicts")
        guid = _require_guid(section.get("bus_section_id"), "bus_sections[].bus_section_id")
        for mode in modes:
            mode_str = str(mode)
            for attr, path in attrs.items():
                path_str = str(path).replace("{MODE}", mode_str)
                value = _get_path_value(section, path_str)
                rows.append(
                    [guid, mode_str, str(attr), _format_value(path_str, value)]
                )
    return rows


def _require_guid(value: object, ctx: str) -> str:
    if value is None:
        raise ValueError(f"Missing GUID at {ctx}")
    text = str(value).strip()
    if not text:
        raise ValueError(f"Empty GUID at {ctx}")
    return text


def _get_path_value(obj: object, path: str) -> object:
    if not path:
        return None
    current: object = obj
    for part in path.split("."):
        if part == "":
            continue
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _format_value(path: str, value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        num = float(value)
        if not math.isfinite(num):
            return ""
        decimals = _decimals_for_path(path)
        if decimals is None:
            return _format_default_number(num)
        return f"{num:.{decimals}f}"
    return str(value)


def _decimals_for_path(path: str) -> int | None:
    segment = path.split(".")[-1].lower()
    if segment == "length_m":
        return 0
    if segment in {"du_pct", "du_limit_pct"}:
        return 2
    if segment in {"ip_a", "i_a", "i_calc_a"} or segment.endswith("_a"):
        return 1
    if segment in {
        "pp_kw",
        "qp_kvar",
        "sp_kva",
        "p_kw",
        "q_kvar",
        "s_kva",
    }:
        return 2
    if segment.endswith("_kw") or segment.endswith("_kvar") or segment.endswith("_kva"):
        return 2
    return None


def _format_default_number(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    if text in {"-0", "-0.0", ""}:
        return "0"
    return text


def _parse_simple_yaml(text: str, path: Path) -> dict:
    lines = text.splitlines()
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(0, root)]

    i = 0
    while i < len(lines):
        raw = _strip_comment(lines[i])
        if not raw.strip():
            i += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2 != 0:
            raise ValueError(f"Invalid indentation in {path} at line {i + 1}")
        line = raw.lstrip(" ")

        while indent < stack[-1][0]:
            stack.pop()
        if indent > stack[-1][0] and indent != stack[-1][0] + 2:
            raise ValueError(f"Unexpected indentation in {path} at line {i + 1}")

        container = stack[-1][1]
        if line.startswith("- "):
            if not isinstance(container, list):
                raise ValueError(f"List item without list in {path} at line {i + 1}")
            container.append(_parse_scalar(line[2:].strip()))
            i += 1
            continue

        if ":" not in line:
            raise ValueError(f"Expected 'key: value' in {path} at line {i + 1}")
        key, rest = line.split(":", 1)
        key = key.strip()
        rest = rest.strip()

        if rest == "":
            new_obj = _peek_container(lines, i + 1, indent)
            if not isinstance(container, dict):
                raise ValueError(f"Mapping without dict in {path} at line {i + 1}")
            container[key] = new_obj
            stack.append((indent + 2, new_obj))
            i += 1
            continue

        if not isinstance(container, dict):
            raise ValueError(f"Scalar in non-dict in {path} at line {i + 1}")
        container[key] = _parse_scalar(rest)
        i += 1

    return root


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    for idx, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:idx]
    return line


def _peek_container(lines: list[str], start: int, indent: int) -> Any:
    j = start
    while j < len(lines):
        raw = _strip_comment(lines[j])
        if not raw.strip():
            j += 1
            continue
        next_indent = len(raw) - len(raw.lstrip(" "))
        if next_indent <= indent:
            return {}
        if raw.lstrip(" ").startswith("- "):
            return []
        return {}
    return {}


def _parse_scalar(value: str) -> Any:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        items = [item.strip() for item in inner.split(",")]
        return [_parse_scalar(item) for item in items if item]
    if value and value[0] in {"'", '"'} and value[-1] == value[0]:
        return value[1:-1]
    return value
