"""Weather risk rules from the assessment brief.

| Condition | Low      | Moderate  | High      | Severe    | No Travel |
|-----------|----------|-----------|-----------|-----------|-----------|
| Wind mph  | <25      | 25–34     | 35–44     | 45–54     | ≥55       |
| Rain in/h | <0.10    | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | >1.00     |
| Snow in/h | <0.5     | 0.5–1.0   | 1.0–2.0   | 2.0–3.0   | >3.0      |

Shared boundaries (e.g. rain 0.25) go to the higher level. Load rules:
  * ≥55 mph               → No Travel for any load
  * 45–54 mph + >30,000 lb → No Travel
  * 35–44 mph + >40,000 lb → Severe
A checkpoint's level is the worst of its wind, rain and snow levels.
"""

from dataclasses import dataclass, field
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def key(self) -> str:
        return self.name.lower()

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


def classify_wind(mph: float) -> RiskLevel:
    if mph >= 55:
        return RiskLevel.NO_TRAVEL
    if mph >= 45:
        return RiskLevel.SEVERE
    if mph >= 35:
        return RiskLevel.HIGH
    if mph >= 25:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_rain(in_per_hr: float) -> RiskLevel:
    if in_per_hr > 1.0:
        return RiskLevel.NO_TRAVEL
    if in_per_hr >= 0.5:
        return RiskLevel.SEVERE
    if in_per_hr >= 0.25:
        return RiskLevel.HIGH
    if in_per_hr >= 0.10:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_snow(in_per_hr: float) -> RiskLevel:
    if in_per_hr > 3.0:
        return RiskLevel.NO_TRAVEL
    if in_per_hr >= 2.0:
        return RiskLevel.SEVERE
    if in_per_hr >= 1.0:
        return RiskLevel.HIGH
    if in_per_hr >= 0.5:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def wind_level_for_load(mph: float, load_lb: float) -> tuple[RiskLevel, bool]:
    """Wind level after load rules. Returns (level, raised_by_load)."""
    level = classify_wind(mph)
    if level == RiskLevel.SEVERE and load_lb > 30_000:
        return RiskLevel.NO_TRAVEL, True
    if level == RiskLevel.HIGH and load_lb > 40_000:
        return RiskLevel.SEVERE, True
    return level, False


@dataclass
class Assessment:
    level: RiskLevel
    wind: RiskLevel
    rain: RiskLevel
    snow: RiskLevel
    reasons: list[str] = field(default_factory=list)


def assess(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float) -> Assessment:
    wind, raised = wind_level_for_load(wind_mph, load_lb)
    rain = classify_rain(rain_in_hr)
    snow = classify_snow(snow_in_hr)

    reasons = []
    if raised:
        reasons.append(f"Wind {wind_mph:.0f} mph with {load_lb:,.0f} lb load → {wind.label}")
    elif wind > RiskLevel.LOW:
        reasons.append(f"Wind {wind_mph:.0f} mph → {wind.label}")
    if rain > RiskLevel.LOW:
        reasons.append(f"Rain {rain_in_hr:.2f} in/hr → {rain.label}")
    if snow > RiskLevel.LOW:
        reasons.append(f"Snow {snow_in_hr:.2f} in/hr → {snow.label}")

    return Assessment(level=max(wind, rain, snow), wind=wind, rain=rain, snow=snow, reasons=reasons)


# --- Continuous scores for the heatmap ---------------------------------------
# Where Moderate, High, Severe and No Travel begin for each condition.
WIND_BOUNDS = (25, 35, 45, 55)
RAIN_BOUNDS = (0.10, 0.25, 0.50, 1.00)
SNOW_BOUNDS = (0.5, 1.0, 2.0, 3.0)


def _score(level: RiskLevel, value: float, bounds: tuple[float, ...]) -> float:
    """Level plus how far the value is through that level's band (0–4).

    The whole part always equals the discrete level, so the heatmap and the
    checkpoint labels agree; the fraction just lets colours blend smoothly.
    """
    if level == RiskLevel.NO_TRAVEL:
        return 4.0
    low = 0.0 if level == RiskLevel.LOW else bounds[level - 1]
    high = bounds[level]
    return level + min(0.99, max(0.0, (value - low) / (high - low)))


def condition_scores(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float) -> tuple[float, float, float]:
    """Continuous (wind, rain, snow) scores on the 0–4 risk scale, load rules included."""
    base_wind = classify_wind(wind_mph)
    wind, _ = wind_level_for_load(wind_mph, load_lb)
    wind_score = 4.0 if wind == RiskLevel.NO_TRAVEL else _score(base_wind, wind_mph, WIND_BOUNDS) + (wind - base_wind)
    return (
        wind_score,
        _score(classify_rain(rain_in_hr), rain_in_hr, RAIN_BOUNDS),
        _score(classify_snow(snow_in_hr), snow_in_hr, SNOW_BOUNDS),
    )
