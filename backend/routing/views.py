import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .services.geocoding import search_places
from .services.http import UpstreamError
from .services.heatmap import MAX_POINTS, build_heatmap
from .services.planner import PlanError, PlanRequest, build_plan, parse_departure, parse_load
from .services.routing import NoRouteError

logger = logging.getLogger(__name__)


def _error(message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _json_body(request) -> dict:
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError as exc:
        raise PlanError("Request body must be valid JSON.") from exc
    if not isinstance(body, dict):
        raise PlanError("Request body must be a JSON object.")
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
def plan(request):
    try:
        plan_request = PlanRequest.from_json(_json_body(request))
        return JsonResponse(build_plan(plan_request))
    except (PlanError, LookupError, NoRouteError) as exc:
        return _error(str(exc), 400)
    except UpstreamError as exc:
        logger.warning("Upstream failure while planning: %s", exc)
        return _error(str(exc), 502)


def _parse_points(raw) -> list[tuple[float, float]]:
    if not isinstance(raw, list) or not raw:
        raise PlanError("Heatmap points are required.")
    if len(raw) > MAX_POINTS:
        raise PlanError(f"At most {MAX_POINTS} heatmap points are allowed.")
    try:
        points = [(float(lat), float(lon)) for lat, lon in raw]
    except (TypeError, ValueError) as exc:
        raise PlanError("Heatmap points must be [lat, lon] pairs.") from exc
    if not all(-90 <= lat <= 90 and -180 <= lon <= 180 for lat, lon in points):
        raise PlanError("Heatmap points are out of range.")
    return points


@require_POST
def heatmap(request):
    try:
        body = _json_body(request)
        data = build_heatmap(_parse_points(body.get("points")), parse_departure(body.get("start")), parse_load(body.get("load_lb")))
        return JsonResponse(data)
    except PlanError as exc:
        return _error(str(exc), 400)
    except UpstreamError as exc:
        logger.warning("Upstream failure while building heatmap: %s", exc)
        return _error(str(exc), 502)
