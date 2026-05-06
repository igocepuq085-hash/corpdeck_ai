import re
from typing import Any


ALLOWED_SLIDE_TYPES = {
    "cover",
    "problem",
    "analysis",
    "kpi",
    "process",
    "solution",
    "economics",
    "roadmap",
    "final",
}

ALLOWED_VISUAL_TYPES = {
    "abstract",
    "business",
    "people",
    "technology",
    "industry",
    "finance",
    "process",
    "roadmap",
    "final",
    "general",
    "transport",
    "safety",
    "digital",
    "education",
    "production",
    "regulation",
}

ALLOWED_CHART_TYPES = {"bar", "line", "donut", "timeline"}


def normalize_slide_payload(slide: dict[str, Any]) -> dict[str, Any]:
    """Normalize AI slide payload into the strict MVP content contract."""
    source = slide if isinstance(slide, dict) else {}
    slide_type = str(source.get("type") or "analysis").strip()
    if slide_type not in ALLOWED_SLIDE_TYPES:
        slide_type = "analysis"

    visual_type = str(source.get("visual_type") or source.get("semantic_category") or "general").strip()
    if visual_type not in ALLOWED_VISUAL_TYPES:
        visual_type = "general"

    return {
        "type": slide_type,
        "title": _shorten(source.get("title"), 90),
        "subtitle": _shorten(source.get("subtitle"), 180),
        "main_message": _shorten(source.get("main_message") or source.get("message"), 140),
        "bullets": [_shorten(item, 160) for item in _list(source.get("bullets"))[:5] if _shorten(item, 160)],
        "kpis": normalize_kpis(source.get("kpis")),
        "steps": normalize_steps(source.get("steps")),
        "charts": normalize_charts(source.get("charts")),
        "tables": normalize_tables(source.get("tables")),
        "conclusion": _shorten(source.get("conclusion"), 200),
        "visual_type": visual_type,
        "semantic_category": visual_type,
    }


def normalize_kpis(value: Any) -> list[dict[str, str]]:
    result = []
    for item in _list(value)[:4]:
        if not isinstance(item, dict):
            continue
        kpi = {
            "label": _shorten(item.get("label") or item.get("name") or item.get("title"), 80),
            "value": _shorten(item.get("value") or item.get("number") or item.get("metric"), 40),
            "note": _shorten(item.get("note") or item.get("comment") or item.get("description"), 140),
        }
        if kpi["label"] and kpi["value"]:
            result.append(kpi)
    return result


def normalize_steps(value: Any) -> list[dict[str, str]]:
    result = []
    for item in _list(value)[:6]:
        if isinstance(item, dict):
            step = {
                "title": _shorten(item.get("title") or item.get("name"), 80),
                "text": _shorten(item.get("text") or item.get("description") or item.get("content"), 160),
            }
        else:
            step = {"title": "", "text": _shorten(item, 160)}
        if step["title"] or step["text"]:
            result.append(step)
    return result


def normalize_charts(value: Any) -> list[dict[str, Any]]:
    result = []
    for item in _list(value):
        if not isinstance(item, dict):
            continue
        chart_type = str(item.get("chart_type") or item.get("type") or "").strip()
        if chart_type not in ALLOWED_CHART_TYPES:
            continue
        if chart_type == "timeline":
            # Timeline is rendered from steps in the MVP. Keep the type reserved,
            # but do not pass it as a chart until the renderer supports it.
            continue

        labels = [_shorten(label, 60) for label in _list(item.get("labels"))]
        series = []
        for series_item in _list(item.get("series"))[:2]:
            if not isinstance(series_item, dict):
                continue
            values = [_to_number(raw) for raw in _list(series_item.get("values"))]
            values = [number for number in values if number is not None]
            if len(values) != len(labels):
                continue
            if chart_type == "line" and len(values) < 3:
                continue
            if chart_type in {"bar", "donut"} and len(values) < 2:
                continue
            series.append(
                {
                    "name": _shorten(series_item.get("name") or "Показатель", 80),
                    "values": values,
                }
            )
        if not labels or not series:
            continue

        first_values = series[0]["values"]
        max_value = max([abs(number) for number in first_values] or [1]) or 1
        render_points = [
            {
                "label": labels[index],
                "value": first_values[index],
                "width": max(8, min(100, round(abs(first_values[index]) / max_value * 100))),
            }
            for index in range(len(labels))
        ]
        result.append(
            {
                "chart_type": chart_type,
                "title": _shorten(item.get("title"), 120),
                "labels": labels,
                "series": series[:1],
                "unit": _shorten(item.get("unit"), 30),
                "source_note": _shorten(item.get("source_note") or "Данные извлечены из документа", 120),
                "render_points": render_points,
            }
        )
        break
    return result


def normalize_tables(value: Any) -> list[dict[str, Any]]:
    result = []
    for item in _list(value):
        if not isinstance(item, dict):
            continue
        columns = [_shorten(column, 50) for column in _list(item.get("columns"))[:5]]
        rows = []
        for row in _list(item.get("rows"))[:6]:
            row_values = [_shorten(cell, 80) for cell in _list(row)[: len(columns)]]
            if row_values:
                rows.append(row_values)
        if not columns or not rows:
            continue
        result.append(
            {
                "title": _shorten(item.get("title"), 120),
                "columns": columns,
                "rows": rows,
                "source_note": _shorten(item.get("source_note") or "Данные извлечены из документа", 120),
            }
        )
        break
    return result


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _shorten(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    cutoff = max(0, limit - 1)
    shortened = text[:cutoff].rstrip()
    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0].rstrip()
    return f"{shortened}…"


def _to_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value or "").replace(" ", "").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None
