import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import CameraCard from "../components/CameraCard";
import { useBackend } from "../context/BackendContext";

function hostOf(url) {
  try {
    return new URL((url || "").replace(/^rtsp/, "http")).host;
  } catch (e) {
    return url || "—";
  }
}

function loadSnapMap() {
  try {
    return JSON.parse(localStorage.getItem("nexgen_snapshot_urls") || "{}");
  } catch (e) {
    return {};
  }
}

export default function CameraLiveView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { cameras, detections, cameraAction, deleteCamera, pushToast } = useBackend();
  const list = Object.values(cameras);
  const camera = cameras[id];

  const [snapMap, setSnapMap] = useState(loadSnapMap);
  const [snapInput, setSnapInput] = useState(snapMap[id] || "");
  const [tick, setTick] = useState(0);
  const [now, setNow] = useState(new Date());

  useEffect(() => setSnapInput(snapMap[id] || ""), [id, snapMap]);

  useEffect(() => {
    const clock = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(clock);
  }, []);

  const snapUrl = snapMap[id];
  useEffect(() => {
    if (!snapUrl) return;
    const t = setInterval(() => setTick((n) => n + 1), 2000);
    return () => clearInterval(t);
  }, [snapUrl]);

  const imgSrc = useMemo(() => {
    if (!snapUrl) return null;
    return snapUrl + (snapUrl.includes("?") ? "&" : "?") + "_=" + tick;
  }, [snapUrl, tick]);

  function saveSnap() {
    const next = { ...snapMap };
    if (snapInput.trim()) next[id] = snapInput.trim();
    else delete next[id];
    localStorage.setItem("nexgen_snapshot_urls", JSON.stringify(next));
    setSnapMap(next);
  }

  async function handleDelete(camId, name) {
    if (!window.confirm(`Remove "${name}"? Its historical events/alerts are kept.`)) return;
    try {
      await deleteCamera(camId);
      navigate("/cameras");
    } catch (e) {
      pushToast("Delete failed", e.message, "medium");
    }
  }

  const det = detections[id] || { faces: [], weapons: [] };

  return (
    <div className="relative">
      <DashboardLayout title="Live Cameras" actionLabel="Add new Camera" onAction={() => navigate("/camera-management")}>
        <div className="flex flex-col gap-2.5">
          {list.map((cam) => (
            <CameraCard
              key={cam.camera_id}
              name={cam.name}
              ip={hostOf(cam.rtsp_url)}
              location={cam.location || "—"}
              status={(cam.status || "offline").replace(/^./, (c) => c.toUpperCase())}
              detections={detections[cam.camera_id]}
              onView={() => navigate(`/cameras/${cam.camera_id}`)}
              onDelete={() => handleDelete(cam.camera_id, cam.name)}
            />
          ))}
        </div>
      </DashboardLayout>

      {/* Live video overlay */}
      <div className="fixed inset-y-2 right-2 w-[calc(100%-280px)] max-w-[1128px] bg-[#046587] rounded-[10px] border border-[#0d88c7] overflow-hidden">
        <div className="bg-black/[0.77] h-[63px] flex items-center justify-between px-9">
          <div className="flex items-center gap-1.5">
            <p className="text-white text-[16px] font-semibold">{camera ? camera.name : "Camera not found"}</p>
            {camera && (camera.status || "").toLowerCase() === "online" && <p className="text-[#0ff266] text-[13px]">Live</p>}
          </div>
          <div className="flex items-center gap-6 text-white text-[14px] font-medium">
            <span>{now.toLocaleDateString()}</span>
            <span>{now.toLocaleTimeString()}</span>
            <button onClick={() => navigate("/cameras")} className="text-white/80 hover:text-white ml-4">
              ✕
            </button>
          </div>
        </div>

        <div className="h-[calc(100%-63px)] bg-gradient-to-b from-[#046587] to-[#02364a] relative flex items-center justify-center overflow-hidden">
          {imgSrc ? (
            <img src={imgSrc} alt="" className="absolute inset-0 w-full h-full object-cover" onError={(e) => { e.currentTarget.style.display = "none"; }} />
          ) : (
            <p className="text-white/40 text-[14px] px-10 text-center">
              No live preview URL configured for this camera.
              <br />
              Add one below (e.g. a Hikvision ISAPI snapshot URL).
            </p>
          )}

          {/* detection chips */}
          <div className="absolute top-4 left-4 flex flex-wrap gap-1.5 max-w-[70%]">
            {det.faces.map((f, i) => (
              <span
                key={`f${i}`}
                className={`text-[11px] font-semibold rounded px-2 py-1 ${
                  f.identity_name && f.identity_name !== "unknown" ? "bg-[#3c9e62] text-white" : "bg-[#e0a020] text-white"
                }`}
              >
                👤 {f.identity_name || "unknown"}
              </span>
            ))}
            {det.weapons.map((w, i) => (
              <span key={`w${i}`} className="text-[11px] font-bold rounded px-2 py-1 bg-brand-red text-white">
                ⚠ {w.label || w.class || "weapon"}
              </span>
            ))}
          </div>

          {/* right-side floating tool icons */}
          <div className="absolute right-6 top-10 flex flex-col gap-4">
            <button
              className="bg-[rgba(46,46,46,0.67)] size-[50px] rounded-full flex items-center justify-center text-white text-[18px]"
              onClick={() => camera && cameraAction(camera.camera_id, "restart")}
              title="Restart pipeline"
            >
              ⚙
            </button>
            <button className="bg-[rgba(46,46,46,0.67)] size-[50px] rounded-full flex items-center justify-center text-white text-[18px]" title="Schedule">
              📅
            </button>
            <button className="bg-[rgba(46,46,46,0.67)] size-[50px] rounded-full flex items-center justify-center text-white text-[18px]" title="Location">
              📍
            </button>
            <button className="bg-[rgba(46,46,46,0.67)] size-[50px] rounded-full flex items-center justify-center text-white text-[18px]" title="Zoom">
              🔍
            </button>
          </div>

          {/* preview URL config */}
          <div className="absolute bottom-4 left-4 right-4 bg-black/60 rounded-lg p-3 flex flex-col gap-2 max-w-[560px]">
            <span className="text-white/70 text-[11px]">
              Live-preview URL (e.g. Hikvision ISAPI snapshot: <code>http://user:pass@ip/ISAPI/Streaming/channels/101/picture</code>)
            </span>
            <div className="flex gap-2">
              <input
                value={snapInput}
                onChange={(e) => setSnapInput(e.target.value)}
                placeholder="http://user:pass@camera-ip/ISAPI/Streaming/channels/101/picture"
                className="flex-1 bg-black/40 border border-white/20 rounded px-2 py-1.5 text-white text-[12px] outline-none"
              />
              <button onClick={saveSnap} className="bg-white/20 hover:bg-white/30 text-white text-[12px] rounded px-3">
                Save
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
