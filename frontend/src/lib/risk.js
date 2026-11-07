export const RISK_LEVELS = [
  { key: "low", label: "Low", color: "#2f9e5b" },
  { key: "moderate", label: "Moderate", color: "#e0b100" },
  { key: "high", label: "High", color: "#f07c1d" },
  { key: "severe", label: "Severe", color: "#d7263d" },
  { key: "no_travel", label: "No Travel", color: "#6b1f8f" },
];

const BY_KEY = Object.fromEntries(RISK_LEVELS.map((level, index) => [level.key, { ...level, index }]));

export const riskColor = (key) => BY_KEY[key]?.color ?? "#64748b";
export const riskLabel = (key) => BY_KEY[key]?.label ?? key;
export const riskIndex = (key) => BY_KEY[key]?.index ?? 0;

/** Average risk (0–4) → nearest level, for colouring summary values. */
export const levelForAverage = (avg) => RISK_LEVELS[Math.min(4, Math.round(avg))].key;
