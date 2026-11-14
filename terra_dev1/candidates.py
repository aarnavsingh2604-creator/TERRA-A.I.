import csv
import io
import json
from datetime import datetime, timezone

def generate_candidates(planet, screen_points, visual_matches=None,
                        region_name="Unspecified region", top_k=50):
    planet = planet.lower()
    if planet not in {"mars", "moon"}:
        raise ValueError("planet must be mars or moon")
    if not isinstance(screen_points, list) or not screen_points:
        raise ValueError("screen_points must be a non-empty list")
    if not 1 <= int(top_k) <= 500:
        raise ValueError("top_k must be between 1 and 500")
    visual_matches = visual_matches or []
    index = {}
    for match in visual_matches:
        try:
            key = (round(float(match["latitude"]), 5),
                   round(float(match["longitude"]), 5))
            score = float(match["similarity"])
            if not -1 <= score <= 1:
                continue
            index[key] = match
        except (KeyError, TypeError, ValueError):
            continue

    candidates = []
    for point in screen_points:
        lat, lon = float(point["latitude"]), float(point["longitude"])
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("Candidate coordinates out of range")
        match = index.get((round(lat, 5), round(lon, 5)))
        candidates.append({
            "candidate_id": point.get("candidate_id") or f"{planet.upper()}_{len(candidates)+1:05d}",
            "planet": planet,
            "region_name": region_name,
            "latitude": lat,
            "longitude": lon,
            "visual_similarity": match.get("similarity") if match else None,
            "image_path": match.get("image_path") if match else None,
            "image_source": match.get("source") if match else None,
            "discovery_status": "visual_match_found" if match else "awaiting_imagery",
            "scientific_suitability": "not_assessed",
            "generated_at": datetime.now(timezone.utc).isoformat()
        })
    candidates.sort(
        key=lambda c: c["visual_similarity"] if c["visual_similarity"] is not None else -2,
        reverse=True
    )
    return candidates[:int(top_k)]

def candidates_to_csv(candidates):
    if not candidates:
        return ""
    output = io.StringIO()
    fields = list(candidates[0].keys())
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(candidates)
    return output.getvalue()
