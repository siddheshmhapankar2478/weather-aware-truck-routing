import { Marker, Tooltip } from "react-leaflet";
import L from "leaflet";

const TRUCK_ICON = L.divIcon({
  className: "truck-marker",
  html: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="6" width="14" height="10" rx="1"/><path d="M15 9h4l3 3v4h-7z"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/></svg>',
  iconSize: [30, 30],
  iconAnchor: [15, 15],
});

export default function TruckMarker({ routeId, position }) {
  return (
    <Marker position={[position.lat, position.lon]} icon={TRUCK_ICON} zIndexOffset={1000} keyboard={false}>
      <Tooltip direction="right" offset={[14, 0]}>
        Route {routeId}: {position.status}
        {position.status === "En route" && ` · mile ${Math.round(position.mile)}`}
      </Tooltip>
    </Marker>
  );
}
