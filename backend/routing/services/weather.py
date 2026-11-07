"""Hourly forecasts from Open-Meteo (free, no API key, many locations per call)."""

import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.cache import cache

from .geo import LatLon
from .http import UpstreamError, get_json

FORECAST_HORIZON = timedelta(days=15)
HOURLY_VARS = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall,temperature_2m,weather_code"
# Weather models resolve ~3–10 km, so nearby checkpoints can share one forecast.
GRID_DEG = 0.05
BATCH_SIZE = 50
CACHE_SECONDS = 30 * 60

WEATHER_CODES = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Freezing fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Rain showers", 81: "Rain showers", 82: "Violent rain showers",
    85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail",
}


@dataclass
class WeatherSample:
    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float
    temp_f: float | None
    condition: str

    def to_dict(self):
        data = asdict(self)
        for key in ("wind_mph", "gust_mph", "temp_f"):
            if data[key] is not None:
                data[key] = round(data[key], 1)
        for key in ("rain_in_hr", "snow_in_hr"):
            data[key] = round(data[key], 3)
        return data


@dataclass
class HourlySeries:
    """Hourly values for one location. Precipitation at hour H covers (H-1h, H]."""

    times: list[int]  # unix seconds, hourly
    wind: list[float]
    gust: list[float]
    rain: list[float]
    snow: list[float]
    temp: list[float | None]
    code: list[int | None]

    def at(self, when: datetime) -> WeatherSample:
        ts = when.timestamp()
        # Wind and temperature are instantaneous: interpolate between hours.
        i = max(0, min(len(self.times) - 2, int((ts - self.times[0]) // 3600)))
        t = max(0.0, min(1.0, (ts - self.times[i]) / 3600))
        # Rain and snow are hourly totals: use the hour bucket the truck is in.
        bucket = max(0, min(len(self.times) - 1, math.ceil((ts - self.times[0]) / 3600)))

        def interp(values):
            a, b = values[i], values[min(i + 1, len(values) - 1)]
            if a is None or b is None:
                return a if b is None else b
            return a + (b - a) * t

        code = self.code[bucket]
        return WeatherSample(
            wind_mph=interp(self.wind) or 0.0,
            gust_mph=interp(self.gust) or 0.0,
            rain_in_hr=self.rain[bucket] or 0.0,
            snow_in_hr=self.snow[bucket] or 0.0,
            temp_f=interp(self.temp),
            condition=WEATHER_CODES.get(code, "Unknown") if code is not None else "Unknown",
        )


def snap(point: LatLon) -> LatLon:
    return (round(round(point[0] / GRID_DEG) * GRID_DEG, 4), round(round(point[1] / GRID_DEG) * GRID_DEG, 4))


def _hour_floor(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _parse_location(raw: dict) -> HourlySeries:
    hourly = raw["hourly"]
    units = raw.get("hourly_units", {})
    n = len(hourly["time"])

    def values(name):
        return hourly.get(name) or [None] * n

    rain = [(r or 0.0) + (s or 0.0) for r, s in zip(values("rain"), values("showers"))]
    snow = [v or 0.0 for v in values("snowfall")]
    if units.get("snowfall") == "cm":  # older API behaviour: convert to inches
        snow = [v / 2.54 for v in snow]
    return HourlySeries(
        times=hourly["time"],
        wind=values("wind_speed_10m"),
        gust=values("wind_gusts_10m"),
        rain=rain,
        snow=snow,
        temp=values("temperature_2m"),
        code=values("weather_code"),
    )


def _fetch_batch(points: list[LatLon], start: datetime, end: datetime) -> list[HourlySeries]:
    data = get_json(
        settings.OPEN_METEO_URL,
        {
            "latitude": ",".join(f"{p[0]:.4f}" for p in points),
            "longitude": ",".join(f"{p[1]:.4f}" for p in points),
            "hourly": HOURLY_VARS,
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "temperature_unit": "fahrenheit",
            "timezone": "GMT",
            "timeformat": "unixtime",
            "start_hour": start.strftime("%Y-%m-%dT%H:%M"),
            "end_hour": end.strftime("%Y-%m-%dT%H:%M"),
        },
        timeout=30,
        service="Weather",
    )
    if isinstance(data, dict):
        if data.get("error"):
            raise UpstreamError(f"Weather service error: {data.get('reason', 'unknown')}")
        data = [data]
    if len(data) != len(points):
        raise UpstreamError("Weather service returned an unexpected number of locations.")
    return [_parse_location(item) for item in data]


def fetch_hourly(points: list[LatLon], start: datetime, end: datetime) -> dict[LatLon, HourlySeries]:
    """Hourly series for each point, keyed by the point's snapped grid cell.

    Look up a point's series with `series[snap(point)]`.
    """
    start = _hour_floor(start)
    end = _hour_floor(end) + timedelta(hours=1)
    span_key = f"{int(start.timestamp())}:{int(end.timestamp())}"

    result: dict[LatLon, HourlySeries] = {}
    missing: list[LatLon] = []
    for cell in dict.fromkeys(snap(p) for p in points):
        cached = cache.get(f"wx:{cell[0]}:{cell[1]}:{span_key}")
        if cached is not None:
            result[cell] = cached
        else:
            missing.append(cell)

    batches = [missing[i : i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
    if batches:
        with ThreadPoolExecutor(max_workers=min(4, len(batches))) as pool:
            for batch, series_list in zip(batches, pool.map(lambda b: _fetch_batch(b, start, end), batches)):
                for cell, series in zip(batch, series_list):
                    result[cell] = series
                    cache.set(f"wx:{cell[0]}:{cell[1]}:{span_key}", series, CACHE_SECONDS)
    return result
