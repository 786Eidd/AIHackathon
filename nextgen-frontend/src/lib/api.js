// Thin REST client for the NexGen backend (app/api/*.py). No auth — the
// backend ships without any (see its README's Security Notes), so this is
// just fetch + JSON handling, not a token/session layer.

export function apiUrl(base, path) {
  return base.replace(/\/+$/, "") + path;
}

export function wsUrl(base) {
  const u = new URL(base);
  const scheme = u.protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${u.host}/api/v1/ws/live`;
}

// Snapshot/clip references are absolute (OSS signed URL) or relative to the
// API origin (locally stored artifacts).
export function mediaUrl(base, ref) {
  if (!ref) return null;
  return ref.startsWith("/") ? apiUrl(base, ref) : ref;
}

export function snapshotUrl(base, cameraId, width = 0, cacheKey = 0, overlay = true) {
  return apiUrl(base, `/api/v1/cameras/${cameraId}/snapshot.jpg?width=${width}&overlay=${overlay}&_=${cacheKey}`);
}

export function streamUrl(base, cameraId, width = 960, fps = 10) {
  return apiUrl(base, `/api/v1/cameras/${cameraId}/stream.mjpg?width=${width}&fps=${fps}`);
}

function describeError(data, res) {
  const detail = data && data.detail;
  if (typeof detail === "string") return detail;
  // FastAPI validation errors arrive as a list of {loc, msg}.
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  return res.statusText || `HTTP ${res.status}`;
}

async function req(base, path, opts = {}) {
  const res = await fetch(apiUrl(base, path), {
    headers: opts.body ? { "Content-Type": "application/json" } : undefined,
    ...opts,
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch (e) {
    data = { raw: text };
  }
  if (!res.ok) {
    const err = new Error(describeError(data, res));
    err.data = data;
    err.status = res.status;
    throw err;
  }
  return data;
}

export const api = {
  health: (base) => req(base, "/api/v1/health"),

  listCameras: (base) => req(base, "/api/v1/cameras"),
  cameraStatus: (base) => req(base, "/api/v1/cameras/status"),
  createCamera: (base, body) => req(base, "/api/v1/cameras", { method: "POST", body: JSON.stringify(body) }),
  updateCamera: (base, id, body) => req(base, `/api/v1/cameras/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteCamera: (base, id) => req(base, `/api/v1/cameras/${id}`, { method: "DELETE" }),
  cameraAction: (base, id, action) => req(base, `/api/v1/cameras/${id}/${action}`, { method: "POST" }),

  listAlerts: (base, limit = 100) => req(base, `/api/v1/alerts?limit=${limit}`),
  ackAlert: (base, id) => req(base, `/api/v1/alerts/${id}/ack`, { method: "POST" }),

  listEvents: (base, limit = 100, cameraId) =>
    req(base, `/api/v1/events?limit=${limit}${cameraId ? `&camera_id=${encodeURIComponent(cameraId)}` : ""}`),
  getEvent: (base, id) => req(base, `/api/v1/events/${id}`),

  listIdentities: (base) => req(base, "/api/v1/identities"),
  reloadIdentities: (base) => req(base, "/api/v1/identities/reload", { method: "POST" }),
  enrollIdentity: (base, name, images) => req(base, "/api/v1/identities", { method: "POST", body: JSON.stringify({ name, images }) }),
  deleteIdentity: (base, name) => req(base, `/api/v1/identities/${encodeURIComponent(name)}`, { method: "DELETE" }),

  discoveryDevices: (base) => req(base, "/api/v1/discovery/devices"),
  discoveryScan: (base) => req(base, "/api/v1/discovery/scan", { method: "POST" }),
  discoveryConnect: (base, body) => req(base, "/api/v1/discovery/connect", { method: "POST", body: JSON.stringify(body) }),

  panic: (base, note) => req(base, "/api/v1/panic", { method: "POST", body: JSON.stringify({ note: note || null }) }),

  getSite: (base) => req(base, "/api/v1/site"),
  saveSite: (base, body) => req(base, "/api/v1/site", { method: "PUT", body: JSON.stringify(body) }),

  chat: (base, body) => req(base, "/api/v1/chat", { method: "POST", body: JSON.stringify(body) }),
};
