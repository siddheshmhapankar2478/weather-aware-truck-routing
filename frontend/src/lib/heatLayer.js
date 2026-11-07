import L from "leaflet";
import { RISK_LEVELS } from "./risk";

/*
 * Canvas heatmap for risk scores (0–4).
 *
 * Classic heatmaps add overlapping points together, which would turn many
 * low-risk points into a fake hotspot. Here each point is drawn as a soft disc
 * and overlapping discs keep the *maximum* value (canvas "lighten" blending):
 *   red channel   = risk score (0–255)
 *   green channel = coverage, used for the alpha edge
 * The grey-scale result is then coloured with the risk palette.
 *
 * Drawing happens at half resolution and is scaled up by CSS, which keeps a
 * full redraw to a few milliseconds so the time slider stays smooth.
 */

const PADDING = 0.3; // extra canvas around the viewport so panning doesn't show gaps
const RESOLUTION = 0.5;

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** 256-colour lookup: each level keeps its own colour and blends into the next near the top of its band. */
function buildPalette() {
  const colors = RISK_LEVELS.map((l) => hexToRgb(l.color));
  const palette = new Uint8ClampedArray(256 * 3);
  for (let i = 0; i < 256; i++) {
    const score = (i / 255) * 4;
    const level = Math.min(4, Math.floor(score));
    const frac = score - level;
    const blend = level < 4 && frac > 0.75 ? (frac - 0.75) / 0.25 : 0;
    const from = colors[level];
    const to = colors[Math.min(4, level + 1)];
    for (let c = 0; c < 3; c++) palette[i * 3 + c] = from[c] + (to[c] - from[c]) * blend;
  }
  return palette;
}

const PALETTE = buildPalette();

// Low risk is drawn faint so the basemap stays readable and hazards stand out.
const LEVEL_ALPHA = [0.35, 0.7, 0.85, 0.95, 1];
const ALPHA = new Float32Array(256).map((_, i) => LEVEL_ALPHA[Math.min(4, Math.floor((i / 255) * 4))]);

export const CorridorHeatLayer = L.Layer.extend({
  options: { radiusMi: 20, opacity: 0.75, pane: "overlayPane" },

  initialize(points, options) {
    this._latlngs = points.map(([lat, lon]) => L.latLng(lat, lon));
    this._values = null;
    L.setOptions(this, options);
  },

  /** values: one score (0–4) per point. */
  setValues(values) {
    this._values = values;
    if (this._map && !this._frame) {
      this._frame = L.Util.requestAnimFrame(() => {
        this._frame = null;
        this._draw();
      });
    }
    return this;
  },

  onAdd(map) {
    this._canvas = L.DomUtil.create("canvas", "corridor-heat leaflet-zoom-animated");
    this._scratch = document.createElement("canvas");
    this.getPane().appendChild(this._canvas);
    this._reset();
  },

  onRemove() {
    L.DomUtil.remove(this._canvas);
    if (this._frame) L.Util.cancelAnimFrame(this._frame);
    this._frame = null;
  },

  getEvents() {
    return { zoomanim: this._animateZoom, moveend: this._reset, resize: this._reset };
  },

  _animateZoom(e) {
    const scale = this._map.getZoomScale(e.zoom, this._map.getZoom());
    const offset = this._map._latLngToNewLayerPoint(this._topLeft, e.zoom, e.center);
    L.DomUtil.setTransform(this._canvas, offset, scale);
  },

  _reset() {
    const map = this._map;
    const size = map.getSize();
    const pad = size.multiplyBy(PADDING).round();
    this._origin = pad; // container point (0,0) sits at this canvas offset
    this._cssSize = size.add(pad.multiplyBy(2));
    this._topLeft = map.containerPointToLatLng(pad.multiplyBy(-1));

    L.DomUtil.setPosition(this._canvas, map.containerPointToLayerPoint(pad.multiplyBy(-1)));
    this._canvas.style.width = `${this._cssSize.x}px`;
    this._canvas.style.height = `${this._cssSize.y}px`;
    this._draw();
  },

  _radiusPx() {
    // Convert the grid spacing (miles) into pixels at the current zoom.
    const map = this._map;
    const center = map.getCenter();
    const metres = this.options.radiusMi * 1609.344;
    const north = L.latLng(center.lat + metres / 111320, center.lng);
    return Math.max(4, map.latLngToContainerPoint(center).distanceTo(map.latLngToContainerPoint(north)));
  },

  _draw() {
    if (!this._map || !this._cssSize) return;
    const w = Math.max(1, Math.round(this._cssSize.x * RESOLUTION));
    const h = Math.max(1, Math.round(this._cssSize.y * RESOLUTION));
    const canvas = this._canvas;
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
      this._scratch.width = w;
      this._scratch.height = h;
    }
    const out = canvas.getContext("2d");
    out.clearRect(0, 0, w, h);
    if (!this._values) return;

    const ctx = this._scratch.getContext("2d", { willReadFrequently: true });
    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, w, h);
    ctx.globalCompositeOperation = "lighten";

    const r = this._radiusPx() * RESOLUTION;
    const map = this._map;
    for (let i = 0; i < this._latlngs.length; i++) {
      const p = map.latLngToContainerPoint(this._latlngs[i]);
      const x = (p.x + this._origin.x) * RESOLUTION;
      const y = (p.y + this._origin.y) * RESOLUTION;
      if (x < -r || y < -r || x > w + r || y > h + r) continue;
      const v = Math.round((Math.min(4, Math.max(0, this._values[i])) / 4) * 255);
      const g = ctx.createRadialGradient(x, y, 0, x, y, r);
      g.addColorStop(0, `rgb(${v},255,0)`);
      g.addColorStop(0.5, `rgb(${v},240,0)`);
      g.addColorStop(1, "rgb(0,0,0)");
      ctx.fillStyle = g;
      ctx.fillRect(x - r, y - r, r * 2, r * 2);
    }

    const image = ctx.getImageData(0, 0, w, h);
    const data = image.data;
    const maxAlpha = this.options.opacity * 255;
    for (let i = 0; i < data.length; i += 4) {
      const coverage = data[i + 1];
      if (coverage === 0) {
        data[i + 3] = 0;
        continue;
      }
      const value = data[i];
      const idx = value * 3;
      const edge = coverage / 255; // soft fade towards the corridor edge
      data[i] = PALETTE[idx];
      data[i + 1] = PALETTE[idx + 1];
      data[i + 2] = PALETTE[idx + 2];
      data[i + 3] = edge * edge * ALPHA[value] * maxAlpha;
    }
    out.putImageData(image, 0, 0);
  },
});
