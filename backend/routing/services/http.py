"""Shared HTTP session for third-party APIs (retries, timeouts, user agent)."""

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class UpstreamError(Exception):
    """A third-party API failed or returned something we can't use."""


def _build_session() -> requests.Session:
    retry = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=16)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = settings.HTTP_USER_AGENT
    return session


_session = None


def get_json(url: str, params=None, *, timeout: float = 20, service: str = "Upstream"):
    global _session
    if _session is None:
        _session = _build_session()
    try:
        response = _session.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise UpstreamError(f"{service} service is unavailable right now ({exc.__class__.__name__}).") from exc
