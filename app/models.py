import json
from datetime import datetime

from .config import CATEGORY_ORDER, MODEL_CATALOG_PATH


def load_model_catalog():
    try:
        with MODEL_CATALOG_PATH.open("r", encoding="utf-8") as f:
            data = f.read()
    except FileNotFoundError:
        return []

    try:
        catalog = json.loads(data)
    except Exception:
        return []

    models = None
    if isinstance(catalog, dict):
        models = catalog.get("models")
    if not isinstance(models, list):
        return []

    normalized = []
    for model in models:
        if not isinstance(model, dict):
            continue
        model_id = model.get("id")
        if not model_id:
            continue
        normalized.append(
            {
                "id": model_id,
                "categories": list(model.get("categories", [])),
                "release_order": model.get("release_order"),
                "pricing": model.get("pricing", {}),
                "notes": model.get("notes", ""),
            }
        )
    return normalized


def infer_categories(model_id):
    lower = model_id.lower()
    categories = set()

    if lower.startswith("ft:") or ":ft:" in lower:
        categories.add("Fine-tuned")

    if lower.startswith("o1") or lower.startswith("o3") or "reason" in lower:
        categories.add("Reasoning")

    if "gpt-5" in lower:
        categories.update(["GPT-5", "Chat"])
    if "gpt-4" in lower:
        categories.update(["GPT-4", "Chat"])
    if "gpt-3.5" in lower or "gpt-3" in lower:
        categories.update(["GPT-3.5", "Chat"])

    if any(hint in lower for hint in ("realtime", "audio", "voice", "tts", "whisper")):
        categories.update(["Audio", "Voice"])

    if any(hint in lower for hint in ("image", "dall-e")):
        categories.add("Image")

    if "embedding" in lower:
        categories.add("Embeddings")

    if "moderation" in lower:
        categories.add("Moderation")

    if any(hint in lower for hint in ("vision", "multimodal", "4o")):
        categories.add("Multimodal")

    if any(
        hint in lower
        for hint in (
            "davinci",
            "curie",
            "babbage",
            "ada",
            "text-",
            "code-",
        )
    ):
        categories.add("Legacy")

    if not categories:
        categories.add("Other")

    return sorted(categories)


def merge_models(catalog_models, api_models):
    catalog_map = {model["id"]: model for model in catalog_models}
    merged = []
    seen = set()

    for api_model in api_models:
        model_id = api_model.get("id")
        if not model_id:
            continue
        base = catalog_map.get(model_id, {})
        categories = set(base.get("categories", []))
        categories.update(infer_categories(model_id))
        entry = {
            "id": model_id,
            "categories": sorted(categories),
            "release_order": base.get("release_order"),
            "pricing": base.get("pricing", {}),
            "created": api_model.get("created"),
            "available": True,
            "source": "catalog+api" if base else "api",
        }
        merged.append(entry)
        seen.add(model_id)

    for model in catalog_models:
        model_id = model["id"]
        if model_id in seen:
            continue
        categories = set(model.get("categories", []))
        categories.update(infer_categories(model_id))
        merged.append(
            {
                "id": model_id,
                "categories": sorted(categories),
                "release_order": model.get("release_order"),
                "pricing": model.get("pricing", {}),
                "created": None,
                "available": False,
                "source": "catalog",
            }
        )

    return merged


def sort_models_oldest_first(models):
    def sort_key(model):
        created = model.get("created")
        release_order = model.get("release_order")
        if isinstance(created, (int, float)):
            return (0, created, model["id"])
        if isinstance(release_order, (int, float)):
            return (1, release_order, model["id"])
        return (2, model["id"])

    return sorted(models, key=sort_key)


def build_categories_map(models):
    categories = {"All (Oldest->Newest)": sort_models_oldest_first(models)}
    for model in models:
        for category in model.get("categories", []):
            categories.setdefault(category, []).append(model)
    for category, items in categories.items():
        categories[category] = sort_models_oldest_first(items)
    return categories


def ordered_categories(categories_map):
    ordered = []
    for name in CATEGORY_ORDER:
        if name in categories_map:
            ordered.append(name)
    for name in sorted(categories_map.keys()):
        if name not in ordered:
            ordered.append(name)
    return ordered


def _format_cost(value):
    if value is None:
        return "?"
    if isinstance(value, (int, float)):
        return f"${value:.2f}"
    return str(value)


def format_pricing(pricing):
    if not pricing:
        return "Unknown (update pricing)"

    if isinstance(pricing, str):
        return pricing

    if isinstance(pricing, dict):
        summary = pricing.get("summary")
        if summary:
            return summary

        tiers = pricing.get("tiers")
        if isinstance(tiers, dict):
            standard = tiers.get("standard") or tiers.get("Standard")
            if isinstance(standard, dict):
                input_cost = _format_cost(standard.get("input"))
                output_cost = _format_cost(standard.get("output"))
                cached_cost = standard.get("cached_input") or standard.get(
                    "cached"
                )
                cached_cost = _format_cost(cached_cost)
                if input_cost == "?" and output_cost == "?":
                    return "Unknown (update pricing)"
                if cached_cost != "?":
                    return (
                        f"Standard: In {input_cost}/1M | Cached {cached_cost}/1M | "
                        f"Out {output_cost}/1M"
                    )
                return f"Standard: In {input_cost}/1M | Out {output_cost}/1M"

        if "input" in pricing or "output" in pricing:
            input_cost = _format_cost(pricing.get("input"))
            output_cost = _format_cost(pricing.get("output"))
            if input_cost == "?" and output_cost == "?":
                return "Unknown (update pricing)"
            return f"Input: {input_cost}/1M | Output: {output_cost}/1M"

    return "Unknown (update pricing)"


def format_created(created, release_order=None):
    if isinstance(created, (int, float)):
        return datetime.utcfromtimestamp(created).strftime("%Y-%m-%d")
    if release_order is not None:
        return f"Catalog order #{release_order}"
    return "Unknown"
