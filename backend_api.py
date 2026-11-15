from pathlib import Path
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests

from terra_dev1.earth_spatial import generate_earth_grid
from terra_dev1.frontend_adapter import write_frontend_candidates
from terra_dev1.clip_engine import score_image_against_prompts, compare_images
from terra_dev1.config import DATA_DIR

app = Flask(__name__)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
PROJECT_ROOT = Path(__file__).resolve().parent
CANDIDATE_CSV = PROJECT_ROOT / "data" / "candidates.csv"
LATEST_CANDIDATES = []

TARGET_PROMPTS = {
    "Mars": [
        "Earth landscape with a Mars-like dry rocky desert, sparse vegetation and exposed geology",
        "Earth landscape with volcanic basalt, dark rock and rugged terrain resembling Mars",
        "Earth landscape with a cold polar desert and permafrost resembling Mars",
        "Earth landscape with dunes and wind-shaped sediment resembling Mars",
        "Earth landscape with a canyon, cliffs and exposed sedimentary layers resembling Mars"
    ],
    "Moon": [
        "Earth landscape with bright barren rocky highlands and impact-like circular depressions",
        "Earth landscape with volcanic basalt plains resembling lunar maria",
        "Earth landscape with an extremely dry, dusty, airless-looking rocky desert",
        "Earth landscape with rugged cratered terrain and exposed bedrock",
        "Earth landscape with polar cold-region terrain and ice-related features"
    ]
}

@app.get("/")
def home():
    return jsonify({
        "project": "TERRA AI",
        "service": "Backend Developer 1",
        "status": "online",
        "frontend": "Existing Streamlit app.py is separate; do not replace it.",
        "candidate_csv": str(CANDIDATE_CSV),
        "workflow": ["Earth spatial screening", "imagery discovery",
                     "CLIP semantic matching", "image comparison",
                     "candidate generation"]
    })

@app.get("/api/health")
def health():
    return jsonify({"status": "online"})

PLANETARY_REFERENCE_POINTS = {
    "Mars": [
        {"id": "MARS-001", "name": "Jezero Crater", "latitude": 18.38, "longitude": 77.58, "status": "REFERENCE LOCATION"},
        {"id": "MARS-002", "name": "Gale Crater", "latitude": -5.40, "longitude": 137.80, "status": "REFERENCE LOCATION"},
        {"id": "MARS-003", "name": "Olympus Mons", "latitude": 18.65, "longitude": -133.80, "status": "REFERENCE LOCATION"},
        {"id": "MARS-004", "name": "Valles Marineris", "latitude": -13.90, "longitude": -59.20, "status": "REFERENCE LOCATION"},
        {"id": "MARS-005", "name": "Hellas Planitia", "latitude": -42.40, "longitude": 70.50, "status": "REFERENCE LOCATION"},
        {"id": "MARS-006", "name": "Elysium Planitia", "latitude": 4.50, "longitude": 135.90, "status": "REFERENCE LOCATION"},
        {"id": "MARS-007", "name": "Arcadia Planitia", "latitude": 46.00, "longitude": 180.00, "status": "REFERENCE LOCATION"}
    ],
    "Moon": [
        {"id": "MOON-001", "name": "Mare Tranquillitatis", "latitude": 8.50, "longitude": 31.40, "status": "REFERENCE LOCATION"},
        {"id": "MOON-002", "name": "Oceanus Procellarum", "latitude": 18.40, "longitude": -57.40, "status": "REFERENCE LOCATION"},
        {"id": "MOON-003", "name": "Tycho Crater", "latitude": -43.30, "longitude": -11.20, "status": "REFERENCE LOCATION"},
        {"id": "MOON-004", "name": "Copernicus Crater", "latitude": 9.70, "longitude": -20.10, "status": "REFERENCE LOCATION"},
        {"id": "MOON-005", "name": "Mare Imbrium", "latitude": 32.80, "longitude": -15.60, "status": "REFERENCE LOCATION"},
        {"id": "MOON-006", "name": "South Pole-Aitken Basin", "latitude": -53.00, "longitude": 169.00, "status": "REFERENCE LOCATION"},
        {"id": "MOON-007", "name": "Aristarchus Plateau", "latitude": 23.70, "longitude": -47.40, "status": "REFERENCE LOCATION"}
    ]
}

@app.post("/api/screen")
def screen():
    data = request.get_json(silent=True) or {}
    target = data.get("target", "Mars")

    if target not in PLANETARY_REFERENCE_POINTS:
        return jsonify({"error": "Unsupported planetary target"}), 400

    points = PLANETARY_REFERENCE_POINTS[target]

    return jsonify({
        "planetary_target": target,
        "screened_reference_points": len(points),
        "points": points
    })


@app.get("/api/planetary/measurements")
def planetary_measurements():
    target = request.args.get("target", "Mars")
    if target not in ("Mars", "Moon"):
        return jsonify({"error": "target must be Mars or Moon"}), 400

    measurement_file = PROJECT_ROOT / "data" / "planetary_scientific_measurements.json"
    if not measurement_file.exists():
        return jsonify({"error": "Planetary measurements file not found"}), 404

    try:
        payload = __import__("json").loads(
            measurement_file.read_text(encoding="utf-8")
        )
        records = [
            item for item in payload.get("measurements", [])
            if item.get("planet") == target
        ]
        return jsonify({
            "planetary_target": target,
            "count": len(records),
            "dataset": payload.get("dataset"),
            "measurements": records
        })
    except (ValueError, OSError) as exc:
        return jsonify({"error": "Could not read measurements", "details": str(exc)}), 500

