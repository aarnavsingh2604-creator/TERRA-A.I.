from datetime import datetime, timezone
import math

DIMENSIONS = ("visual", "terrain", "geology", "climate", "water")

# Values shown in the TERRA AI presentation. These are example weights,
# not calibrated scientific truth.
DEFAULT_WEIGHTS = {
    "visual": 28.0,
    "terrain": 25.0,
    "geology": 20.0,
    "climate": 17.0,
    "water": 10.0
}

# Illustrative mission-question presets. Tune and validate with domain experts.
MISSION_PROFILES = {
    "balanced": dict(DEFAULT_WEIGHTS),
    "mars_geology": {
        "visual": 20.0, "terrain": 15.0, "geology": 35.0,
        "climate": 15.0, "water": 15.0
    },
    "mars_surface_operations": {
        "visual": 15.0, "terrain": 35.0, "geology": 20.0,
        "climate": 20.0, "water": 10.0
    },
    "mars_water_history": {
        "visual": 15.0, "terrain": 15.0, "geology": 20.0,
        "climate": 15.0, "water": 35.0
    },
    "lunar_geology": {
        "visual": 20.0, "terrain": 20.0, "geology": 40.0,
        "climate": 10.0, "water": 10.0
    },
    "lunar_surface_operations": {
        "visual": 15.0, "terrain": 35.0, "geology": 25.0,
        "climate": 15.0, "water": 10.0
    }
}

ECOLOGY_STATUSES = {"pass", "review", "reject", "unknown"}

def validate_weights(weights):
    if not isinstance(weights, dict):
        raise ValueError("weights must be an object with visual, terrain, geology, climate, water")
    if set(weights) != set(DIMENSIONS):
        raise ValueError(f"weights must contain exactly: {', '.join(DIMENSIONS)}")
    clean = {}
    for key in DIMENSIONS:
        value = float(weights[key])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"Weight {key} must be a finite non-negative number")
        clean[key] = value
    total = sum(clean.values())
    if total <= 0:
        raise ValueError("At least one weight must be greater than zero")
    # Normalize to 100 so users can enter e.g. 28,25... or fractions.
    return {k: round(v * 100.0 / total, 6) for k, v in clean.items()}

def _dimension_score(dimensions, key):
    item = dimensions.get(key)
    if item is None:
        return None, []
    if isinstance(item, (int, float)):
        score, evidence = float(item), []
    elif isinstance(item, dict):
        raw = item.get("score")
        score = None if raw is None else float(raw)
        evidence = item.get("evidence") or []
    else:
        raise ValueError(f"dimensions.{key} must be a number, object, or null")
    if score is not None and (not math.isfinite(score) or not 0 <= score <= 100):
        raise ValueError(f"dimensions.{key}.score must be between 0 and 100")
    if not isinstance(evidence, list):
        raise ValueError(f"dimensions.{key}.evidence must be a list")
    return score, evidence

def normalize_ecology(ecology):
    status = str(ecology.get("status", "unknown")).lower()
    if status not in ECOLOGY_STATUSES:
        raise ValueError("ecology.status must be pass, review, reject, or unknown")
    protected = ecology.get("protected_area")
    return {
        "status": status,
        "protected_area": protected,
        "notes": ecology.get("notes", ""),
        "evidence": ecology.get("evidence", []),
        "gate_cleared": status == "pass",
        "eligible_for_recommendation": status == "pass"
    }

