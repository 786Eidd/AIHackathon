import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, wsUrl } from "../lib/api";

// On the appliance the backend serves this dashboard, so the API is simply
// the page's own origin. Under the Vite dev server it is port 8000 on the
// same host, which also keeps a phone on the LAN pointed at the right place.
const DEV_PORTS = ["5173", "4173"];
const DEFAULT_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (DEV_PORTS.includes(window.location.port)
    ? `${window.location.protocol}//${window.location.hostname || "localhost"}:8000`
    : window.location.origin);

// Detection chips disappear this long after the last sighting.
const DETECTION_TTL_MS = 4000;
const BackendContext = createContext(null);

export function BackendProvider({ children }) {
  const [baseUrl, setBaseUrlState] = useState(() => localStorage.getItem("nexgen_base_url") || DEFAULT_BASE);
  const [connected, setConnected] = useState(false);
  const [health, setHealth] = useState(null);
  const [cameras, setCameras] = useState({});
  const [detections, setDetections] = useState({});
  const [alerts, setAlerts] = useState({});
  const [events, setEvents] = useState([]);
  const [identities, setIdentities] = useState([]);
  const [toasts, setToasts] = useState([]);
  const wsRef = useRef(null);
  const retryRef = useRef(null);

  const pushToast = useCallback((title, message, level = "medium") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, title, message, level }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
  }, []);

  const setBaseUrl = useCallback((url) => {
    const clean = (url || DEFAULT_BASE).trim().replace(/\/+$/, "");
    localStorage.setItem("nexgen_base_url", clean);
    setBaseUrlState(clean);
  }, []);

  const refreshCameras = useCallback(async () => {
    try {
      const data = await api.listCameras(baseUrl);
      // Rebuilt from the response so cameras deleted elsewhere disappear;
      // only the polled pipeline telemetry is carried over.
      setCameras((prev) => {
        const next = {};
        (data.cameras || []).forEach((c) => {
          next[c.camera_id] = { ...c, pipeline: prev[c.camera_id]?.pipeline };
        });
        return next;
      });
    } catch (e) {
      /* backend unreachable this cycle — leave state as-is */
    }
  }, [baseUrl]);

  const pollStatus = useCallback(async () => {
    try {
      const data = await api.cameraStatus(baseUrl);
      setCameras((prev) => {
        const next = { ...prev };
        (data.pipelines || []).forEach((p) => {
          const id = p.camera_id || p.id;
          if (id && next[id]) next[id] = { ...next[id], pipeline: p };
        });
        return next;
      });
    } catch (e) {}
  }, [baseUrl]);

  const refreshAlerts = useCallback(async () => {
    try {
      const data = await api.listAlerts(baseUrl);
      const map = {};
      (data.alerts || []).forEach((a) => {
        map[a.alert_id] = a;
      });
      setAlerts(map);
    } catch (e) {}
  }, [baseUrl]);

  const refreshEvents = useCallback(async () => {
    try {
      const data = await api.listEvents(baseUrl);
      setEvents(data.events || []);
    } catch (e) {}
  }, [baseUrl]);

  const refreshIdentities = useCallback(async () => {
    try {
      const data = await api.listIdentities(baseUrl);
      setIdentities(data.identities || []);
    } catch (e) {}
  }, [baseUrl]);

  const reloadIdentities = useCallback(async () => {
    const data = await api.reloadIdentities(baseUrl);
    setIdentities(data.identities || []);
    pushToast("Identities reloaded", `${data.identity_count ?? (data.identities || []).length} identities loaded.`, "medium");
    return data;
  }, [baseUrl, pushToast]);

  const enrollIdentity = useCallback(
    async (name, images) => {
      const data = await api.enrollIdentity(baseUrl, name, images);
      setIdentities(data.identities || []);
      return data;
    },
    [baseUrl]
  );

  const deleteIdentity = useCallback(
    async (name) => {
      const data = await api.deleteIdentity(baseUrl, name);
      setIdentities(data.identities || []);
      return data;
    },
    [baseUrl]
  );

  const createCamera = useCallback(
    async (body) => {
      const data = await api.createCamera(baseUrl, body);
      if (data.warning) pushToast("Added with a warning", data.warning, "medium");
      await refreshCameras();
      return data;
    },
    [baseUrl, refreshCameras, pushToast]
  );

  const updateCamera = useCallback(
    async (id, body) => {
      const data = await api.updateCamera(baseUrl, id, body);
      await refreshCameras();
      return data;
    },
    [baseUrl, refreshCameras]
  );

  const deleteCamera = useCallback(
    async (id) => {
      await api.deleteCamera(baseUrl, id);
      setCameras((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      setDetections((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    },
    [baseUrl]
  );

  const cameraAction = useCallback(
    async (id, action) => {
      try {
        await api.cameraAction(baseUrl, id, action);
      } catch (e) {
        pushToast("Action failed", e.message, "medium");
      }
      await refreshCameras();
    },
    [baseUrl, refreshCameras, pushToast]
  );

  const ackAlert = useCallback(
    async (id) => {
      await api.ackAlert(baseUrl, id);
      setAlerts((prev) => ({ ...prev, [id]: { ...(prev[id] || {}), acknowledged: true } }));
    },
    [baseUrl]
  );

  const raisePanic = useCallback(
    async (note) => {
      const data = await api.panic(baseUrl, note);
      // Shown at once here; other dashboards get it over the WebSocket.
      setAlerts((prev) => ({ ...prev, [data.alert.alert_id]: data.alert }));
      refreshCameras();
      return data;
    },
    [baseUrl, refreshCameras]
  );

  const sendChat = useCallback(
    async (question, cameraId, minutes) => {
      return api.chat(baseUrl, { question, camera_id: cameraId || null, minutes: minutes || 60 });
    },
    [baseUrl]
  );

  // Armed reflects the backend: a camera is "enabled" until it is stopped.
  const armed = Object.values(cameras).some((c) => c.enabled);

  const toggleArm = useCallback(async () => {
    const next = !armed;
    const ids = Object.keys(cameras);
    for (const id of ids) {
      try {
        await api.cameraAction(baseUrl, id, next ? "start" : "stop");
      } catch (e) {}
    }
    pushToast(
      next ? "System armed" : "System unarmed",
      next ? "Starting every registered camera." : "Stopping every running camera.",
      "medium"
    );
    await refreshCameras();
  }, [armed, cameras, baseUrl, refreshCameras, pushToast]);

  const connect = useCallback(
    async (url) => {
      if (url) setBaseUrl(url);
      const target = url ? url.trim().replace(/\/+$/, "") : baseUrl;
      try {
        const h = await api.health(target);
        setHealth(h);
        setConnected(true);
        return { ok: true, health: h };
      } catch (e) {
        setConnected(false);
        return { ok: false, error: e };
      }
    },
    [baseUrl, setBaseUrl]
  );

  // WebSocket: open/reopen whenever baseUrl changes, auto-retry on drop.
  useEffect(() => {
    let cancelled = false;

    function patchEvent(eventId, changes) {
      setEvents((prev) => prev.map((e) => (e.event_id === eventId ? { ...e, ...changes } : e)));
    }

    function handleMessage(msg) {
      switch (msg.type) {
        case "snapshot":
          setCameras((prev) => {
            const next = { ...prev };
            (msg.cameras || []).forEach((c) => {
              next[c.camera_id] = { ...(next[c.camera_id] || {}), ...c };
            });
            return next;
          });
          if (msg.recent_alerts) {
            setAlerts((prev) => {
              const next = { ...prev };
              msg.recent_alerts.forEach((a) => {
                next[a.alert_id] = a;
              });
              return next;
            });
          }
          break;
        case "detection":
          setDetections((prev) => ({
            ...prev,
            [msg.camera_id]: { faces: msg.faces || [], weapons: msg.weapons || [], at: msg.observed_at, receivedAt: Date.now() },
          }));
          break;
        case "camera.status":
          setCameras((prev) =>
            prev[msg.camera_id]
              ? { ...prev, [msg.camera_id]: { ...prev[msg.camera_id], status: msg.status, last_error: msg.error } }
              : prev
          );
          break;
        case "event.opened":
          setEvents((prev) => [{ ...msg.event, camera_id: msg.camera_id }, ...prev].slice(0, 200));
          break;
        case "event.closed":
          patchEvent(msg.event.event_id, { ...msg.event, status: "closed" });
          break;
        case "event.clip_ready":
          patchEvent(msg.event_id, { clip_key: msg.clip_key, clip_url: msg.clip_url });
          break;
        case "event.analysis":
          patchEvent(msg.event_id, { summary: msg.summary });
          break;
        case "alert.updated":
          setAlerts((prev) => (prev[msg.alert_id] ? { ...prev, [msg.alert_id]: { ...prev[msg.alert_id], message: msg.message } } : prev));
          break;
        case "alert": {
          setAlerts((prev) => ({ ...prev, [msg.alert.alert_id]: msg.alert }));
          const p = (msg.alert.priority || "").toLowerCase();
          pushToast(msg.alert.title, msg.alert.message, p === "high" ? "high" : "medium");
          break;
        }
        case "alert.acknowledged":
          setAlerts((prev) => (prev[msg.alert_id] ? { ...prev, [msg.alert_id]: { ...prev[msg.alert_id], acknowledged: true } } : prev));
          break;
        default:
          break;
      }
    }

    function openSocket() {
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch (e) {}
      }
      let socket;
      try {
        socket = new WebSocket(wsUrl(baseUrl));
      } catch (e) {
        return;
      }
      wsRef.current = socket;
      socket.onopen = () => {
        if (!cancelled) setConnected(true);
        clearTimeout(retryRef.current);
      };
      socket.onclose = () => {
        if (!cancelled) {
          setConnected(false);
          retryRef.current = setTimeout(openSocket, 4000);
        }
      };
      socket.onerror = () => {};
      socket.onmessage = (evt) => {
        let msg;
        try {
          msg = JSON.parse(evt.data);
        } catch (e) {
          return;
        }
        handleMessage(msg);
      };
    }

    openSocket();
    return () => {
      cancelled = true;
      clearTimeout(retryRef.current);
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch (e) {}
      }
    };
  }, [baseUrl, pushToast]);

  // Drop detection chips once the subject has not been seen for a moment;
  // the backend only publishes frames that contain something.
  useEffect(() => {
    const timer = setInterval(() => {
      const cutoff = Date.now() - DETECTION_TTL_MS;
      setDetections((prev) => {
        const stale = Object.keys(prev).filter((id) => (prev[id].receivedAt || 0) < cutoff);
        if (!stale.length) return prev;
        const next = { ...prev };
        stale.forEach((id) => delete next[id]);
        return next;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Initial + periodic REST refresh.
  useEffect(() => {
    connect();
    refreshCameras();
    refreshAlerts();
    refreshEvents();
    refreshIdentities();
    const t1 = setInterval(refreshCameras, 15000);
    const t2 = setInterval(pollStatus, 5000);
    return () => {
      clearInterval(t1);
      clearInterval(t2);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl]);

  const value = {
    baseUrl,
    setBaseUrl,
    connect,
    connected,
    health,
    cameras,
    detections,
    alerts,
    events,
    identities,
    armed,
    refreshCameras,
    refreshAlerts,
    refreshEvents,
    refreshIdentities,
    reloadIdentities,
    enrollIdentity,
    deleteIdentity,
    createCamera,
    updateCamera,
    deleteCamera,
    cameraAction,
    ackAlert,
    raisePanic,
    sendChat,
    toggleArm,
    toasts,
    pushToast,
  };

  return <BackendContext.Provider value={value}>{children}</BackendContext.Provider>;
}

export function useBackend() {
  const ctx = useContext(BackendContext);
  if (!ctx) throw new Error("useBackend must be used within a <BackendProvider>");
  return ctx;
}
