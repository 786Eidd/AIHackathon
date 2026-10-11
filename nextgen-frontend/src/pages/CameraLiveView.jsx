import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import CameraList from "../components/CameraList";
import { DetectionChips } from "../components/CameraCard";
import { useBackend } from "../context/BackendContext";
import { streamUrl } from "../lib/api";

export default function CameraLiveView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { cameras, detections, cameraAction, baseUrl } = useBackend();
  const camera = cameras[id];

  const [now, setNow] = useState(new Date());
  // Bumped to force the <img> to reconnect after a stream error or restart.
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const clock = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(clock);
  }, []);

  const status = (camera?.status || "offline").toLowerCase();
  const streaming = camera && status !== "offline";

  // Reconnect when the camera changes or comes back from offline.
  useEffect(() => {
    setFailed(false);
    setAttempt((n) => n + 1);
  }, [id, streaming]);

  useEffect(() => {
    if (!failed) return;
    const retry = setTimeout(() => {
      setFailed(false);
      setAttempt((n) => n + 1);
    }, 3000);
    return () => clearTimeout(retry);
  }, [failed]);

  async function restart() {
    if (!camera) return;
    await cameraAction(camera.camera_id, "restart");
    setFailed(false);
    setAttempt((n) => n + 1);
  }

  return (
    <div className="relative">
      <DashboardLayout title="Live Cameras" actionLabel="Add new Camera" onAction={() => navigate("/camera-management")}>
        <CameraList onDeleted={(deletedId) => deletedId === id && navigate("/cameras")} />
      </DashboardLayout>

      {/* Live video overlay */}
      <div className="fixed inset-2 lg:left-auto lg:w-[calc(100%-280px)] lg:max-w-[1128px] bg-[#046587] rounded-[10px] border border-[#0d88c7] overflow-hidden z-20">
        <div className="bg-black/[0.77] h-[63px] flex items-center justify-between gap-3 px-4 lg:px-9">
          <div className="flex items-center gap-2 min-w-0">
            <p className="text-white text-[16px] font-semibold truncate">{camera ? camera.name : "Camera not found"}</p>
            {status === "online" && <p className="text-[#0ff266] text-[13px]">● Live</p>}
            {camera && status !== "online" && <p className="text-[#ffb347] text-[13px] capitalize">{status}</p>}
          </div>
          <div className="flex items-center gap-3 sm:gap-6 text-white text-[14px] font-medium shrink-0">
            <span className="hidden md:inline">{now.toLocaleDateString()}</span>
            <span className="hidden sm:inline">{now.toLocaleTimeString()}</span>
            <button onClick={restart} className="text-white/80 hover:text-white text-[13px] underline" title="Restart this camera's pipeline">
              Restart
            </button>
            <button onClick={() => navigate("/cameras")} className="text-white/80 hover:text-white">
              ✕
            </button>
          </div>
        </div>

        <div className="h-[calc(100%-63px)] bg-black relative flex items-center justify-center overflow-hidden">
          {streaming && !failed ? (
            <img
              key={attempt}
              src={`${streamUrl(baseUrl, id)}&_=${attempt}`}
              alt={camera.name}
              className="absolute inset-0 w-full h-full object-contain"
              onError={() => setFailed(true)}
            />
          ) : (
            <p className="text-white/50 text-[14px] px-10 text-center leading-relaxed">
              {!camera
                ? "This camera no longer exists."
                : status === "offline"
                ? "This camera is stopped. Press Restart to start it."
                : "Waiting for video…"}
              {camera?.last_error && (
                <>
                  <br />
                  <span className="text-[#ff8f8f] text-[12px]">{camera.last_error}</span>
                </>
              )}
            </p>
          )}

          <div className="absolute top-4 left-4 max-w-[70%]">
            <DetectionChips detections={detections[id]} solid />
          </div>
        </div>
      </div>
    </div>
  );
}
