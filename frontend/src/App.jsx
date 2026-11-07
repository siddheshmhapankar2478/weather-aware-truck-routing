import { useCallback, useState } from "react";
import { planTrip } from "./api";
import CheckpointList from "./components/CheckpointList";
import Legend from "./components/Legend";
import PlanForm from "./components/PlanForm";
import RouteCards from "./components/RouteCards";
import RouteMap from "./components/RouteMap";

export default function App() {
  const [plan, setPlan] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [focusedIndex, setFocusedIndex] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (payload) => {
    setLoading(true);
    setError(null);
    try {
      const result = await planTrip(payload);
      setPlan(result);
      setSelectedId(result.recommendation.route_id);
      setFocusedIndex(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const selectRoute = useCallback((id) => {
    setSelectedId(id);
    setFocusedIndex(null);
  }, []);

  const selectedRoute = plan?.routes.find((r) => r.id === selectedId);
  const focusedCheckpoint = focusedIndex != null ? selectedRoute?.checkpoints[focusedIndex] : null;

  return (
    <div className="app">
      <aside className="sidebar">
        <header className="brand">
          <img src="/truck.svg" alt="" width="28" height="28" />
          <div>
            <h1>Weather-Aware Truck Routing</h1>
            <p>Compare routes by forecast weather at your ETA.</p>
          </div>
        </header>

        <PlanForm onSubmit={handleSubmit} loading={loading} />
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {plan && (
          <>
            <RouteCards plan={plan} selectedId={selectedId} onSelect={selectRoute} />
            {selectedRoute && (
              <CheckpointList route={selectedRoute} focusedIndex={focusedIndex} onFocus={setFocusedIndex} />
            )}
          </>
        )}
      </aside>

      <main className="map-area">
        <RouteMap plan={plan} selectedId={selectedId} onSelect={selectRoute} focusedCheckpoint={focusedCheckpoint} />
        <Legend />
        {loading && <div className="map-loading">Fetching routes and forecasts…</div>}
      </main>
    </div>
  );
}
