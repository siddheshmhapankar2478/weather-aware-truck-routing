import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import { CorridorHeatLayer } from "../lib/heatLayer";

export default function HeatmapLayer({ points, spacingMi, values }) {
  const map = useMap();
  const layerRef = useRef(null);

  useEffect(() => {
    const layer = new CorridorHeatLayer(points, { radiusMi: spacingMi * 1.15, pane: "heat" }).addTo(map);
    layerRef.current = layer;
    return () => {
      layer.remove();
      layerRef.current = null;
    };
  }, [map, points, spacingMi]);

  useEffect(() => {
    layerRef.current?.setValues(values);
  }, [values, points, spacingMi]);

  return null;
}
