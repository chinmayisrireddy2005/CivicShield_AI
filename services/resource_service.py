import math
import os
import re
from typing import Any, Dict, List

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_FALLBACK_URLS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
)
GOOGLE_PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
RESOURCE_CATEGORIES = {
    "hospital": "Hospital",
    "police": "Police Station",
    "fire_station": "Fire Station",
}


def _resource_label(resource_type: str) -> str:
    mapping = {
        "hospital": "Hospital",
        "fire_station": "Fire Station",
        "police": "Police Station",
        "police_station": "Police Station",
    }
    return mapping.get(resource_type, resource_type.replace("_", " ").title())


def _extract_name(tag: Dict[str, Any]) -> str:
    for key in ("official_name", "name:en", "name", "alt_name", "brand", "operator"):
        value = (tag.get(key) or "").strip()
        if value:
            return value
    return ""


def _extract_address(tag: Dict[str, Any]) -> str:
    address_parts = [
        tag.get("addr:full"),
        tag.get("addr:street"),
        tag.get("addr:suburb"),
        tag.get("addr:city"),
        tag.get("description"),
    ]
    cleaned = [part for part in address_parts if isinstance(part, str) and part.strip()]
    if cleaned:
        return cleaned[0]
    return "Address unavailable"


def resource_types_for_incident(emergency_type: str) -> set[str]:
    allowed_types = {"hospital", "police"}
    if "FIRE" in (emergency_type or "").upper():
        allowed_types.add("fire_station")
    return allowed_types


def _filter_resources_by_incident(emergency_type: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    allowed_types = resource_types_for_incident(emergency_type)
    return [item for item in items if item.get("type") in allowed_types]


def _classify_osm_resource(tag: Dict[str, Any]) -> str:
    amenity = (tag.get("amenity") or "").strip().lower()
    emergency = (tag.get("emergency") or "").strip().lower()
    healthcare = (tag.get("healthcare") or "").strip().lower()
    police = (tag.get("police") or "").strip().lower()
    building = (tag.get("building") or "").strip().lower()
    government = (tag.get("government") or "").strip().lower()
    office = (tag.get("office") or "").strip().lower()
    name = " ".join(
        str(tag.get(key) or "")
        for key in ("name", "name:en", "official_name", "alt_name", "operator")
    )
    if amenity == "fire_station" or emergency == "fire_station" or building == "fire_station":
        return "fire_station"
    if (
        amenity in {"police", "police_station"}
        or emergency in {"police", "police_station"}
        or government == "police"
        or police == "station"
        or building == "police"
        or (office == "government" and "police" in name.lower())
        or re.search(
            r"\bpolice\b.*\b(station|outpost|chowky|chowki|post|headquarters|hq)\b",
            name,
            re.IGNORECASE,
        )
    ):
        return "police"
    if amenity in {"hospital", "clinic"} or healthcare == "hospital":
        return "hospital"
    return ""


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class ResourceLookupError(Exception):
    pass


def _fetch_google_places(lat: float, lon: float, emergency_type: str) -> List[Dict[str, Any]]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        return []

    resources = []
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,places.location,"
            "places.googleMapsUri,places.nationalPhoneNumber,places.websiteUri"
        ),
    }
    allowed_types = resource_types_for_incident(emergency_type)
    for resource_type in RESOURCE_CATEGORIES:
        if resource_type not in allowed_types:
            continue
        try:
            response = requests.post(
                GOOGLE_PLACES_SEARCH_URL,
                headers=headers,
                json={
                    "includedTypes": [resource_type],
                    "maxResultCount": 4,
                    "locationRestriction": {
                        "circle": {
                            "center": {"latitude": lat, "longitude": lon},
                            "radius": 10000,
                        }
                    },
                },
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("places", []), list):
                raise ValueError("Google Places returned an invalid response.")
        except (requests.RequestException, ValueError) as exc:
            raise ResourceLookupError(
                "Google Places nearby search failed. Check the key, Places API access, billing, and network."
            ) from exc

        for place in payload.get("places", []):
            location = place.get("location") or {}
            display_name = place.get("displayName") or {}
            name = display_name.get("text", "").strip()
            place_lat = location.get("latitude")
            place_lon = location.get("longitude")
            if not name or place_lat is None or place_lon is None:
                continue
            resources.append({
                "name": name,
                "type": resource_type,
                "type_label": RESOURCE_CATEGORIES[resource_type],
                "address": place.get("formattedAddress") or "Address unavailable",
                "lat": float(place_lat),
                "lon": float(place_lon),
                "distance_km": round(_distance_km(lat, lon, float(place_lat), float(place_lon)), 2),
                "phone": place.get("nationalPhoneNumber") or "Phone unavailable",
                "website": place.get("websiteUri") or "Website unavailable",
                "osm_url": "",
                "source": "Google Maps",
                "source_url": place.get("googleMapsUri") or "",
                "place_id": place.get("id") or "",
            })
    return resources


