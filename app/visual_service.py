import json
from pathlib import Path


VISUAL_LIBRARY_PATH = Path("static/assets/visual_library.json")
STYLE_NAME = "light_premium_corporate"

ROLE_TO_ASSET_ROLE = {
    "background": "background_visual",
    "hero": "hero_visual",
    "support": "support_visual",
    "icon": "icon_visual",
}


def load_visual_library() -> list[dict]:
    try:
        with VISUAL_LIBRARY_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def get_enabled_visual_assets() -> list[dict]:
    return [asset for asset in load_visual_library() if isinstance(asset, dict) and asset.get("enabled") is True]


def select_visual_asset(
    visual_intent: dict,
    document_context: dict,
    layout_type: str,
) -> dict:
    intent = visual_intent if isinstance(visual_intent, dict) else {}
    domain = str((document_context or {}).get("domain") or "")
    role = _infer_role(str(intent.get("role") or "none"), layout_type)
    semantic_category = _infer_semantic_category(
        str(intent.get("semantic_category") or ""),
        domain,
        layout_type,
    )

    required_visual_role = ROLE_TO_ASSET_ROLE.get(role, f"{role}_visual")
    preferred_asset = _preferred_asset_id(semantic_category, required_visual_role, layout_type, domain)
    if preferred_asset:
        asset = _asset_by_id(preferred_asset)
        if asset and _asset_is_safe_match(
            asset=asset,
            semantic_category=str(asset.get("semantic_category") or semantic_category),
            visual_role=str(asset.get("visual_role") or required_visual_role),
            domain=domain,
            layout_type=layout_type,
        ):
            result = dict(asset)
            result["asset_source"] = "library"
            return result

    for asset in get_enabled_visual_assets():
        if not _asset_is_safe_match(
            asset=asset,
            semantic_category=semantic_category,
            visual_role=required_visual_role,
            domain=domain,
            layout_type=layout_type,
        ):
            continue
        result = dict(asset)
        result["asset_source"] = "library"
        return result

    return _css_fallback_asset(semantic_category, role)


def _infer_role(role: str, layout_type: str) -> str:
    role = (role or "none").strip()
    if role and role != "none":
        return role
    if layout_type == "cover_light":
        return "hero"
    if layout_type in {"problem_metrics_light", "roadmap_light", "final_light"}:
        return "support"
    if layout_type == "data_dashboard_light":
        return "icon"
    return "support"


def _infer_semantic_category(category: str, domain: str, layout_type: str) -> str:
    category = (category or "").strip()
    if category and category != "neutral":
        return category
    if layout_type == "roadmap_light":
        return "roadmap"
    if layout_type == "data_dashboard_light":
        return "analytics"
    domain_map = {
        "transport": "transport",
        "it_digital": "digital",
        "safety": "safety",
        "education": "education",
        "production": "production",
        "finance": "finance",
        "project_management": "strategy",
        "legal_compliance": "communication",
    }
    return domain_map.get(domain, "transport")


def _preferred_asset_id(
    semantic_category: str,
    visual_role: str,
    layout_type: str,
    domain: str,
) -> str:
    if layout_type == "cover_light":
        if semantic_category == "digital":
            return "hero_digital_control_light"
        if semantic_category == "safety":
            return "hero_safety_light"
        return "hero_cover_transport_light"
    if layout_type == "roadmap_light":
        return "icon_transport_route" if domain == "transport" else "icon_strategy_roadmap"
    if layout_type == "data_dashboard_light":
        return "icon_finance_growth" if semantic_category == "finance" else "icon_analytics_chart"
    if layout_type == "final_light":
        return "icon_strategy_roadmap"
    category_to_id = {
        "transport": "icon_transport_locomotive",
        "digital": "icon_digital_dashboard",
        "safety": "icon_safety_shield",
        "education": "icon_education_training",
        "production": "icon_production_hub",
        "analytics": "icon_analytics_chart",
        "finance": "icon_finance_growth",
        "strategy": "icon_strategy_roadmap",
        "communication": "icon_protocol_document",
        "roadmap": "icon_transport_route",
    }
    return category_to_id.get(semantic_category, "icon_transport_locomotive")


def _asset_by_id(asset_id: str) -> dict:
    for asset in get_enabled_visual_assets():
        if asset.get("id") == asset_id:
            return asset
    return {}


def _asset_is_safe_match(
    asset: dict,
    semantic_category: str,
    visual_role: str,
    domain: str,
    layout_type: str,
) -> bool:
    if asset.get("semantic_category") != semantic_category:
        return False
    if asset.get("visual_role") != visual_role:
        return False
    if asset.get("style") != STYLE_NAME:
        return False
    if asset.get("contains_text") is True or asset.get("contains_numbers") is True:
        return False

    forbidden_domains = asset.get("forbidden_domains") if isinstance(asset.get("forbidden_domains"), list) else []
    if domain and domain in forbidden_domains:
        return False

    allowed_domains = asset.get("allowed_domains") if isinstance(asset.get("allowed_domains"), list) else []
    if allowed_domains and domain not in allowed_domains:
        return False

    allowed_layouts = asset.get("allowed_layouts") if isinstance(asset.get("allowed_layouts"), list) else []
    if allowed_layouts and layout_type not in allowed_layouts:
        return False

    return True


def _css_fallback_asset(semantic_category: str, role: str) -> dict:
    return {
        "id": "css_fallback",
        "enabled": False,
        "semantic_category": semantic_category or "neutral",
        "visual_role": role or "support",
        "file": "",
        "asset_source": "css_fallback",
        "style": STYLE_NAME,
    }
