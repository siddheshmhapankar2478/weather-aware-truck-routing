import { formatDuration, formatMiles, formatTime } from "../lib/format";
import { RISK_LEVELS, levelForAverage, riskColor, riskLabel } from "../lib/risk";

function RiskBar({ miles, total }) {
  return (
    <div className="risk-bar" aria-hidden="true">
      {RISK_LEVELS.map(({ key, color }) =>
        miles[key] > 0 ? (
          <span key={key} style={{ width: `${(miles[key] / total) * 100}%`, background: color }} />
        ) : null,
      )}
    </div>
  );
}

function RiskMiles({ miles }) {
  const shown = RISK_LEVELS.filter(({ key }) => key !== "low" && miles[key] > 0);
  if (!shown.length) return <p className="risk-miles">All {formatMiles(miles.low)} in Low risk</p>;
  return (
    <p className="risk-miles">
      {shown.map(({ key, label, color }) => (
        <span key={key}>
          <i style={{ background: color }} />
          {label} {formatMiles(miles[key])}
        </span>
      ))}
    </p>
  );
}

export default function RouteCards({ plan, selectedId, onSelect }) {
  const { recommendation } = plan;
  return (
    <section className="route-cards" aria-label="Route options">
      <div className="recommendation">
        <strong>Recommended: Route {recommendation.route_id}</strong>
        <p>{recommendation.reason}</p>
        {recommendation.warning && <p className="warning">⚠ {recommendation.warning}</p>}
      </div>

      {plan.routes.map((route) => {
        const total = Object.values(route.risk.miles).reduce((a, b) => a + b, 0) || 1;
        const recommended = route.id === recommendation.route_id;
        return (
          <button
            key={route.id}
            type="button"
            className={`route-card${route.id === selectedId ? " selected" : ""}`}
            onClick={() => onSelect(route.id)}
            aria-pressed={route.id === selectedId}
          >
            <div className="route-card-head">
              <span className="route-id">{route.id}</span>
              <span className="route-summary" title={route.summary}>
                {route.summary || "Unnamed roads"}
              </span>
              {recommended ? <span className="badge best">Best</span> : <span className="badge">#{route.rank}</span>}
            </div>
            <div className="route-stats">
              <span>{formatMiles(route.distance_mi)}</span>
              <span>{formatDuration(route.duration_s)}</span>
              <span>Arrive {formatTime(route.arrival)}</span>
            </div>
            <RiskBar miles={route.risk.miles} total={total} />
            <RiskMiles miles={route.risk.miles} />
            <div className="route-stats subtle">
              <span>
                Avg risk{" "}
                <b style={{ color: riskColor(levelForAverage(route.risk.average)) }}>{route.risk.average.toFixed(2)}</b>{" "}
                / 4
              </span>
              <span>
                Worst <b style={{ color: riskColor(route.risk.max_level) }}>{riskLabel(route.risk.max_level)}</b>
              </span>
            </div>
          </button>
        );
      })}
    </section>
  );
}