def _fetch_overpass_query(lat: float, lon: float, query: str) -> List[Dict[str, Any]]:
    payload = {"data": query}
    last_error = None
    for endpoint in (OVERPASS_URL, *OVERPASS_FALLBACK_URLS):
        try:
            response = requests.post(
                endpoint,
                data=payload,
                headers={"User-Agent": "CivicShieldAI/1.0"},
                timeout=(5, 35),
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict) or not isinstance(result.get("elements"), list):
                raise ValueError("Overpass returned an invalid response.")
            return result["elements"]
        except (requests.RequestException, ValueError) as exc:
            last_error = exc

    raise ResourceLookupError(
        "OpenStreetMap nearby lookup failed. Please try again shortly or use the map search links."
    ) from last_error


def get_nearby_resources(lat: float, lon: float, emergency_type: str) -> List[Dict[str, Any]]:
    radius = 10000
    allowed_types = resource_types_for_incident(emergency_type)
    query_parts = []
    if "hospital" in allowed_types:
        query_parts.extend([
            f'nwr["amenity"~"^(hospital|clinic)$"](around:{radius},{lat},{lon});',
            f'nwr["healthcare"="hospital"](around:{radius},{lat},{lon});',
        ])
    if "police" in allowed_types:
        query_parts.extend([
            f'nwr["amenity"~"^(police|police_station)$"](around:{radius},{lat},{lon});',
            f'nwr["emergency"~"^(police|police_station)$"](around:{radius},{lat},{lon});',
            f'nwr["government"="police"](around:{radius},{lat},{lon});',
            f'nwr["police"="station"](around:{radius},{lat},{lon});',
            f'nwr["building"="police"](around:{radius},{lat},{lon});',
        ])
    if "fire_station" in allowed_types:
        query_parts.extend([
            f'nwr["amenity"="fire_station"](around:{radius},{lat},{lon});',
            f'nwr["emergency"="fire_station"](around:{radius},{lat},{lon});',
            f'nwr["building"="fire_station"](around:{radius},{lat},{lon});',
        ])
    query = f'[out:json][timeout:30];({"".join(query_parts)});out center tags;'
    google_error = None
    try:
        resources = _fetch_google_places(lat, lon, emergency_type)
    except ResourceLookupError as exc:
        resources = []
        google_error = exc
    try:
        items = _fetch_overpass_query(lat, lon, query)
    except ResourceLookupError as exc:
        if resources:
            return sorted(resources, key=lambda item: item["distance_km"])
        if google_error:
            raise ResourceLookupError(
                "Google Places and OpenStreetMap lookups both failed. Check GOOGLE_MAPS_API_KEY, Places API access, billing, and internet connectivity."
            ) from google_error
        raise exc

    for el in items:
        tag = el.get("tags") or {}
        if not tag:
            continue
        item_lat = el.get("lat")
        item_lon = el.get("lon")
        if item_lat is None and "center" in el:
            item_lat = el["center"].get("lat")
            item_lon = el["center"].get("lon")
        if item_lat is None or item_lon is None:
            continue
        osm_type = el.get("type")
        osm_id = el.get("id")
        osm_url = (
            f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
            if osm_type in {"node", "way", "relation"} and isinstance(osm_id, int)
            else ""
        )

        ele_type = _classify_osm_resource(tag)
        if not ele_type:
            continue

        resource_record = {
            "name": _extract_name(tag),
            "type": ele_type,
            "type_label": _resource_label(ele_type),
            "address": _extract_address(tag),
            "lat": float(item_lat),
            "lon": float(item_lon),
            "distance_km": round(_distance_km(lat, lon, float(item_lat), float(item_lon)), 2),
            "phone": tag.get("phone") or "Phone unavailable",
            "website": tag.get("website") or "Website unavailable",
            "osm_url": osm_url,
            "source": "OpenStreetMap",
            "source_url": osm_url,
            "place_id": "",
        }
        if resource_record["name"]:
            resources.append(resource_record)

    filtered = _filter_resources_by_incident(emergency_type, resources)
    categories = ["hospital", "police", "fire_station"]
    selected = []
    for category in categories:
        nearest = sorted(
            (item for item in filtered if item.get("type") == category),
            key=lambda item: (item.get("source") != "Google Maps", item.get("distance_km", 9999)),
        )
        seen = set()
        for item in nearest:
            identity = (
                item.get("name", "").casefold(),
                round(item.get("lat", 0), 4),
                round(item.get("lon", 0), 4),
            )
            if identity in seen:
                continue
            seen.add(identity)
            selected.append(item)
            if len(seen) == 4:
                break
    return sorted(selected, key=lambda item: item.get("distance_km", 9999))
