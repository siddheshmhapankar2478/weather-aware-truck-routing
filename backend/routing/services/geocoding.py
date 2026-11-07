"""Place search via Photon (OpenStreetMap data, no API key)."""

import re
from dataclasses import asdict, dataclass

from django.conf import settings
from django.core.cache import cache

from .http import get_json

_COORD_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


@dataclass
class Place:
    label: str
    lat: float
    lon: float

    def to_dict(self):
        return asdict(self)


def _label(props: dict) -> str:
    parts = []
    for key in ("name", "city", "state", "country"):
        value = props.get(key)
        if value and value not in parts:
            parts.append(value)
    return ", ".join(parts)


def search_places(query: str, limit: int = 5) -> list[Place]:
    query = query.strip()
    if len(query) < 2:
        return []
    cache_key = f"geocode:{limit}:{query.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = get_json(
        f"{settings.PHOTON_URL}/api/",
        {"q": query, "limit": limit, "lang": "en"},
        timeout=10,
        service="Geocoding",
    )
    places = []
    for feature in data.get("features", []):
        lon, lat = feature["geometry"]["coordinates"][:2]
        places.append(Place(label=_label(feature.get("properties", {})), lat=lat, lon=lon))
    cache.set(cache_key, places, 24 * 3600)
    return places


def resolve_place(value) -> Place:
    """Accept {label, lat, lon}, "lat, lon" or free text, and return a Place."""
    if isinstance(value, dict) and value.get("lat") is not None and value.get("lon") is not None:
        lat, lon = float(value["lat"]), float(value["lon"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise LookupError("Coordinates are out of range.")
        return Place(label=value.get("label") or f"{lat:.4f}, {lon:.4f}", lat=lat, lon=lon)

    text = value.get("label", "") if isinstance(value, dict) else str(value or "")
    match = _COORD_RE.match(text)
    if match:
        return resolve_place({"lat": match.group(1), "lon": match.group(2), "label": text.strip()})

    results = search_places(text, limit=1)
    if not results:
        raise LookupError(f'Could not find a location for "{text}".')
    return results[0]
