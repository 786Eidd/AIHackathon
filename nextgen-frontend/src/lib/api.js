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
    const err = new Error(data.detail || res.statusText || `HTTP ${res.status}`);
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

  chat: (base, body) => req(base, "/api/v1/chat", { method: "POST", body: JSON.stringify(body) }),
};
