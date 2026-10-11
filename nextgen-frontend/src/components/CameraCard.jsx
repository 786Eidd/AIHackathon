import { useEffect, useState } from "react";
import { icons } from "../assets/figmaAssets";

export function DetectionChips({ detections, solid = false }) {
  if (!detections) return null;
  const faces = detections.faces || [];
  const weapons = detections.weapons || [];
  if (!faces.length && !weapons.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-1">
      {faces.map((f, i) => {
        const known = f.status ? f.status === "known" : f.identity_name && f.identity_name !== "unknown";
        const tone = solid
          ? known
            ? "bg-[#3c9e62] text-white"
            : "bg-[#e0a020] text-white"
          : known
          ? "bg-[#e3f6ea] text-[#3c9e62]"
          : "bg-[#fdf3de] text-[#c98a12]";
        return (
          <span key={`f${i}`} className={`text-[10px] font-semibold rounded px-1.5 py-0.5 ${tone}`}>
            👤 {f.identity_name || "unknown"}
          </span>
        );
      })}
      {weapons.map((w, i) => (
        <span
          key={`w${i}`}
          className={`text-[10px] font-bold rounded px-1.5 py-0.5 ${
            solid ? "bg-brand-red text-white" : "bg-[rgba(255,62,62,0.15)] text-brand-red"
          }`}
        >
          ⚠ {(w.object_class || "weapon").replace(/_/g, " ")}
        </span>
      ))}
    </div>
  );
}

// Polled still image. A thumbnail per camera as MJPEG would pin one HTTP
// connection each and starve the API calls, so only the single-camera view
// streams.
function Thumbnail({ src, alt }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  if (!src || failed) return null;
  return <img src={src} alt={alt} className="w-full h-full object-cover" onError={() => setFailed(true)} />;
}

export default function CameraCard({ name, ip, location, status = "Online", error, thumbnail, detections, onView, onDelete }) {
  const isOnline = status.toLowerCase() === "online";
  return (
    <div className="bg-white rounded-[5px] shadow-[0px_0px_38px_0px_rgba(0,0,0,0.11)] min-h-[112px] w-full flex items-center px-4 sm:px-7 py-3 gap-x-6 xl:gap-x-14 gap-y-3 flex-wrap">
      <div className="flex items-center gap-3.5 w-full sm:w-auto sm:min-w-[300px] min-w-0">
        <div className="h-20 w-[112px] sm:w-[142px] rounded-[5px] overflow-hidden bg-gray-200 shrink-0">
          <Thumbnail src={isOnline ? thumbnail : null} alt={name} />
        </div>
        <div className="flex flex-col gap-0.5">
          <p className="text-brand-navy text-[16px] font-semibold">{name}</p>
          <p className="text-[#6a6888] text-[12px] font-medium">{ip}</p>
          <DetectionChips detections={detections} />
        </div>
      </div>

      <div className="flex flex-col items-center gap-1 w-[99px]">
        <p className="text-brand-navy text-[16px] font-semibold capitalize truncate w-full text-center">{location}</p>
        <p className="text-[12px] font-medium opacity-60">Location</p>
      </div>

      <div className="flex flex-col items-center gap-1 w-[140px]">
        <p className={`text-[16px] font-semibold capitalize ${isOnline ? "text-[#3c9e62]" : "text-brand-red"}`}>{status}</p>
        <p className="text-[12px] font-medium opacity-60 uppercase">current status</p>
        {error && !isOnline && (
          <p className="text-[10.5px] text-brand-red text-center leading-tight max-w-[140px] truncate" title={error}>
            {error}
          </p>
        )}
      </div>

      <div className="flex gap-3 sm:gap-5 items-center ml-auto">
        <button
          type="button"
          onClick={onView}
          className="bg-[#3c9e62] text-white text-[14px] font-medium rounded-[5px] px-3 py-1.5 flex items-center gap-1.5"
        >
          <img src={icons.viewCamera} alt="" className="w-5 h-5" />
          view camera
        </button>
        <button
          type="button"
          onClick={onDelete}
          className="bg-[rgba(255,62,62,0.2)] text-brand-red text-[14px] font-medium rounded-[5px] px-3 py-1.5 flex items-center gap-1"
        >
          <img src={icons.deleteIcon} alt="" className="w-[22px] h-[22px]" />
          delete
        </button>
      </div>
    </div>
  );
}
