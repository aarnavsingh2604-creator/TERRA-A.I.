import math

def generate_earth_grid(bbox, spacing_km=100, max_points=5000):
    """Create an approximate Earth lat/lon screening grid.

    This is a discovery grid, not an equal-area projection or a site-safety model.
    Dateline-crossing bounding boxes are not supported in this MVP.
    """
    required = {"west", "south", "east", "north"}
    if not isinstance(bbox, dict) or not required.issubset(bbox):
        raise ValueError("bbox must contain west, south, east, north")
    west, east = float(bbox["west"]), float(bbox["east"])
    south, north = float(bbox["south"]), float(bbox["north"])
    if not (-180 <= west < east <= 180):
        raise ValueError("Require -180 <= west < east <= 180; split dateline boxes")
    if not (-90 <= south < north <= 90):
        raise ValueError("Require -90 <= south < north <= 90")
    spacing_km = float(spacing_km)
    if not 1 <= spacing_km <= 2000:
        raise ValueError("spacing_km must be between 1 and 2000")
    if not 1 <= int(max_points) <= 20000:
        raise ValueError("max_points must be between 1 and 20000")

    earth_radius_km = 6371.0088
    lat_step = math.degrees(spacing_km / earth_radius_km)
    points, row, lat = [], 0, south
    while lat <= north + 1e-9:
        cos_lat = max(0.05, abs(math.cos(math.radians(lat))))
        lon_step = min(360.0, lat_step / cos_lat)
        lon = west + (lon_step / 2 if row % 2 else 0)
        while lon <= east + 1e-9:
            points.append({
                "site_id": f"TA-GRID-{len(points)+1:05d}",
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "grid_spacing_km": spacing_km,
                "screening_status": "unassessed"
            })
            if len(points) > int(max_points):
                raise ValueError("Grid too large; increase spacing_km or reduce bbox")
            lon += lon_step
        lat += lat_step
        row += 1
    return points
