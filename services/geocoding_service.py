from typing import Any, Dict, Optional

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"


def geocode_location(query: str, limit: int = 5) -> Dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "Unable to locate this place. Please try another location."}
    headers = {"User-Agent": "CivicShieldAI/1.0"}
    params = {"q": q, "format": "jsonv2", "limit": max(1, min(int(limit or 5), 5)), "countrycodes": "in"}
    try:
        response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json() or []
        if not data:
            return {"ok": False, "error": "Unable to locate this place. Please try another location."}

        results = []
        for item in data:
            address_info = item.get("address") or {}
            result = {
                "latitude": float(item.get("lat", 0.0)),
                "longitude": float(item.get("lon", 0.0)),
                "address": item.get("display_name", q),
                "state": address_info.get("state", ""),
                "city": address_info.get("city") or address_info.get("town") or address_info.get("village") or "",
                "place": address_info.get("amenity") or address_info.get("suburb") or item.get("display_name", q),
            }
            results.append(result)

        first_result = results[0]
        return {
            "ok": True,
            "latitude": first_result["latitude"],
            "longitude": first_result["longitude"],
            "address": first_result["address"],
            "state": first_result["state"],
            "city": first_result["city"],
            "place": first_result["place"],
            "results": results,
        }
    except Exception:
        return {"ok": False, "error": "Unable to locate this place. Please try another location."}


def reverse_geocode(lat: Optional[float], lon: Optional[float]) -> Dict[str, Any]:
    if lat is None or lon is None:
        return {"ok": False, "error": "Unable to locate this place. Please try another location."}
    headers = {"User-Agent": "CivicShieldAI/1.0"}
    params = {"lat": lat, "lon": lon, "format": "jsonv2"}
    try:
        response = requests.get(NOMINATIM_REVERSE_URL, params=params, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        if not data:
            return {"ok": False, "error": "Unable to locate this place. Please try another location."}
        address = data.get("display_name") or "Current location"
        address_info = data.get("address") or {}
        return {
            "ok": True,
            "latitude": float(lat),
            "longitude": float(lon),
            "address": address,
            "state": address_info.get("state", ""),
            "city": address_info.get("city") or address_info.get("town") or address_info.get("village") or "",
            "place": address_info.get("amenity") or address_info.get("suburb") or address,
        }
    except Exception:
        return {"ok": False, "error": "Unable to locate this place. Please try another location."}
