import math
from typing import Dict, List

PLANET_RADII_KM = {"mars": 3389.5, "moon": 1737.4}

def _validate_bbox(bbox: Dict[str, float]) -> None:
    required = {"west", "south", "east", "north"}
    if not isinstance(bbox, dict) or not required.issubset(bbox):
        raise ValueError("bbox must contain west, south, east, north")
    west, east = float(bbox["west"]), float(bbox["east"])
    south, north = float(bbox["south"]), float(bbox["north"])
    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise ValueError("longitude must be between -180 and 180 degrees")
    if not (-90 <= south < north <= 90):
        raise ValueError("latitude must satisfy -90 <= south < north <= 90")
    if west == east:
        raise ValueError("bbox west and east cannot be equal")
    # Dateline-crossing boxes are intentionally rejected in this MVP.
    if west > east:
        raise ValueError("Dateline-crossing bbox is not supported; split it into two boxes")

def generate_screen_grid(planet: str, bbox: Dict[str, float],
                         spacing_km: float = 100.0,
                         max_points: int = 5000) -> List[dict]:
    planet = planet.lower()
    if planet not in PLANET_RADII_KM:
        raise ValueError("planet must be 'mars' or 'moon'")
    _validate_bbox(bbox)
    if not (1 <= float(spacing_km) <= 2000):
        raise ValueError("spacing_km must be between 1 and 2000")
    if not (1 <= int(max_points) <= 20000):
        raise ValueError("max_points must be between 1 and 20000")

    radius = PLANET_RADII_KM[planet]
    lat_step = math.degrees(float(spacing_km) / radius)
    south, north = float(bbox["south"]), float(bbox["north"])
    west, east = float(bbox["west"]), float(bbox["east"])
    points = []
    lat = south
    row = 0
    while lat <= north + 1e-9:
        cos_lat = max(0.05, abs(math.cos(math.radians(lat))))
        lon_step = min(360.0, lat_step / cos_lat)
        lon = west + (lon_step / 2 if row % 2 else 0)
        while lon <= east + 1e-9:
            points.append({
                "candidate_id": f"{planet.upper()}_GRID_{len(points)+1:05d}",
                "planet": planet,
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "grid_spacing_km": float(spacing_km),
                "screening_status": "unassessed"
            })
            if len(points) > max_points:
                raise ValueError(
                    f"Grid exceeds max_points={max_points}; increase spacing_km or reduce bbox"
                )
            lon += lon_step
        lat += lat_step
        row += 1
    return points
