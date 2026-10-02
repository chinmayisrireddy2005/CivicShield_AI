from typing import Any, Dict

import requests

OSRM_URL = "http://router.project-osrm.org/route/v1/driving/"


def get_route_info(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> Dict[str, Any]:
    try:
        request_url = (
            f"{OSRM_URL}{start_lon},{start_lat};{end_lon},{end_lat}"
            "?overview=false&geometries=geojson"
        )
        response = requests.get(request_url, timeout=20)
        response.raise_for_status()
        payload = response.json()
        routes = payload.get("routes") or []
        if not routes:
            return {"ok": False, "message": "Road route unavailable"}
        route = routes[0]
        distance_km = round(route.get("distance", 0) / 1000, 2)
        duration_min = max(1, round(route.get("duration", 0) / 60))
        return {"ok": True, "distance_km": distance_km, "duration_min": duration_min}
    except Exception:
        return {"ok": False, "message": "Road route unavailable"}
