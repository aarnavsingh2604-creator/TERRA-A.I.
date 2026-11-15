import csv
from pathlib import Path

FRONTEND_COLUMNS = [
    "site_id", "site_name", "country", "latitude", "longitude",
    "visual_similarity", "terrain_score", "geology_score",
    "climate_score", "water_score", "data_coverage",
    "protected_area", "ecology_warning", "summary"
]

def write_frontend_candidates(candidates, output_path):
    """Write the exact schema consumed by the existing Streamlit app.

    Unmeasured scientific scores remain blank. data_coverage is the proportion
    of the five score dimensions with actual values; it is NOT a suitability score.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FRONTEND_COLUMNS)
        writer.writeheader()
        for i, c in enumerate(candidates, 1):
            score_fields = ["visual_similarity", "terrain_score",
                            "geology_score", "climate_score", "water_score"]
            available = sum(c.get(k) is not None for k in score_fields)
            row = {
                "site_id": c.get("site_id") or f"TA-{i:03d}",
                "site_name": c.get("site_name") or f"Unlabelled Earth grid candidate {i}",
                "country": c.get("country") or "Unresolved",
                "latitude": c.get("latitude"),
                "longitude": c.get("longitude"),
                "visual_similarity": c.get("visual_similarity"),
                "terrain_score": c.get("terrain_score"),
                "geology_score": c.get("geology_score"),
                "climate_score": c.get("climate_score"),
                "water_score": c.get("water_score"),
                "data_coverage": round(available / 5 * 100, 1),
                "protected_area": c.get("protected_area", ""),
                "ecology_warning": c.get(
                    "ecology_warning",
                    "Environmental and protected-area screening not yet assessed"
                ),
                "summary": c.get(
                    "summary",
                    "Earth analog candidate. Scientific evaluation is pending."
                )
            }
            writer.writerow(row)
    return str(path)