def score_candidate(candidate, dimensions, weights, ecology=None,
                    target="Mars", mission="balanced"):
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")
    if not isinstance(dimensions, dict):
        raise ValueError("dimensions must be an object")
    target = str(target).title()
    if target not in {"Mars", "Moon"}:
        raise ValueError("target must be Mars or Moon")
    normalized_weights = validate_weights(weights)

    scores, evidence_by_dimension = {}, {}
    for key in DIMENSIONS:
        score, evidence = _dimension_score(dimensions, key)
        scores[key] = score
        evidence_by_dimension[key] = evidence

    available = [k for k in DIMENSIONS if scores[k] is not None and normalized_weights[k] > 0]
    missing = [k for k in DIMENSIONS if scores[k] is None]
    available_weight = sum(normalized_weights[k] for k in available)

    if available_weight > 0:
        # For complete data this is exactly S = sum(w_i * dimension_i)/100.
        # For missing dimensions, renormalize only available weights; missing != 0.
        index = sum(normalized_weights[k] * scores[k] for k in available) / available_weight
        index = round(index, 4)
    else:
        index = None

    coverage = round(len([k for k in DIMENSIONS if scores[k] is not None]) / len(DIMENSIONS) * 100, 1)
    ecology_result = normalize_ecology(ecology or {})
    if ecology_result["status"] == "reject":
        recommendation_status = "excluded_by_ecological_gate"
    elif ecology_result["status"] == "pass" and not missing:
        recommendation_status = "eligible_for_comparison"
    elif ecology_result["status"] == "pass":
        recommendation_status = "provisional_incomplete_scientific_data"
    else:
        recommendation_status = "provisional_ecology_review_required"

    caveats = []
    if missing:
        caveats.append("Missing dimensions: " + ", ".join(missing) +
                       ". Missing data is not treated as a mismatch or a zero score.")
    if coverage < 100:
        caveats.append("The displayed index is partial and renormalized over available dimensions.")
    if ecology_result["status"] != "pass":
        caveats.append("Ecological gate has not passed; this candidate is not cleared for recommendation.")
    caveats.append("Ranking index, not probability. Scores depend on input evidence and scoring protocols.")
    result = {
        "site_id": candidate.get("site_id") or candidate.get("candidate_id") or "UNASSIGNED",
        "site_name": candidate.get("site_name") or candidate.get("name") or "Unnamed candidate",
        "country": candidate.get("country", "Unresolved"),
        "latitude": candidate.get("latitude"),
        "longitude": candidate.get("longitude"),
        "target": target,
        "mission": mission,
        "dimension_scores": scores,
        "weights_percent": normalized_weights,
        "ranking_index": index,
        "ranking_index_label": "partial" if missing else "complete",
        "data_coverage": coverage,
        "available_weight_percent": round(available_weight, 4),
        "missing_dimensions": missing,
        "ecology": ecology_result,
        "recommendation_status": recommendation_status,
        "evidence": evidence_by_dimension,
        "caveats": caveats,
        "formula": "S = wv*V + wt*T + wg*G + wc*C + ww*W; weights normalized to 100%; missing dimensions excluded and remaining weights renormalized.",
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
    return result

def rank_candidates(candidates, weights, target="Mars", mission="balanced"):
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidates must be a non-empty list")
    normalized = validate_weights(weights)
    results = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("Each candidate must be an object")
        result = score_candidate(
            candidate=candidate,
            dimensions=candidate.get("dimensions", {}),
            weights=normalized,
            ecology=candidate.get("ecology", {}),
            target=target,
            mission=mission
        )
        results.append(result)
    # Rank scores for comparison; candidates rejected by the separate ecology
    # gate are kept visible for audit but are not eligible recommendations.
    results.sort(
        key=lambda x: (
            x["recommendation_status"] != "excluded_by_ecological_gate",
            x["ranking_index"] if x["ranking_index"] is not None else -1
        ),
        reverse=True
    )
    for position, result in enumerate(results, 1):
        result["rank"] = position
    return results

def compare_candidates(candidate_a, candidate_b, weights):
    a = score_candidate(
        candidate_a, candidate_a.get("dimensions", {}), weights,
        candidate_a.get("ecology", {}), candidate_a.get("target", "Mars"),
        candidate_a.get("mission", "custom")
    )
    b = score_candidate(
        candidate_b, candidate_b.get("dimensions", {}), weights,
        candidate_b.get("ecology", {}), candidate_b.get("target", "Mars"),
        candidate_b.get("mission", "custom")
    )
    if a["ranking_index"] is None or b["ranking_index"] is None:
        winner = None
        note = "Insufficient dimension data to compare both candidates."
    elif a["ranking_index"] == b["ranking_index"]:
        winner = "tie"
        note = "Equal partial/complete ranking indices; compare coverage and evidence."
    else:
        winner = a["site_id"] if a["ranking_index"] > b["ranking_index"] else b["site_id"]
        note = "Higher index is not a probability and does not override the ecological gate."
    return {
        "candidate_a": a, "candidate_b": b,
        "higher_index_candidate": winner,
        "note": note
    }
