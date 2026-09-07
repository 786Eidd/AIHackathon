import { useNavigate } from "react-router-dom";
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

export default function LiveCameras() {
  const navigate = useNavigate();
  const { cameras, detections, deleteCamera, pushToast } = useBackend();
  const list = Object.values(cameras);

  async function handleDelete(id, name) {
    if (!window.confirm(`Remove "${name}"? Its historical events/alerts are kept.`)) return;
    try {
      await deleteCamera(id);
    } catch (e) {
      pushToast("Delete failed", e.message, "medium");
    }
  }

  return (
    <DashboardLayout title="Live Cameras" actionLabel="Add new Camera" onAction={() => navigate("/camera-management")}>
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
            detections={detections[cam.camera_id]}
            onView={() => navigate(`/cameras/${cam.camera_id}`)}
            onDelete={() => handleDelete(cam.camera_id, cam.name)}
          />
        ))}
      </div>
    </DashboardLayout>
  );
}
