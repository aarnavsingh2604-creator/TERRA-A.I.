"""
TERRA AI - Terrain evidence collector.

Uses existing Copernicus GLO-90 elevation records for centre points
and Open-Meteo API for eight surrounding elevation samples.

Calculates estimated slope, local relief, elevation standard
deviation and a local ruggedness proxy.
"""

import argparse
import csv
import json
import math
import time
from pathlib import Path

from terra_dev2.elevation_collector import (
    MAX_BATCH_SIZE,
    fetch_elevation,
    read_json,
    safe_filename,
    utc_now,
    validate_coordinate,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "data" / "candidates.csv"
ELEVATION_DIR = ROOT / "data" / "evidence" / "elevation"
OUTPUT_DIR = ROOT / "data" / "evidence" / "terrain"

SPACING_M = 90.0

# dx = east/west metres, dy = north/south metres
OFFSETS = [
    ("NW", -SPACING_M, SPACING_M),
    ("N", 0.0, SPACING_M),
    ("NE", SPACING_M, SPACING_M),
    ("W", -SPACING_M, 0.0),
    ("E", SPACING_M, 0.0),
    ("SW", -SPACING_M, -SPACING_M),
    ("S", 0.0, -SPACING_M),
    ("SE", SPACING_M, -SPACING_M),
]


def surrounding_coordinate(lat, lon, dx, dy):
    lat2 = lat + dy / 111320.0
    cos_lat = max(abs(math.cos(math.radians(lat))), 0.01)
    lon2 = lon + dx / (111320.0 * cos_lat)
    return validate_coordinate(lat2, lon2)


def calculate_metrics(samples):
    valid = [
        sample for sample in samples
        if isinstance(sample["elevation_m"], (int, float))
        and math.isfinite(sample["elevation_m"])
    ]

    if len(valid) != 9:
        return None

    elevations = [s["elevation_m"] for s in valid]
    centre = next(s for s in valid if s["sample_id"] == "C")
    centre_elevation = centre["elevation_m"]

    # Least-squares local plane: z = a*x + b*y + c.
    sum_xz = sum(s["dx_m"] * s["elevation_m"] for s in valid)
    sum_yz = sum(s["dy_m"] * s["elevation_m"] for s in valid)
    sum_x2 = sum(s["dx_m"] ** 2 for s in valid)
    sum_y2 = sum(s["dy_m"] ** 2 for s in valid)

    if sum_x2 == 0 or sum_y2 == 0:
        return None

    gradient_x = sum_xz / sum_x2
    gradient_y = sum_yz / sum_y2

    slope_degrees = math.degrees(
        math.atan(math.sqrt(gradient_x ** 2 + gradient_y ** 2))
    )

    neighbours = [
        s["elevation_m"] for s in valid
        if s["sample_id"] != "C"
    ]

    return {
        "slope_degrees": round(slope_degrees, 4),
        "local_relief_m": round(max(elevations) - min(elevations), 3),
        "elevation_stddev_m": round(
            math.sqrt(
                sum((z - sum(elevations) / 9) ** 2 for z in elevations) / 9
            ), 3
        ),
        "ruggedness_proxy_m": round(
            sum(abs(z - centre_elevation) for z in neighbours) / 8, 3
        ),
        "sample_count": 9,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Collect surrounding elevation evidence and derive terrain metrics."
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=0.3)
    args = parser.parse_args()

    if args.limit < 0 or args.delay < 0:
        parser.error("Limit and delay cannot be negative.")

    if not INPUT_FILE.is_file():
        parser.error(f"Candidate file not found: {INPUT_FILE}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cache_dir = OUTPUT_DIR / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    with INPUT_FILE.open("r", encoding="utf-8-sig", newline="") as handle:
        candidates = list(csv.DictReader(handle))

    if args.limit:
        candidates = candidates[:args.limit]

    if not candidates:
        parser.error("No candidates found.")

    site_ids = [c.get("site_id", "") for c in candidates]

    if any(not value for value in site_ids):
        parser.error("Every candidate must have a site_id.")

    if len(site_ids) != len(set(site_ids)):
        parser.error("Duplicate site IDs found.")

    records = {}
    requests = []

    # Reuse the existing centre elevation; request only eight neighbours.
    for candidate in candidates:
        site_id = candidate["site_id"]
        lat, lon = validate_coordinate(
            candidate["latitude"], candidate["longitude"]
        )

        centre_path = (
            ELEVATION_DIR / f"{safe_filename(site_id)}_elevation.json"
        )

        try:
            centre_data = read_json(centre_path)
            centre_value = centre_data["measurement"]["value"]
            centre_source = centre_data["source"]
        except (OSError, ValueError, KeyError, TypeError):
            centre_value = None
            centre_source = None

        records[site_id] = {
            "candidate": candidate,
            "samples": [{
                "sample_id": "C",
                "dx_m": 0.0,
                "dy_m": 0.0,
                "latitude": lat,
                "longitude": lon,
                "elevation_m": centre_value,
                "source": "Existing elevation record",
            }],
            "centre_source": centre_source,
        }

        for label, dx, dy in OFFSETS:
            sample_lat, sample_lon = surrounding_coordinate(
                lat, lon, dx, dy
            )

            requests.append({
                "site_id": site_id,
                "sample_id": label,
                "dx_m": dx,
                "dy_m": dy,
                "latitude": sample_lat,
                "longitude": sample_lon,
            })

    print(
        f"Candidates: {len(candidates)} | "
        f"Neighbour samples: {len(requests)}"
    )

    failed_samples = 0
    api_batches = [
        requests[i:i + MAX_BATCH_SIZE]
        for i in range(0, len(requests), MAX_BATCH_SIZE)
    ]

    for batch_number, batch in enumerate(api_batches, start=1):
        print(
            f"[Batch {batch_number}/{len(api_batches)}] "
            f"Requesting {len(batch)} elevations...",
            flush=True,
        )

        try:
            cached, cache_used = fetch_elevation(
                [
                    (item["latitude"], item["longitude"])
                    for item in batch
                ],
                cache_dir,
            )

            elevations = cached["raw_response"]["elevation"]

            for item, value in zip(batch, elevations):
                records[item["site_id"]]["samples"].append({
                    **item,
                    "elevation_m": value,
                    "source": "Open-Meteo Elevation API",
                    "cache_used": cache_used,
                })

                if value is None:
                    failed_samples += 1

            print("  Batch collected.", flush=True)

        except Exception as exc:
            failed_samples += len(batch)
            print(f"  Batch failed: {exc}", flush=True)

            for item in batch:
                records[item["site_id"]]["samples"].append({
                    **item,
                    "elevation_m": None,
                    "source": "Open-Meteo Elevation API",
                    "error": str(exc),
                })

        if batch_number < len(api_batches) and args.delay:
            time.sleep(args.delay)

    results = []
    complete_count = 0

    for site_id, record in records.items():
        samples = sorted(
            record["samples"],
            key=lambda item: item["sample_id"]
        )

        metrics = calculate_metrics(samples)
        status = "complete" if metrics is not None else "incomplete"

        if status == "complete":
            complete_count += 1

        payload = {
            "schema_version": "1.0",
            "site_id": site_id,
            "site_name": record["candidate"].get("site_name"),
            "status": status,
            "method": {
                "description": (
                    "One centre elevation and eight surrounding "
                    "elevation samples arranged in a 3x3 grid."
                ),
                "nominal_spacing_m": SPACING_M,
                "slope_method": "Least-squares local plane",
                "ruggedness_method": (
                    "Mean absolute elevation difference between "
                    "the eight neighbours and centre."
                ),
            },
            "samples": samples,
            "terrain_metrics": metrics,
            "source": {
                "name": "Open-Meteo Elevation API",
                "dataset": "Copernicus DEM GLO-90",
                "nominal_resolution": "90 m",
                "generated_at_utc": utc_now(),
                "centre_source": record["centre_source"],
            },
            "interpretation_limits": [
                "Metrics are DEM-derived estimates, not field surveys.",
                "Nominal sample spacing does not guarantee independent "
                "90 m terrain pixels or 90 m positional accuracy.",
                "Ruggedness proxy is a project-defined indicator, "
                "not a standardized terrain ruggedness index.",
                "Nine samples cannot identify every local landform "
                "or engineering hazard.",
                "Elevation values near zero do not establish whether "
                "a location is land or ocean.",
                "Terrain metrics do not establish site suitability.",
            ],
        }

        output_file = OUTPUT_DIR / f"{safe_filename(site_id)}_terrain.json"
        write_json(output_file, payload)

        results.append({
            "site_id": site_id,
            "status": status,
            "file": str(output_file),
            "metrics_available": metrics is not None,
        })

    summary = {
        "created_at_utc": utc_now(),
        "source": "Open-Meteo Elevation API",
        "dataset": "Copernicus DEM GLO-90",
        "candidate_count": len(candidates),
        "neighbour_samples_requested": len(requests),
        "api_batch_count": len(api_batches),
        "complete_count": complete_count,
        "incomplete_count": len(candidates) - complete_count,
        "failed_or_null_neighbour_samples": failed_samples,
        "results": results,
    }

    summary_path = OUTPUT_DIR / "terrain_collection_summary.json"
    write_json(summary_path, summary)

    print("\nTerrain collection finished.")
    print(f"Complete: {complete_count}/{len(candidates)}")
    print(f"Incomplete: {len(candidates) - complete_count}")
    print(f"Failed/null neighbour samples: {failed_samples}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
