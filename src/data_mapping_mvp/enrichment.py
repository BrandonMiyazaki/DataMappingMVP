"""Deterministic enrichment applied to extracted measurements before CSV mapping.

Content Understanding extracts what is present in the raw text. This module fills
the gaps that the desired output requires but that are not stated on every source
line: constant context (line/shift), work-order propagation, station-ID
normalization, engineering spec limits, and result-synonym normalization.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_LINE = "Line 2"
DEFAULT_SHIFT = "Day"

# Exact (whole-string) result tokens that are too short for safe substring matching.
_RESULT_EXACT: Dict[str, str] = {
    "y": "PASS",
    "yes": "PASS",
    "p": "PASS",
    "n": "FAIL",
    "no": "FAIL",
    "f": "FAIL",
}

# Raw result text (lowercased, matched as substring) -> normalized result.
# Order matters: the first matching entry wins.
_RESULT_SYNONYMS: List[Tuple[str, str]] = [
    ("review", "REVIEW"),
    ("hold", "HOLD"),
    ("info", "INFO"),
    ("fail", "FAIL"),
    ("reject", "FAIL"),
    ("ng", "FAIL"),
    ("pass", "PASS"),
    ("accept", "PASS"),
    ("release approved", "PASS"),
    ("good", "PASS"),
    ("ok", "PASS"),
]

# Station keyword (lowercased substring) -> canonical station id.
_STATION_KEYWORDS: List[Tuple[str, str]] = [
    ("stn-01", "STN-01"),
    ("station 01", "STN-01"),
    ("station01", "STN-01"),
    ("cell a", "STN-01"),
    ("torque station", "STN-01"),
    ("stn-03", "STN-03"),
    ("stn 03", "STN-03"),
    ("press#03", "STN-03"),
    ("press-fit", "STN-03"),
    ("press fit", "STN-03"),
    ("ftb-07", "FTB-07"),
    ("ftb", "FTB-07"),
    ("functional", "FTB-07"),
    ("l-2", "L-2"),
    ("leak", "L-2"),
    ("v4", "V4"),
    ("vision", "V4"),
    ("pack-out", "Pack-Out"),
    ("pack out", "Pack-Out"),
    ("packout", "Pack-Out"),
    ("electrical", "Electrical"),
]

# Test category (lowercased) -> canonical station id used when nothing else matches.
_CATEGORY_STATION_FALLBACK: Dict[str, str] = {
    "torque": "STN-01",
    "press fit": "STN-03",
    "leak": "L-2",
    "vision": "V4",
    "functional": "FTB-07",
    "electrical": "Electrical",
    "pack-out": "Pack-Out",
}

# (category, measurement-name keyword) -> (lower, upper, target, duration_s).
_SPEC_RULES: List[Tuple[str, str, Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]]] = [
    ("torque", "angle", (42, 48, 45, None)),
    ("torque", "torque", (18, 19, 18.5, None)),
    ("press fit", "depth", (11.8, 12.2, 12, None)),
    ("press fit", "force", (4.5, 5.2, 4.85, None)),
    ("leak", "drop", (None, 1.5, 0, 10)),
    ("leak", "pressure", (None, 1.5, 0, 10)),
    ("vision", "offset", (-0.5, 0.5, 0, None)),
    ("vision", "confidence", (95, 100, 100, None)),
    ("vision", "ocr", (95, 100, 100, None)),
    ("vision", "skew", (0, 2.5, 0, None)),
    ("functional", "current", (1.5, 2.2, 1.9, None)),
    ("functional", "speed", (1450, 1520, 1500, None)),
    ("functional", "vibration", (0, 3, 0, None)),
    ("functional", "voltage", (23.5, 24.5, 24, None)),
    ("electrical", "resist", (0, 0.22, 0, None)),
    ("pack-out", "accessory", (3, 3, 3, None)),
]


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _is_blank(value: Any) -> bool:
    return _text(value) == ""


def normalize_result(value: Any) -> str:
    text = _text(value).lower()
    if text in _RESULT_EXACT:
        return _RESULT_EXACT[text]
    for keyword, normalized in _RESULT_SYNONYMS:
        if keyword in text:
            return normalized
    return _text(value).upper()


def normalize_station_id(station: Any, test_category: Any) -> str:
    text = _text(station).lower()
    for keyword, canonical in _STATION_KEYWORDS:
        if keyword in text:
            return canonical
    fallback = _CATEGORY_STATION_FALLBACK.get(_text(test_category).lower())
    if fallback:
        return fallback
    return _text(station)


def lookup_spec(test_category: Any, measurement_name: Any):
    category = _text(test_category).lower()
    name = _text(measurement_name).lower()
    for spec_category, name_keyword, spec in _SPEC_RULES:
        if spec_category == category and name_keyword in name:
            return spec
    return (None, None, None, None)


def _resolve_work_order(measurements: List[Dict[str, Any]]) -> None:
    distinct = {
        _text(m.get("workOrder")) for m in measurements if not _is_blank(m.get("workOrder"))
    }
    if len(distinct) == 1:
        only = next(iter(distinct))
        for measurement in measurements:
            if _is_blank(measurement.get("workOrder")):
                measurement["workOrder"] = only
        return

    # Multiple work orders: carry the most recent one forward, then backfill leaders.
    last_seen: Optional[str] = None
    for measurement in measurements:
        if not _is_blank(measurement.get("workOrder")):
            last_seen = _text(measurement.get("workOrder"))
        elif last_seen is not None:
            measurement["workOrder"] = last_seen

    first_seen = next(
        (_text(m.get("workOrder")) for m in measurements if not _is_blank(m.get("workOrder"))),
        None,
    )
    if first_seen is not None:
        for measurement in measurements:
            if _is_blank(measurement.get("workOrder")):
                measurement["workOrder"] = first_seen


def enrich_measurements(
    measurements: List[Dict[str, Any]],
    *,
    default_line: Optional[str] = DEFAULT_LINE,
    default_shift: Optional[str] = DEFAULT_SHIFT,
    fill_specs: bool = True,
) -> List[Dict[str, Any]]:
    """Return enriched copies of the measurements with gaps filled deterministically."""
    enriched = [dict(measurement) for measurement in measurements]

    for measurement in enriched:
        if not _is_blank(measurement.get("result")):
            measurement["result"] = normalize_result(measurement.get("result"))

        measurement["stationId"] = normalize_station_id(
            measurement.get("stationId"), measurement.get("testCategory")
        )

        if default_line and _is_blank(measurement.get("line")):
            measurement["line"] = default_line
        if default_shift and _is_blank(measurement.get("shift")):
            measurement["shift"] = default_shift

        if fill_specs:
            lower, upper, target, duration = lookup_spec(
                measurement.get("testCategory"), measurement.get("measurementName")
            )
            if lower is not None and _is_blank(measurement.get("lowerSpecLimit")):
                measurement["lowerSpecLimit"] = lower
            if upper is not None and _is_blank(measurement.get("upperSpecLimit")):
                measurement["upperSpecLimit"] = upper
            if target is not None and _is_blank(measurement.get("targetValue")):
                measurement["targetValue"] = target
            if duration is not None and _is_blank(measurement.get("testDurationSeconds")):
                measurement["testDurationSeconds"] = duration

    _resolve_work_order(enriched)
    return enriched
