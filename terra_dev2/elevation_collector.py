"""
TERRA AI - Open-Meteo elevation evidence collector.

Collects elevation measurements from the Open-Meteo Elevation API,
using the Copernicus DEM GLO-90 dataset.

Requests are batched in groups of at most 100 coordinates.
This module preserves measurements and provenance; it does not
calculate terrain or suitability scores.
"""

import argparse
import csv
import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "candidates.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "evidence" / "elevation"

BASE_URL = "https://api.open-meteo.com/v1/elevation"
MAX_BATCH_SIZE = 100


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def safe_filename(value):
    cleaned = "".join(
        char if char.isalnum() or char in "-_." else "_"
        for char in str(value)
    )
    return cleaned[:120] or "unknown_candidate"


def validate_coordinate(latitude, longitude):
    lat = float(latitude)
    lon = float(longitude)

    if not math.isfinite(lat) or not -90 <= lat <= 90:
        raise ValueError(f"Invalid latitude: {latitude}")

    if not math.isfinite(lon) or not -180 <= lon <= 180:
        raise ValueError(f"Invalid longitude: {longitude}")

    return lat, lon


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")

    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    temporary.replace(path)


def read_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def cache_key(candidates):
    parts = [
        f"{lat:.6f},{lon:.6f}"
        for lat, lon in candidates
    ]
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fetch_elevation(batch, cache_dir):
    key = cache_key(batch)
    cache_path = cache_dir / f"open_meteo_elevation_{key}.json"

    if cache_path.is_file():
        cached = read_json(cache_path)
        return cached, True

    latitudes = ",".join(f"{lat:.6f}" for lat, _ in batch)
    longitudes = ",".join(f"{lon:.6f}" for _, lon in batch)

    query = {
        "latitude": latitudes,
        "longitude": longitudes,
    }

    url = f"{BASE_URL}?{urlencode(query)}"
    request = Request(
        url,
        headers={"User-Agent": "TERRA-AI-ElevationCollector/1.0"},
    )

    last_error = None

    for attempt in range(3):
        try:
            with urlopen(request, timeout=45) as response:
                payload = json.loads(response.read().decode("utf-8"))

            if not isinstance(payload, dict):
                raise ValueError(
                    "Open-Meteo returned an unexpected response."
                )

            elevations = payload.get("elevation")

            if not isinstance(elevations, list):
                raise ValueError(
                    "Open-Meteo response is missing its elevation list."
                )

            if len(elevations) != len(batch):
                raise ValueError(
                    "Elevation response count does not match request: "
                    f"requested {len(batch)}, received {len(elevations)}."
                )

            for index, value in enumerate(elevations):
                if value is not None:
                    numeric = float(value)
                    if not math.isfinite(numeric):
                        raise ValueError(
                            f"Invalid elevation at response index {index}."
                        )

            cache_record = {
                "retrieved_at_utc": utc_now(),
                "request_url": url,
                "raw_response": payload,
            }

            write_json(cache_path, cache_record)
            return cache_record, False

        except (
            HTTPError, URLError, TimeoutError, OSError,
            ValueError, json.JSONDecodeError
        ) as exc:
            last_error = str(exc)
            if attempt < 2:
                time.sleep(2 ** attempt)

    raise RuntimeError(
        f"Open-Meteo request failed after 3 attempts: {last_error}"
    )


