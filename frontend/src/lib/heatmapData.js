/** Per-hour score arrays (0–4) for one metric. "risk" is the worst of the three. */
export function metricFrames(data, metric) {
  if (!data) return null;
  const { wind, rain, snow } = data.scores;
  const scale = data.scale;
  return data.hours.map((_, h) => {
    const frame = new Float32Array(data.points.length);
    for (let i = 0; i < frame.length; i++) {
      frame[i] =
        metric === "risk"
          ? Math.max(wind[h][i], rain[h][i], snow[h][i]) / scale
          : data.scores[metric][h][i] / scale;
    }
    return frame;
  });
}

/** Where the truck is on `route` at `time` (Date), using checkpoint ETAs. */
export function truckPosition(route, departureIso, time) {
  const elapsed = (time - new Date(departureIso)) / 1000;
  const cps = route.checkpoints;
  if (elapsed <= 0) return { lat: cps[0].lat, lon: cps[0].lon, mile: 0, status: "Not departed" };
  const last = cps[cps.length - 1];
  if (elapsed >= last.elapsed_s) return { lat: last.lat, lon: last.lon, mile: last.mile, status: "Arrived" };

  let k = 0;
  while (cps[k + 1].elapsed_s < elapsed) k++;
  const a = cps[k];
  const b = cps[k + 1];
  const t = (elapsed - a.elapsed_s) / (b.elapsed_s - a.elapsed_s || 1);
  return {
    lat: a.lat + (b.lat - a.lat) * t,
    lon: a.lon + (b.lon - a.lon) * t,
    mile: a.mile + (b.mile - a.mile) * t,
    status: "En route",
  };
}
