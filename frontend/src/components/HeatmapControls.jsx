import { useEffect } from "react";
import { formatDateTime } from "../lib/format";

export const METRICS = [
  { key: "risk", label: "Risk" },
  { key: "wind", label: "Wind" },
  { key: "rain", label: "Rain" },
  { key: "snow", label: "Snow" },
];

const PLAY_STEP_MS = 450;

export default function HeatmapControls({ heatmap, enabled, onToggle, metric, onMetric, hour, onHour, playing, onPlaying }) {
  const maxHour = heatmap.data ? heatmap.data.hours.length - 1 : 48;

  useEffect(() => {
    if (!playing) return undefined;
    const timer = setInterval(() => onHour((h) => (h >= maxHour ? 0 : h + 1)), PLAY_STEP_MS);
    return () => clearInterval(timer);
  }, [playing, maxHour, onHour]);

  const label = heatmap.data ? formatDateTime(heatmap.data.hours[hour]) : "";

  return (
    <div className="heat-controls map-panel">
      <div className="heat-row">
        <label className="toggle">
          <input type="checkbox" checked={enabled} onChange={(e) => onToggle(e.target.checked)} />
          Weather heatmap
        </label>
        <div className="segmented small" role="radiogroup" aria-label="Heatmap layer">
          {METRICS.map((m) => (
            <button
              key={m.key}
              type="button"
              role="radio"
              aria-checked={metric === m.key}
              className={metric === m.key ? "selected" : ""}
              onClick={() => onMetric(m.key)}
              disabled={!enabled}
            >
              {m.label}
            </button>
          ))}
        </div>
        {heatmap.status === "loading" && <span className="muted">Loading forecast…</span>}
        {heatmap.status === "error" && <span className="error-text">{heatmap.error}</span>}
      </div>

      <div className="heat-row">
        <button
          type="button"
          className="play"
          onClick={() => onPlaying(!playing)}
          disabled={!heatmap.data}
          aria-label={playing ? "Pause forecast animation" : "Play forecast animation"}
        >
          {playing ? "❚❚" : "▶"}
        </button>
        <input
          type="range"
          min="0"
          max={maxHour}
          step="1"
          value={hour}
          disabled={!heatmap.data}
          onChange={(e) => {
            onPlaying(false);
            onHour(Number(e.target.value));
          }}
          aria-label="Forecast hour"
        />
        <span className="hour-label">
          <b>+{hour}h</b> {label}
        </span>
      </div>
    </div>
  );
}