def collect_batch(candidates, output_dir, batch_number):
    coordinates = [
        validate_coordinate(
            candidate.get("latitude"),
            candidate.get("longitude"),
        )
        for candidate in candidates
    ]

    cache_dir = output_dir / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    cached_record, cache_used = fetch_elevation(
        coordinates, cache_dir
    )

    raw = cached_record["raw_response"]
    elevations = raw["elevation"]
    results = []

    for index, candidate in enumerate(candidates):
        site_id = candidate.get("site_id") or "unknown_candidate"
        latitude, longitude = coordinates[index]
        elevation = elevations[index]

        result = {
            "schema_version": "1.0",
            "site_id": site_id,
            "site_name": candidate.get("site_name"),
            "requested_location": {
                "latitude": latitude,
                "longitude": longitude,
            },
            "measurement": {
                "variable": "elevation",
                "value": elevation,
                "units": "m",
                "dataset": "Copernicus DEM GLO-90",
                "note": (
                    "Elevation is preserved in metres as returned by "
                    "Open-Meteo. A null value means no elevation value "
                    "was returned for this coordinate."
                ),
            },
            "source": {
                "name": "Open-Meteo Elevation API",
                "api": BASE_URL,
                "dataset": "Copernicus DEM GLO-90",
                "nominal_resolution": "90 m",
                "request_url": cached_record["request_url"],
                "retrieved_at_utc": cached_record["retrieved_at_utc"],
                "cache_used": cache_used,
                "batch_number": batch_number,
                "batch_size": len(candidates),
                "response_index": index,
                "generationtime_ms": raw.get("generationtime_ms"),
            },
            "interpretation_limits": [
                "Elevation is one terrain attribute, not a terrain score.",
                "Elevation alone does not establish slope, roughness, "
                "surface hazards, or site suitability.",
                "DEM-derived elevation is not a field survey measurement.",
                "The nominal 90 m dataset resolution does not imply "
                "90 m positional or vertical accuracy at every location.",
            ],
        }

        filename = safe_filename(site_id) + "_elevation.json"
        output_path = output_dir / filename
        write_json(output_path, result)

        results.append({
            "site_id": site_id,
            "status": "collected",
            "file": str(output_path),
            "elevation_m": elevation,
            "cache_used": cache_used,
            "batch_number": batch_number,
        })

    return results


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Collect raw Open-Meteo elevation evidence for TERRA AI."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum candidates to process; 0 means all candidates.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Pause in seconds between API batches.",
    )
    args = parser.parse_args()

    if args.limit < 0:
        parser.error("--limit cannot be negative.")

    if args.delay < 0:
        parser.error("--delay cannot be negative.")

    if not args.input.is_file():
        parser.error(f"Candidate CSV not found: {args.input}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    with args.input.open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        candidates = list(csv.DictReader(handle))

    if not candidates:
        parser.error("Candidate CSV contains no candidate rows.")

    if args.limit > 0:
        candidates = candidates[:args.limit]

    site_ids = [
        str(candidate.get("site_id") or "")
        for candidate in candidates
    ]

    if any(not site_id for site_id in site_ids):
        parser.error("Every candidate must have a site_id.")

    if len(site_ids) != len(set(site_ids)):
        parser.error("Duplicate site_id values found in candidate CSV.")

    # Validate all coordinates before making any API requests.
    try:
        for candidate in candidates:
            validate_coordinate(
                candidate.get("latitude"),
                candidate.get("longitude"),
            )
    except (TypeError, ValueError) as exc:
        parser.error(f"Candidate coordinate validation failed: {exc}")

    batches = [
        candidates[index:index + MAX_BATCH_SIZE]
        for index in range(0, len(candidates), MAX_BATCH_SIZE)
    ]

    results = []
    total = len(candidates)

    for batch_number, batch in enumerate(batches, start=1):
        first_id = batch[0]["site_id"]
        last_id = batch[-1]["site_id"]

        print(
            f"[Batch {batch_number}/{len(batches)}] "
            f"Collecting {len(batch)} coordinates "
            f"({first_id} to {last_id})...",
            flush=True,
        )

        try:
            batch_results = collect_batch(
                batch, args.output_dir, batch_number
            )
            results.extend(batch_results)

            cache_status = (
                "True" if batch_results[0]["cache_used"] else "False"
            )
            print(
                f"  Status: collected {len(batch_results)}"
                f" | Cache: {cache_status}",
                flush=True,
            )

        except Exception as exc:
            error = str(exc)
            for candidate in batch:
                results.append({
                    "site_id": candidate["site_id"],
                    "status": "failed",
                    "error": error,
                    "batch_number": batch_number,
                })

            print(f"  Status: failed | Error: {error}", flush=True)

        if batch_number < len(batches) and args.delay > 0:
            time.sleep(args.delay)

    summary = {
        "created_at_utc": utc_now(),
        "source": "Open-Meteo Elevation API",
        "dataset": "Copernicus DEM GLO-90",
        "candidate_count": total,
        "batch_count": len(batches),
        "maximum_batch_size": MAX_BATCH_SIZE,
        "collected_count": sum(
            item["status"] == "collected" for item in results
        ),
        "failed_count": sum(
            item["status"] == "failed" for item in results
        ),
        "results": results,
    }

    summary_path = args.output_dir / "elevation_collection_summary.json"
    write_json(summary_path, summary)

    print("\nElevation collection finished.")
    print(f"Collected: {summary['collected_count']} / {total}")
    print(f"Failed: {summary['failed_count']}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
