from __future__ import annotations

from functools import lru_cache

try:
    import googlemaps
except ImportError:  # pragma: no cover - optional dependency fallback
    googlemaps = None

from config import Config


def google_maps_ready() -> bool:
    """Return whether the Google Maps client can make live requests."""
    return bool(Config.GOOGLE_MAPS_API_KEY and Config.GOOGLE_MAPS_API_KEY != "your_google_maps_api_key_here")


def get_client():
    """Return a Google Maps client if configured, otherwise None."""
    if not google_maps_ready():
        return None
    if googlemaps is None:
        return None
    try:
        return googlemaps.Client(key=Config.GOOGLE_MAPS_API_KEY)
    except Exception as exc:
        print(f"[MAPS][ERROR] Failed to initialize Google Maps client: {exc}")
        return None


@lru_cache(maxsize=256)
def get_address(lat: float, lng: float) -> str:
    """
    Reverse geocode coordinates to street address using Google Maps API.
    Cache results to avoid duplicate API calls.
    Return 'Unknown Location' if API call fails.
    """
    client = get_client()
    if client is None:
        return "Unknown Location"
    try:
        results = client.reverse_geocode((lat, lng))
        if not results:
            return "Unknown Location"
        return results[0].get("formatted_address", "Unknown Location")
    except Exception as exc:
        print(f"[MAPS][ERROR] Reverse geocode failed: {exc}")
        return "Unknown Location"


def get_maps_link(lat: float, lng: float) -> str:
    """Return a clickable Google Maps URL for the coordinates."""
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"


def detect_zone(address: str) -> str:
    """
    Try to detect zone name from address string.
    Return 'Unknown Zone' if not detectable.
    """
    if not address or address == "Unknown Location":
        return "Unknown Zone"
    zone_tokens = [token.strip() for token in address.split(",") if token.strip()]
    for token in zone_tokens:
        if any(char.isdigit() for char in token):
            continue
        if len(token) >= 3:
            return token
    return "Unknown Zone"
