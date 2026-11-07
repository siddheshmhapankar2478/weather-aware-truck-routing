import { formatTime } from "../lib/format";
import { riskColor, riskLabel } from "../lib/risk";

export default function CheckpointList({ route, focusedIndex, onFocus }) {
  return (
    <section className="checkpoints">
      <h3>
        Route {route.id} checkpoints <small>({route.checkpoints.length})</small>
      </h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Mile</th>
              <th>ETA</th>
              <th>Risk</th>
              <th title="Wind speed (mph)">Wind</th>
              <th title="Rain (in/hr)">Rain</th>
              <th title="Snow (in/hr)">Snow</th>
            </tr>
          </thead>
          <tbody>
            {route.checkpoints.map((cp, index) => (
              <tr
                key={cp.mile}
                className={index === focusedIndex ? "focused" : ""}
                onClick={() => onFocus(index)}
                title={cp.reasons.join("\n") || cp.weather.condition}
              >
                <td>{Math.round(cp.mile)}</td>
                <td>{formatTime(cp.eta)}</td>
                <td>
                  <span className="chip" style={{ background: riskColor(cp.level) }}>
                    {riskLabel(cp.level)}
                  </span>
                </td>
                <td>{Math.round(cp.weather.wind_mph)}</td>
                <td>{cp.weather.rain_in_hr.toFixed(2)}</td>
                <td>{cp.weather.snow_in_hr.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
