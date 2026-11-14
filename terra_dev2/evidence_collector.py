"""
TERRA AI - Raw environmental evidence collector.

Collects NASA POWER monthly point data and preserves monthly observations,
annual aggregates, units, coordinates, source metadata, and retrieval time.

This module deliberately does not calculate suitability scores.
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
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "evidence"

BASE_URL = (
    "https://power.larc.nasa.gov/api/temporal/monthly/point"
)

PARAMETERS = ("T2M", "PRECTOTCORR", "WS10M")

PARAMETER_DESCRIPTIONS = {
    "T2M": "Temperature at 2 meters",
    "PRECTOTCORR": "Corrected precipitation",
    "WS10M": "Wind speed at 10 meters",
}


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


def cache_key(latitude, longitude, start, end):
    payload = (
        f"{latitude:.6f}|{longitude:.6f}|"
        f"{start}|{end}|{','.join(PARAMETERS)}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")

    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    temporary.replace(path)


def fetch_nasa_power(latitude, longitude, start, end, cache_dir):
    key = cache_key(latitude, longitude, start, end)
    cache_path = cache_dir / f"nasa_power_{key}.json"

    if cache_path.is_file():
        cached = read_json(cache_path)
        return cached, True

    query = {
        "parameters": ",".join(PARAMETERS),
        "community": "AG",
        "longitude": f"{longitude:.6f}",
        "latitude": f"{latitude:.6f}",
        "start": str(start),
        "end": str(end),
        "format": "JSON",
    }

    url = f"{BASE_URL}?{urlencode(query)}"
    request = Request(
        url,
        headers={"User-Agent": "TERRA-AI-EvidenceCollector/1.0"},
    )

    last_error = None

    for attempt in range(3):
        try:
            with urlopen(request, timeout=45) as response:
                payload = json.loads(response.read().decode("utf-8"))

            if not isinstance(payload, dict):
                raise ValueError("NASA POWER returned an unexpected response.")

            if not isinstance(payload.get("properties"), dict):
                raise ValueError(
                    "NASA POWER response is missing its properties section."
                )

            parameters = payload["properties"].get("parameter", {})
            missing = [name for name in PARAMETERS if name not in parameters]

            if missing:
                raise ValueError(
                    f"NASA POWER response is missing parameters: {missing}"
                )

            cache_record = {
                "retrieved_at_utc": utc_now(),
                "request_url": url,
                "raw_response": payload,
            }

            write_json(cache_path, cache_record)
            return cache_record, False

        except (HTTPError, URLError, TimeoutError, OSError,
                ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            if attempt < 2:
                time.sleep(2 ** attempt)

    raise RuntimeError(
        f"NASA POWER request failed after 3 attempts: {last_error}"
    )


def split_time_series(series):
    monthly = {}
    annual = {}
    other = {}

    for key, value in series.items():
        key = str(key)

        if len(key) == 6 and key.isdigit():
            year = int(key[:4])
            period = int(key[4:])

            if 1 <= period <= 12:
                monthly[key] = value
            elif period == 13:
                annual[key] = value
            else:
                other[key] = value
        else:
            other[key] = value

    return monthly, annual, other


def build_measurements(raw_response):
    parameter_values = raw_response["properties"]["parameter"]
    parameter_metadata = raw_response.get("parameters", {})
    fill_value = raw_response.get("header", {}).get("fill_value", -999.0)

    measurements = {}

    for name in PARAMETERS:
        monthly, annual, other = split_time_series(
            parameter_values[name]
        )
        metadata = parameter_metadata.get(name, {})

        measurements[name] = {
            "description": metadata.get(
                "longname", PARAMETER_DESCRIPTIONS[name]
            ),
            "units": metadata.get("units"),
            "monthly": monthly,
            "annual_aggregates": annual,
            "other_periods": other,
            "fill_value": fill_value,
            "note": (
                "Values are preserved as returned by NASA POWER. "
                "Annual YYYY13 entries are kept separate from months. "
                "Fill values must not be treated as observations."
            ),
        }

    return measurements


def collect_candidate(candidate, start, end, output_dir):
    site_id = candidate.get("site_id") or "unknown_candidate"

    latitude, longitude = validate_coordinate(
        candidate.get("latitude"),
        candidate.get("longitude"),
    )

    cache_dir = output_dir / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    cached_record, cache_used = fetch_nasa_power(
        latitude, longitude, start, end, cache_dir
    )

    raw = cached_record["raw_response"]
    geometry = raw.get("geometry", {})
    returned_coordinates = geometry.get("coordinates", [])

    result = {
        "schema_version": "1.0",
        "site_id": site_id,
        "site_name": candidate.get("site_name"),
        "requested_location": {
            "latitude": latitude,
            "longitude": longitude,
        },
        "returned_geometry": geometry,
        "returned_coordinates": returned_coordinates,
        "source": {
            "name": "NASA POWER",
            "api": raw.get("header", {}).get("api"),
            "title": raw.get("header", {}).get("title"),
            "sources": raw.get("header", {}).get("sources"),
            "time_standard": raw.get("header", {}).get("time_standard"),
            "period_start": raw.get("header", {}).get("start"),
            "period_end": raw.get("header", {}).get("end"),
            "request_url": cached_record["request_url"],
            "retrieved_at_utc": cached_record["retrieved_at_utc"],
            "cache_used": cache_used,
        },
        "measurements": build_measurements(raw),
        "raw_response": raw,
        "interpretation_limits": [
            "These are environmental measurements, not suitability scores.",
            "NASA POWER grid data are not point-scale field measurements.",
            "Annual YYYY13 aggregates are not monthly observations.",
            "No geology, water availability, ecology, or terrain suitability "
            "has been established by this collection.",
        ],
    }

    filename = safe_filename(site_id) + "_nasa_power.json"
    output_path = output_dir / filename
    write_json(output_path, result)

    return {
        "site_id": site_id,
        "status": "collected",
        "file": str(output_path),
        "cache_used": cache_used,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Collect raw NASA POWER climate evidence for TERRA AI."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start", type=int, default=2020)
    parser.add_argument("--end", type=int, default=2024)
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
        help="Pause in seconds between candidate requests.",
    )
    args = parser.parse_args()

    if args.start < 1981 or args.end < args.start:
        parser.error("Use a valid period: start >= 1981 and end >= start.")

    if not args.input.is_file():
        parser.error(f"Candidate CSV not found: {args.input}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    with args.input.open("r", encoding="utf-8-sig", newline="") as handle:
        candidates = list(csv.DictReader(handle))

    if not candidates:
        parser.error("Candidate CSV contains no candidate rows.")

    if args.limit > 0:
        candidates = candidates[:args.limit]

    results = []
    total = len(candidates)

    for index, candidate in enumerate(candidates, start=1):
        site_id = candidate.get("site_id", "unknown_candidate")
        print(f"[{index}/{total}] Collecting {site_id}...", flush=True)

        try:
            result = collect_candidate(
                candidate, args.start, args.end, args.output_dir
            )
        except Exception as exc:
            result = {
                "site_id": site_id,
                "status": "failed",
                "error": str(exc),
            }

        results.append(result)
        print(
            f"  Status: {result['status']}"
            + (
                f" | Cache: {result['cache_used']}"
                if result["status"] == "collected"
                else f" | Error: {result['error']}"
            ),
            flush=True,
        )

        if index < total and args.delay > 0:
            time.sleep(args.delay)

    summary = {
        "created_at_utc": utc_now(),
        "source": "NASA POWER",
        "period": {"start": args.start, "end": args.end},
        "candidate_count": total,
        "collected_count": sum(
            item["status"] == "collected" for item in results
        ),
        "failed_count": sum(
            item["status"] == "failed" for item in results
        ),
        "results": results,
    }

    summary_path = args.output_dir / "collection_summary.json"
    write_json(summary_path, summary)

    print("\nCollection finished.")
    print(f"Collected: {summary['collected_count']} / {total}")
    print(f"Failed: {summary['failed_count']}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
