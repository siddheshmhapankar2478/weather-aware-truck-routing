import { memo, useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Marker, Pane, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import { formatDuration, formatMiles, formatTime } from "../lib/format";
import { riskColor, riskLabel } from "../lib/risk";

const US_CENTER = [39.5, -98.35];

const endpointIcon = (letter, className) =>
  L.divIcon({ className: `endpoint ${className}`, html: letter, iconSize: [26, 26], iconAnchor: [13, 13] });
const ORIGIN_ICON = endpointIcon("S", "origin");
const DESTINATION_ICON = endpointIcon("E", "destination");

function FitToPlan({ plan }) {
  const map = useMap();
  useEffect(() => {
    if (!plan) return;
    const bounds = L.latLngBounds(plan.routes.flatMap((r) => r.geometry));
    map.fitBounds(bounds, { padding: [40, 40] });
  }, [map, plan]);
  return null;
}

function FlyToCheckpoint({ checkpoint }) {
  const map = useMap();
  useEffect(() => {
    if (checkpoint) map.flyTo([checkpoint.lat, checkpoint.lon], Math.max(map.getZoom(), 9), { duration: 0.6 });
  }, [map, checkpoint]);
  return null;
}

function CheckpointTooltip({ routeId, cp }) {
  return (
    <Tooltip direction="top" offset={[0, -6]}>
      <div className="cp-tooltip">
        <strong>
          Route {routeId} · mile {Math.round(cp.mile)}
        </strong>
        <div>ETA {formatTime(cp.eta)}</div>
        <div>
          <span className="chip" style={{ background: riskColor(cp.level) }}>
            {riskLabel(cp.level)}
          </span>{" "}
          {cp.weather.condition}
          {cp.weather.temp_f != null && `, ${Math.round(cp.weather.temp_f)}°F`}
        </div>
        <div>
          Wind {Math.round(cp.weather.wind_mph)} mph (gust {Math.round(cp.weather.gust_mph)}) · Rain{" "}
          {cp.weather.rain_in_hr.toFixed(2)} · Snow {cp.weather.snow_in_hr.toFixed(2)} in/hr
        </div>
        {cp.reasons.map((reason) => (
          <div key={reason} className="reason">
            {reason}
          </div>
        ))}
      </div>
    </Tooltip>
  );
}

/** One route: dashed grey line when idle, risk-coloured line when selected. */
const RouteLayer = memo(function RouteLayer({ route, selected, recommended, onSelect }) {
  const handlers = useMemo(() => ({ click: () => onSelect(route.id) }), [onSelect, route.id]);
  const pane = selected ? "selected-route" : "overlayPane";

  return (
    <>
      <Polyline
        positions={route.geometry}
        pane={pane}
        eventHandlers={handlers}
        pathOptions={
          selected
            ? { color: "#0f172a", weight: 9, opacity: 0.55 }
            : { color: "#475569", weight: 5, opacity: 0.45, dashArray: "8 8" }
        }
      >
        <Tooltip permanent direction="center" className={`route-label${selected ? " selected" : ""}`}>
          <b>{route.id}</b> {formatMiles(route.distance_mi)} · {formatDuration(route.duration_s)}
          {recommended && " ★"}
        </Tooltip>
      </Polyline>

      {selected &&
        route.segments.map((segment, i) => (
          <Polyline
            key={i}
            positions={segment.coords}
            pane={pane}
            eventHandlers={handlers}
            pathOptions={{ color: riskColor(segment.level), weight: 5, opacity: 1 }}
          />
        ))}

      {route.checkpoints.map((cp) => (
        <CircleMarker
          key={cp.mile}
          center={[cp.lat, cp.lon]}
          radius={selected ? 5 : 3}
          pane={selected ? "selected-checkpoints" : "overlayPane"}
          eventHandlers={handlers}
          pathOptions={{
            color: "#ffffff",
            weight: selected ? 1.5 : 1,
            opacity: selected ? 1 : 0.6,
            fillColor: riskColor(cp.level),
            fillOpacity: selected ? 1 : 0.6,
          }}
        >
          <CheckpointTooltip routeId={route.id} cp={cp} />
        </CircleMarker>
      ))}
    </>
  );
});

export default function RouteMap({ plan, selectedId, onSelect, focusedCheckpoint, children }) {
  // Draw the selected route last so it sits on top.
  const ordered = useMemo(
    () => (plan ? [...plan.routes].sort((a, b) => (a.id === selectedId) - (b.id === selectedId)) : []),
    [plan, selectedId],
  );

  return (
    <MapContainer center={US_CENTER} zoom={4} maxZoom={16} preferCanvas className="map" zoomControl>
      <TileLayer
        attribution="Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors"
        url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        maxZoom={16}
      />
      <TileLayer
        url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
        maxZoom={16}
        pane="shadowPane"
      />
      <Pane name="selected-route" style={{ zIndex: 450 }} />
      <Pane name="selected-checkpoints" style={{ zIndex: 460 }} />
      {children}
      {ordered.map((route) => (
        <RouteLayer
          // Remount on selection change so layers move to the right pane.
          key={`${route.id}-${route.id === selectedId}`}
          route={route}
          selected={route.id === selectedId}
          recommended={route.id === plan.recommendation.route_id}
          onSelect={onSelect}
        />
      ))}
      {plan && (
        <>
          <Marker position={[plan.origin.lat, plan.origin.lon]} icon={ORIGIN_ICON} title={plan.origin.label} />
          <Marker
            position={[plan.destination.lat, plan.destination.lon]}
            icon={DESTINATION_ICON}
            title={plan.destination.label}
          />
        </>
      )}
      <FitToPlan plan={plan} />
      <FlyToCheckpoint checkpoint={focusedCheckpoint} />
    </MapContainer>
  );
}
