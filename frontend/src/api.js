const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Can't reach the server. Check your connection and try again.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}

export const searchPlaces = (query, signal) =>
  request(`/api/geocode?q=${encodeURIComponent(query)}`, { signal }).then((d) => d.results);

export const planTrip = (payload) => request("/api/plan", { method: "POST", body: JSON.stringify(payload) });
