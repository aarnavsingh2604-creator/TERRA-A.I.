import os
from pathlib import Path
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import json
from datetime import datetime, timezone

from terra_dev2.scoring import (
    DEFAULT_WEIGHTS, MISSION_PROFILES, validate_weights,
    score_candidate, rank_candidates, compare_candidates
)
from terra_dev2.storage import write_frontend_csv, write_audit_json

app = Flask(__name__)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_CSV = DATA_DIR / "scientific_candidates.csv"
AUDIT_JSON = DATA_DIR / "scientific_analysis.json"
LATEST = []

@app.get("/")
def home():
    return jsonify({
        "project": "TERRA AI",
        "module": "Backend Developer 2 â€” Scientific Analysis",
        "status": "online",
        "port": 5002,
        "responsibilities": [
            "terrain analysis", "geological analysis", "climate analysis",
            "water indicators", "ecological safeguards", "explainable scoring and ranking"
        ],
        "frontend_contract": "data/candidates.csv",
        "note": "This API scores supplied, evidence-backed dimension assessments. It does not invent or automatically retrieve scientific measurements."
    })

@app.get("/api/health")
def health():
    return jsonify({"status": "online"})

@app.get("/api/profiles")
def profiles():
    return jsonify({
        "default_weights": DEFAULT_WEIGHTS,
        "mission_profiles": MISSION_PROFILES,
        "note": "Profiles are illustrative starting points. Validate/calibrate them with domain experts before operational use."
    })

@app.post("/api/analyze")
def analyze():
    """Score one candidate using evidence-backed dimension scores.

    JSON:
    {
      "candidate": {"site_id":"TA-101", "site_name":"...", "latitude":-23.5,
                    "longitude":-68.2, "country":"Chile"},
      "target": "Mars",
      "mission": "balanced",
      "weights": {"visual":28,"terrain":25,"geology":20,"climate":17,"water":10},
      "dimensions": {
        "visual": {"score":81.5,"evidence":[{"source":"...", "detail":"..."}]},
        "terrain": {"score":75,"evidence":[...]},
        "geology": {"score":80,"evidence":[...]},
        "climate": {"score":68,"evidence":[...]},
        "water": {"score":40,"evidence":[...]}
      },
      "ecology": {"status":"review","protected_area":false,"notes":"..."}
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        candidate = data.get("candidate") or {}
        dimensions = data.get("dimensions") or {}
        weights = data.get("weights")
        if weights is None:
            mission = data.get("mission", "balanced")
            weights = MISSION_PROFILES.get(mission)
            if weights is None:
                return jsonify({"error": f"Unknown mission profile: {mission}",
                                "available_profiles": list(MISSION_PROFILES)}), 400
        result = score_candidate(
            candidate=candidate,
            dimensions=dimensions,
            weights=weights,
            ecology=data.get("ecology") or {},
            target=data.get("target", "Mars"),
            mission=data.get("mission", "custom" if data.get("weights") else "balanced")
        )
        return jsonify(result)
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify({"error": str(exc)}), 400

@app.post("/api/rank")
def rank():
    """Rank multiple candidates with one shared set of weights."""
    try:
        data = request.get_json(silent=True) or {}
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return jsonify({"error": "candidates must be a non-empty list"}), 400
        mission = data.get("mission", "balanced")
        weights = data.get("weights")
        if weights is None:
            weights = MISSION_PROFILES.get(mission)
            if weights is None:
                return jsonify({"error": f"Unknown mission profile: {mission}"}), 400
        results = rank_candidates(
            candidates, weights,
            target=data.get("target", "Mars"),
            mission=mission
        )
        global LATEST
        LATEST = results
        csv_path = write_frontend_csv(results, OUTPUT_CSV)
        write_audit_json(results, AUDIT_JSON)
        return jsonify({
            "target": data.get("target", "Mars"),
            "mission": mission,
            "weights": validate_weights(weights),
            "count": len(results),
            "candidates": results,
            "csv_written": str(csv_path),
            "audit_json": str(AUDIT_JSON),
            "ranking_note": "Index, not probability. Ecology gate is separate. Partial scores are renormalized over available dimensions."
        })
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify({"error": str(exc)}), 400

@app.post("/api/compare")
def compare():
    try:
        data = request.get_json(silent=True) or {}
        a, b = data.get("candidate_a"), data.get("candidate_b")
        if not isinstance(a, dict) or not isinstance(b, dict):
            return jsonify({"error": "candidate_a and candidate_b objects are required"}), 400
        weights = data.get("weights") or MISSION_PROFILES.get(data.get("mission", "balanced"))
        if weights is None:
            return jsonify({"error": "Unknown mission profile"}), 400
        return jsonify(compare_candidates(a, b, weights))
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify({"error": str(exc)}), 400

@app.get("/api/export.csv")
def export_csv():
    if not OUTPUT_CSV.exists():
        return jsonify({"error": "No ranked candidates available yet; POST to /api/rank first"}), 404
    return Response(
        OUTPUT_CSV.read_text(encoding="utf-8"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=terra_scientific_candidates.csv"}
    )

@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "Request too large"}), 413

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5002)), debug=False)