@app.get("/api/imagery/search")
def imagery_search():
    """Search NASA Images for Earth analog imagery.

    NASA Images is a discovery endpoint; search hits are not guaranteed
    to be georeferenced/calibrated remote-sensing products.
    """
    target = request.args.get("target", "Mars")
    region_query = request.args.get("q", "")
    if target not in TARGET_PROMPTS:
        return jsonify({"error": "target must be Mars or Moon"}), 400
    if not region_query or len(region_query) > 120:
        return jsonify({"error": "Provide q with a region or feature query"}), 400
    query = region_query.strip()
    try:
        r = requests.get("https://images-api.nasa.gov/search",
                         params={"q": query, "media_type": "image",
                                 "page_size": min(int(request.args.get("page_size", 10)), 100)},
                         timeout=30)
        r.raise_for_status()
        collection = r.json().get("collection", {})
        items = []
        for item in collection.get("items", []):
            meta = (item.get("data") or [{}])[0]
            preview = next((x.get("href") for x in item.get("links", [])
                            if x.get("rel") == "preview"), None)
            items.append({
                "nasa_id": meta.get("nasa_id"),
                "title": meta.get("title"),
                "description": meta.get("description"),
                "date_created": meta.get("date_created"),
                "keywords": meta.get("keywords", []),
                "preview_url": preview,
                "source": "NASA Image and Video Library",
                "warning": "Verify whether this is georeferenced scientific imagery before analysis."
            })
        return jsonify({"query": query, "count": len(items), "items": items})
    except Exception as exc:
        return jsonify({"error": "Imagery search failed", "details": str(exc)}), 502

@app.post("/api/clip/score")
def clip_score():
    try:
        data = request.get_json(silent=True) or {}
        target = data.get("target", "Mars")
        prompts = data.get("prompts") or TARGET_PROMPTS.get(target)
        if target not in TARGET_PROMPTS:
            return jsonify({"error": "target must be Mars or Moon"}), 400
        result = score_image_against_prompts(data.get("image_path", ""), prompts)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": "CLIP inference failed", "details": str(exc)}), 500

@app.post("/api/compare")
def compare():
    try:
        data = request.get_json(silent=True) or {}
        return jsonify(compare_images(data.get("image_a", ""), data.get("image_b", "")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": "Image comparison failed", "details": str(exc)}), 500

@app.post("/api/candidates/generate")
def generate():
    """Generate Earth analog discovery candidates and write frontend CSV.

    Each candidate must include coordinates. A CLIP-derived visual score can be
    provided on a 0-100 display scale. Other scientific dimensions stay null
    until Backend Developer 2 supplies measured evidence.
    """
    global LATEST_CANDIDATES
    try:
        data = request.get_json(silent=True) or {}
        target = data.get("target", "Mars")
        if target not in TARGET_PROMPTS:
            return jsonify({"error": "target must be Mars or Moon"}), 400
        candidates = data.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            return jsonify({"error": "candidates must be a non-empty list"}), 400
        normalized = []
        for i, c in enumerate(candidates, 1):
            lat, lon = float(c["latitude"]), float(c["longitude"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("Candidate coordinates out of range")
            visual = c.get("visual_similarity")
            if visual is not None:
                visual = float(visual)
                if not 0 <= visual <= 100:
                    raise ValueError("visual_similarity must be between 0 and 100")
            normalized.append({
                "site_id": c.get("site_id", f"TA-{i:03d}"),
                "site_name": c.get("site_name", f"Unlabelled Earth candidate {i}"),
                "country": c.get("country", "Unresolved"),
                "latitude": lat, "longitude": lon,
                "visual_similarity": visual,
                "terrain_score": c.get("terrain_score"),
                "geology_score": c.get("geology_score"),
                "climate_score": c.get("climate_score"),
                "water_score": c.get("water_score"),
                "protected_area": c.get("protected_area", ""),
                "ecology_warning": c.get("ecology_warning"),
                "summary": c.get("summary")
            })
        LATEST_CANDIDATES = normalized
        csv_path = write_frontend_candidates(normalized, CANDIDATE_CSV)
        return jsonify({
            "target": target,
            "count": len(normalized),
            "csv_written": csv_path,
            "frontend_contract": "data/candidates.csv",
            "notice": "Discovery candidates only. Missing scientific scores are left blank; do not interpret them as zero or as evidence of unsuitability."
        })
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify({"error": str(exc)}), 400

@app.get("/api/candidates/export.csv")
def export_csv():
    if not CANDIDATE_CSV.exists():
        return jsonify({"error": "No candidate CSV generated yet"}), 404
    return Response(CANDIDATE_CSV.read_text(encoding="utf-8"),
                    mimetype="text/csv",
                    headers={"Content-Disposition":
                             "attachment; filename=terra_ai_candidates.csv"})

@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "Request too large"}), 413

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
