import json
import re
from pathlib import Path
from urllib.parse import urlparse
import requests
from .config import NASA_API_KEY, IMAGE_DIR, METADATA_DIR

NASA_SEARCH = "https://images-api.nasa.gov/search"
NASA_ASSET = "https://images-api.nasa.gov/asset/{}"
TIMEOUT = 30
ALLOWED_HOSTS = {"images-assets.nasa.gov"}

def search_nasa_images(planet: str, query: str, page_size: int = 10,
                       page: int = 1) -> dict:
    planet = planet.lower().strip()
    if planet not in {"mars", "moon"}:
        raise ValueError("planet must be mars or moon")
    if not query or len(query) > 150:
        raise ValueError("query is required and must be at most 150 characters")
    page_size = max(1, min(int(page_size), 100))
    params = {
        "q": f"{planet} {query}",
        "media_type": "image",
        "page_size": page_size,
        "page": max(1, int(page))
    }
    response = requests.get(NASA_SEARCH, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    items = []
    for item in payload.get("collection", {}).get("items", []):
        data = (item.get("data") or [{}])[0]
        links = item.get("links") or []
        preview = next((x.get("href") for x in links
                        if x.get("rel") == "preview" and x.get("href")), None)
        items.append({
            "nasa_id": data.get("nasa_id"),
            "title": data.get("title"),
            "description": data.get("description"),
            "date_created": data.get("date_created"),
            "center": data.get("center"),
            "keywords": data.get("keywords", []),
            "media_type": data.get("media_type"),
            "preview_url": preview,
            "asset_manifest": NASA_ASSET.format(data.get("nasa_id"))
                if data.get("nasa_id") else None,
            "source": "NASA Image and Video Library"
        })
    return {"query": params["q"], "count": len(items), "items": items}

def download_nasa_image(nasa_id: str) -> dict:
    if not nasa_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", nasa_id):
        raise ValueError("Invalid NASA ID")
    response = requests.get(NASA_ASSET.format(nasa_id), timeout=TIMEOUT)
    response.raise_for_status()
    manifest = response.json()
    assets = manifest.get("collection", {}).get("items", [])
    # Prefer a full-size image asset, avoid thumbnails where possible.
    candidates = [x.get("href") for x in assets if x.get("href")]
    image_url = next((u for u in candidates
                      if urlparse(u).hostname in ALLOWED_HOSTS
                      and u.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff"))), None)
    if not image_url:
        raise ValueError("No downloadable image file found in this NASA asset manifest")
    image_response = requests.get(image_url, timeout=60, stream=True)
    image_response.raise_for_status()
    content_type = image_response.headers.get("Content-Type", "").lower()
    suffix = Path(urlparse(image_url).path).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
        suffix = ".jpg" if "jpeg" in content_type else ".png"
    destination = IMAGE_DIR / f"{nasa_id}{suffix}"
    total = 0
    with destination.open("wb") as output:
        for chunk in image_response.iter_content(1024 * 256):
            if chunk:
                total += len(chunk)
                if total > 100 * 1024 * 1024:
                    output.close()
                    destination.unlink(missing_ok=True)
                    raise ValueError("Image exceeds 100 MB download limit")
                output.write(chunk)
    metadata_path = METADATA_DIR / f"{nasa_id}.json"
    metadata_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "nasa_id": nasa_id,
        "image_path": str(destination),
        "metadata_path": str(metadata_path),
        "source_url": image_url,
        "bytes": total
    }
