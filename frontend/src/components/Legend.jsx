import { RISK_LEVELS } from "../lib/risk";

export default function Legend() {
  return (
    <div className="legend map-panel" aria-label="Risk legend">
      {RISK_LEVELS.map(({ key, label, color }) => (
        <span key={key}>
          <i style={{ background: color }} />
          {label}
        </span>
      ))}
    </div>
  );
}
