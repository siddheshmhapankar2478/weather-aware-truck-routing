import { useState } from "react";
import { nextHourLocalInput } from "../lib/format";
import PlaceInput from "./PlaceInput";

const INTERVALS = [10, 25, 50];

const PRESETS = [
  { name: "Denver → Chicago", origin: "Denver, Colorado", destination: "Chicago, Illinois" },
  { name: "Seattle → Salt Lake City", origin: "Seattle, Washington", destination: "Salt Lake City, Utah" },
  { name: "Dallas → Atlanta", origin: "Dallas, Texas", destination: "Atlanta, Georgia" },
];

export default function PlanForm({ onSubmit, loading }) {
  const [origin, setOrigin] = useState({ label: "" });
  const [destination, setDestination] = useState({ label: "" });
  const [departure, setDeparture] = useState(nextHourLocalInput);
  const [loadLb, setLoadLb] = useState(35000);
  const [intervalMi, setIntervalMi] = useState(25);

  const submit = (event) => {
    event.preventDefault();
    onSubmit({
      origin,
      destination,
      departure: new Date(departure).toISOString(),
      load_lb: Number(loadLb),
      interval_mi: intervalMi,
    });
  };

  const applyPreset = (preset) => {
    setOrigin({ label: preset.origin });
    setDestination({ label: preset.destination });
  };

  return (
    <form className="plan-form" onSubmit={submit}>
      <PlaceInput label="Origin" value={origin} onChange={setOrigin} placeholder="City or address" />
      <PlaceInput label="Destination" value={destination} onChange={setDestination} placeholder="City or address" />

      <div className="field-row">
        <label className="field">
          <span>Departure</span>
          <input type="datetime-local" value={departure} onChange={(e) => setDeparture(e.target.value)} required />
        </label>
        <label className="field">
          <span>Load (lb)</span>
          <input
            type="number"
            min="0"
            max="120000"
            step="500"
            value={loadLb}
            onChange={(e) => setLoadLb(e.target.value)}
            required
          />
        </label>
      </div>

      <div className="field">
        <span>Weather checkpoint every</span>
        <div className="segmented" role="radiogroup" aria-label="Checkpoint interval">
          {INTERVALS.map((miles) => (
            <button
              key={miles}
              type="button"
              role="radio"
              aria-checked={intervalMi === miles}
              className={intervalMi === miles ? "selected" : ""}
              onClick={() => setIntervalMi(miles)}
            >
              {miles} mi
            </button>
          ))}
        </div>
      </div>

      <button type="submit" className="primary" disabled={loading}>
        {loading ? "Checking routes and weather…" : "Find safest route"}
      </button>

      <div className="presets">
        <span>Try:</span>
        {PRESETS.map((preset) => (
          <button key={preset.name} type="button" className="link" onClick={() => applyPreset(preset)}>
            {preset.name}
          </button>
        ))}
      </div>
    </form>
  );
}
