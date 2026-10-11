import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import CameraCard from "./CameraCard";
import { useBackend } from "../context/BackendContext";
import { snapshotUrl } from "../lib/api";
import { hostOf } from "../lib/streamUrl";

const THUMBNAIL_REFRESH_MS = 3000;

// Shared by the camera list page and the single-camera view behind its overlay.
export default function CameraList({ onDeleted }) {
  const navigate = useNavigate();
  const { cameras, detections, deleteCamera, pushToast, baseUrl } = useBackend();
  const list = Object.values(cameras);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setTick((n) => n + 1), THUMBNAIL_REFRESH_MS);
    return () => clearInterval(timer);
  }, []);

  async function handleDelete(id, name) {
    if (!window.confirm(`Remove "${name}"? Its historical events/alerts are kept.`)) return;
    try {
      await deleteCamera(id);
      if (onDeleted) onDeleted(id);
    } catch (e) {
      pushToast("Delete failed", e.message, "medium");
    }
  }

  return (
    <div className="flex flex-col gap-2.5">
      {list.length === 0 && (
        <div className="text-center text-[#9c9c9c] text-[14px] py-16 border border-dashed border-brand-border rounded-[5px]">
          No cameras registered yet — click "Add new Camera" above.
        </div>
      )}
      {list.map((cam) => (
        <CameraCard
          key={cam.camera_id}
          name={cam.name}
          ip={hostOf(cam.rtsp_url)}
          location={cam.location || "—"}
          status={(cam.status || "offline").replace(/^./, (c) => c.toUpperCase())}
          error={cam.last_error}
          thumbnail={snapshotUrl(baseUrl, cam.camera_id, 320, tick)}
          detections={detections[cam.camera_id]}
          onView={() => navigate(`/cameras/${cam.camera_id}`)}
          onDelete={() => handleDelete(cam.camera_id, cam.name)}
        />
      ))}
    </div>
  );
}
