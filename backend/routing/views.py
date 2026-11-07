import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .services.geo import simplify
from .services.geocoding import resolve_place, search_places
from .services.http import UpstreamError
from .services.routing import NoRouteError, find_route_options

logger = logging.getLogger(__name__)


def _error(message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _json_body(request) -> dict:
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Request body must be valid JSON.") from exc
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object.")
    return body


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


@require_GET
def geocode(request):
    try:
        places = search_places(request.GET.get("q", ""))
    except UpstreamError as exc:
        return _error(str(exc), 502)
    return JsonResponse({"results": [p.to_dict() for p in places]})


@require_POST
def routes(request):
    try:
        body = _json_body(request)
        origin = resolve_place(body.get("origin"))
        destination = resolve_place(body.get("destination"))
        options = find_route_options((origin.lat, origin.lon), (destination.lat, destination.lon))
    except (ValueError, LookupError, NoRouteError) as exc:
        return _error(str(exc), 400)
    except UpstreamError as exc:
        return _error(str(exc), 502)

    return JsonResponse(
        {
            "origin": origin.to_dict(),
            "destination": destination.to_dict(),
            "routes": [
                {
                    "id": chr(ord("A") + i),
                    "summary": r.summary,
                    "distance_mi": round(r.distance_mi, 1),
                    "duration_s": round(r.duration_s),
                    "geometry": [[round(lat, 5), round(lon, 5)] for lat, lon in simplify(r.coords, 0.0005)],
                }
                for i, r in enumerate(options)
            ],
        }
    )
