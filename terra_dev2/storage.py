import csv
import json
from pathlib import Path

# Preserve the columns expected by the current TERRA Streamlit frontend.
# Extra columns are appended for the scientific ranking and audit trail.
FRONTEND_COLUMNS = [
    "site_id", "site_name", "country", "latitude", "longitude",
    "visual_similarity", "terrain_score", "geology_score",
    "climate_score", "water_score", "data_coverage",
    "protected_area", "ecology_warning", "summary",
    "analog_score", "ranking_index", "ranking_status",
    "ecology_gate", "missing_dimensions", "target", "mission"
]

def write_frontend_csv(results, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FRONTEND_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for result in results:
            dims = result["dimension_scores"]
            ecology = result["ecology"]
            warnings = ecology.get("notes") or ""
            if ecology["status"] != "pass":
                warnings = (warnings + " " if warnings else "") + "Ecological gate not passed."
            summary = (
                f"{result['ranking_index_label'].title()} TERRA ranking index: "
                f"{result['ranking_index'] if result['ranking_index'] is not None else 'not available'}. "
                f"Coverage: {result['data_coverage']}%. "
                f"Status: {result['recommendation_status']}."
            )
            writer.writerow({
                "site_id": result["site_id"],
                "site_name": result["site_name"],
                "country": result["country"],
                "latitude": result["latitude"],
                "longitude": result["longitude"],
                "visual_similarity": dims["visual"],
                "terrain_score": dims["terrain"],
                "geology_score": dims["geology"],
                "climate_score": dims["climate"],
                "water_score": dims["water"],
                "data_coverage": result["data_coverage"],
                "protected_area": ecology.get("protected_area"),
                "ecology_warning": warnings,
                "summary": summary,
                "analog_score": result["ranking_index"],
                "ranking_index": result["ranking_index"],
                "ranking_status": result["recommendation_status"],
                "ecology_gate": ecology["status"],
                "missing_dimensions": ";".join(result["missing_dimensions"]),
                "target": result["target"],
                "mission": result["mission"]
            })
    return str(path)

def write_audit_json(results, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)
