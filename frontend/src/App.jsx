import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchHeatmap, planTrip } from "./api";
import CheckpointList from "./components/CheckpointList";
import HeatmapControls from "./components/HeatmapControls";
import HeatmapLayer from "./components/HeatmapLayer";
import Legend from "./components/Legend";
import PlanForm from "./components/PlanForm";
import RouteCards from "./components/RouteCards";
import RouteMap from "./components/RouteMap";
import TruckMarker from "./components/TruckMarker";
import { metricFrames, truckPosition } from "./lib/heatmapData";

const NO_HEATMAP = { status: "idle", data: null, error: null };

export default function App() {
  const [plan, setPlan] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [focusedIndex, setFocusedIndex] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [heatmap, setHeatmap] = useState(NO_HEATMAP);
  const [heatEnabled, setHeatEnabled] = useState(true);
  const [metric, setMetric] = useState("risk");
  const [hour, setHour] = useState(0);
  const [playing, setPlaying] = useState(false);

  const handleSubmit = async (payload) => {
    setLoading(true);
    setError(null);
    setPlaying(false);
    try {
      const result = await planTrip(payload);
      setPlan(result);
      setSelectedId(result.recommendation.route_id);
      setFocusedIndex(null);
      setHour(0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Load the corridor forecast once a plan arrives.
  useEffect(() => {
    if (!plan) return undefined;
    let cancelled = false;
    setHeatmap({ status: "loading", data: null, error: null });
    fetchHeatmap({ points: plan.heatmap_grid.points, start: plan.departure, load_lb: plan.load_lb })
      .then((data) => !cancelled && setHeatmap({ status: "ready", data, error: null }))
      .catch((err) => !cancelled && setHeatmap({ status: "error", data: null, error: err.message }));
    return () => {
      cancelled = true;
    };
  }, [plan]);

  const selectRoute = useCallback((id) => {
    setSelectedId(id);
    setFocusedIndex(null);
  }, []);

  const frames = useMemo(() => metricFrames(heatmap.data, metric), [heatmap.data, metric]);

  const selectedRoute = plan?.routes.find((r) => r.id === selectedId);
  const focusedCheckpoint = focusedIndex != null ? selectedRoute?.checkpoints[focusedIndex] : null;
  const truck =
    selectedRoute && heatmap.data
      ? truckPosition(selectedRoute, plan.departure, new Date(heatmap.data.hours[hour]))
      : null;

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
        <RouteMap plan={plan} selectedId={selectedId} onSelect={selectRoute} focusedCheckpoint={focusedCheckpoint}>
          {heatEnabled && frames && (
            <HeatmapLayer
              points={heatmap.data.points}
              spacingMi={plan.heatmap_grid.spacing_mi}
              values={frames[hour]}
            />
          )}
          {truck && <TruckMarker routeId={selectedRoute.id} position={truck} />}
        </RouteMap>
        <Legend />
        {plan && (
          <HeatmapControls
            heatmap={heatmap}
            enabled={heatEnabled}
            onToggle={setHeatEnabled}
            metric={metric}
            onMetric={setMetric}
            hour={hour}
            onHour={setHour}
            playing={playing}
            onPlaying={setPlaying}
          />
        )}
        {loading && <div className="map-loading">Fetching routes and forecasts…</div>}
      </main>
    </div>
  );
}
