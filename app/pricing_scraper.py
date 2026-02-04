import json
import re
import time
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from .config import MODEL_CATALOG_PATH

MODELS_URL = "https://platform.openai.com/docs/models"
PRICING_URL = "https://platform.openai.com/docs/pricing"

SECTION_HEADERS = {
    "Text tokens",
    "Image tokens",
    "Audio tokens",
    "Video",
    "Embeddings",
    "Legacy models",
    "Transcription and speech generation",
    "Image generation",
}

TIER_HEADERS = {
    "Batch",
    "Flex",
    "Standard",
    "Priority",
    "Batch Standard",
    "Batch Flex",
}

COLUMN_HEADERS = {
    "Input",
    "Cached input",
    "Cached Input",
    "Output",
    "Training",
    "Cost",
    "Quality",
    "Use case",
    "Estimated cost",
    "Size: Output resolution",
    "Price per second",
    "Model",
}

NAME_MAP = {
    "GPT Image 1.5": "gpt-image-1.5",
    "GPT Image Latest": "chatgpt-image-latest",
    "GPT Image 1": "gpt-image-1",
    "GPT Image 1 Mini": "gpt-image-1-mini",
    "DALL·E 3": "dall-e-3",
    "DALL·E 2": "dall-e-2",
    "TTS-1": "tts-1",
    "TTS-1 HD": "tts-1-hd",
    "Whisper": "whisper-1",
}


@dataclass
class PricingTable:
    section: str
    tier: str
    unit: str
    columns: list
    model: str
    values: dict


def _fetch(url):
    response = requests.get(
        url,
        headers={
            "User-Agent": "OpenAI API Communicator/1.0",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def _extract_model_ids(html):
    ids = set()
    for match in re.findall(r"/docs/models/([a-zA-Z0-9\-\.]+)", html):
        ids.add(match)
    return sorted(ids)


def fetch_model_ids():
    html = _fetch(MODELS_URL)
    return _extract_model_ids(html)


def _normalize_model_id(name):
    name = name.strip()
    if name in NAME_MAP:
        return NAME_MAP[name]

    normalized = name.lower()
    normalized = normalized.replace("·", "")
    normalized = normalized.replace("–", "-")
    normalized = normalized.replace(":", "")
    normalized = normalized.replace("(", "")
    normalized = normalized.replace(")", "")
    normalized = normalized.replace("'", "")
    normalized = normalized.replace("\u2019", "")
    normalized = normalized.replace(" ", "-")
    normalized = normalized.replace("--", "-")
    return normalized


def _clean_lines(text):
    lines = [line.strip() for line in text.splitlines()]
    return [line for line in lines if line]


def _is_stop_line(line):
    if line in SECTION_HEADERS:
        return True
    if line in TIER_HEADERS:
        return True
    if line in ("Model", "Models"):
        return True
    if line.endswith("models") and line.istitle():
        return True
    return False


def _parse_tables(lines):
    tables = []
    section = ""
    tier = ""
    unit = ""

    i = 0
    while i < len(lines):
        line = lines[i]
        if line in SECTION_HEADERS:
            section = line
            tier = ""
            i += 1
            continue
        if line in TIER_HEADERS:
            tier = line
            i += 1
            continue
        if line.lower().startswith("prices per "):
            unit = line.replace("Prices per ", "").strip().rstrip(".")
            i += 1
            continue

        if line == "Model":
            columns = []
            j = i + 1
            while j < len(lines):
                header = lines[j]
                if header == "Model":
                    j += 1
                    continue
                if header in COLUMN_HEADERS or re.match(r"^\d+\s*x\s*\d+$", header):
                    columns.append(header)
                    j += 1
                    continue
                break

            if not columns:
                i += 1
                continue

            k = j
            while k < len(lines):
                model_name = lines[k]
                if _is_stop_line(model_name):
                    break
                if model_name in ("Deprecated", "New"):
                    k += 1
                    continue

                if k + len(columns) >= len(lines):
                    break

                values = {}
                for idx, column in enumerate(columns):
                    values[column] = lines[k + 1 + idx]

                model_id = _normalize_model_id(model_name)
                tables.append(
                    PricingTable(
                        section=section,
                        tier=tier,
                        unit=unit,
                        columns=columns,
                        model=model_id,
                        values=values,
                    )
                )
                k += len(columns) + 1

            i = k
            continue

        i += 1

    return tables


def fetch_pricing_tables():
    html = _fetch(PRICING_URL)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    lines = _clean_lines(text)
    return _parse_tables(lines)


def _summarize_entry(entry):
    parts = []
    for column in entry["columns"]:
        value = entry["values"].get(column, "-")
        parts.append(f"{column}: {value}")
    tier = f" {entry['tier']}" if entry["tier"] else ""
    unit = f" ({entry['unit']})" if entry["unit"] else ""
    return f"{entry['section']}{tier}{unit}: " + ", ".join(parts)


def build_pricing_map(tables):
    pricing_map = {}
    for table in tables:
        entry = {
            "section": table.section,
            "tier": table.tier,
            "unit": table.unit,
            "columns": table.columns,
            "values": table.values,
        }
        model_entry = pricing_map.setdefault(table.model, {"tables": []})
        model_entry["tables"].append(entry)

    for model_id, data in pricing_map.items():
        preferred = None
        for entry in data["tables"]:
            if entry["section"] == "Text tokens" and entry["tier"] == "Standard":
                preferred = entry
                break
        if preferred is None and data["tables"]:
            preferred = data["tables"][0]
        if preferred:
            data["summary"] = _summarize_entry(preferred)
    return pricing_map


def update_model_catalog(progress_callback=None):
    def report(message):
        if progress_callback:
            progress_callback(message)

    report("Fetching model list from docs...")
    model_ids = fetch_model_ids()
    report(f"Found {len(model_ids)} models. Fetching pricing tables...")
    pricing_tables = fetch_pricing_tables()
    report("Parsing pricing tables...")
    pricing_map = build_pricing_map(pricing_tables)
    report("Updating local catalog...")

    try:
        with MODEL_CATALOG_PATH.open("r", encoding="utf-8") as f:
            catalog = json.load(f)
    except FileNotFoundError:
        catalog = {"version": 1, "models": []}
    except json.JSONDecodeError:
        catalog = {"version": 1, "models": []}

    models = catalog.get("models")
    if not isinstance(models, list):
        models = []

    model_map = {model.get("id"): model for model in models if isinstance(model, dict)}
    for model_id in model_ids:
        if model_id not in model_map:
            model_map[model_id] = {
                "id": model_id,
                "categories": [],
                "release_order": None,
                "pricing": {},
            }

    for model_id, pricing in pricing_map.items():
        entry = model_map.setdefault(
            model_id,
            {
                "id": model_id,
                "categories": [],
                "release_order": None,
                "pricing": {},
            },
        )
        entry["pricing"] = pricing

    sorted_models = sorted(
        model_map.values(),
        key=lambda item: (
            0
            if isinstance(item.get("release_order"), (int, float))
            else 1,
            item.get("release_order") or 0,
            item.get("id") or "",
        ),
    )

    catalog["models"] = sorted_models
    catalog["pricing_updated_at"] = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
    )

    with MODEL_CATALOG_PATH.open("w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, sort_keys=True)

    report("Pricing update complete.")
    return {
        "models": len(sorted_models),
        "prices": len(pricing_map),
    }


if __name__ == "__main__":
    result = update_model_catalog()
    print(
        f"Updated pricing for {result['prices']} models (catalog size: {result['models']})."
    )
