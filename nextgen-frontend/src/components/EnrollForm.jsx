import { useEffect, useRef, useState } from "react";
import { onboarding } from "../assets/figmaAssets";
import { useBackend } from "../context/BackendContext";
import { snapshotUrl } from "../lib/api";

const MAX_PHOTOS = 10;
// Photos are downscaled in the browser; faces only need a few hundred pixels
// and a phone photo would otherwise be a multi-megabyte JSON body.
const MAX_SIDE = 1280;

function toJpegDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, MAX_SIDE / Math.max(img.width, img.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL("image/jpeg", 0.9));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error(`Could not read ${blob.name || "image"}`));
    };
    img.src = url;
  });
}

// Browsers only expose the camera to pages on HTTPS or localhost. Elsewhere
// (a phone opening the dashboard by IP) the file input's `capture` attribute
// still opens the native camera, so that is the fallback.
const canUseLiveCamera = () => Boolean(window.isSecureContext && navigator.mediaDevices?.getUserMedia);

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-3" onClick={onClose}>
      <div className="bg-white rounded-[10px] w-full max-w-[640px] max-h-full overflow-auto p-4 sm:p-5 flex flex-col gap-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <p className="text-brand-navy text-[16px] font-semibold">{title}</p>
          <button type="button" onClick={onClose} className="text-[#6a6888] text-[18px] px-2">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function DeviceCameraModal({ onCapture, onClose }) {
  const videoRef = useRef(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let stream;
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "user", width: { ideal: 1280 } }, audio: false })
      .then((s) => {
        if (cancelled) {
          s.getTracks().forEach((t) => t.stop());
          return;
        }
        stream = s;
        if (videoRef.current) videoRef.current.srcObject = s;
      })
      .catch((e) => setError(e.name === "NotAllowedError" ? "Camera permission was denied." : `Could not open the camera (${e.message}).`));
    return () => {
      cancelled = true;
      if (stream) stream.getTracks().forEach((t) => t.stop());
    };
  }, []);

  function capture() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    onCapture(canvas.toDataURL("image/jpeg", 0.9));
  }

  return (
    <Modal title="Take a photo with this device" onClose={onClose}>
      {error ? (
        <p className="text-brand-red text-[13px] py-6 text-center">{error}</p>
      ) : (
        <video ref={videoRef} autoPlay playsInline muted className="w-full rounded-[5px] bg-black aspect-video object-contain" />
      )}
      <div className="flex gap-3 justify-end">
        <button type="button" onClick={onClose} className="border border-brand-border text-[#4f4b61] text-[13px] rounded-[5px] h-[40px] px-4">
          Done
        </button>
        <button type="button" onClick={capture} disabled={Boolean(error)} className="bg-brand-red disabled:opacity-50 text-white font-semibold text-[13px] rounded-[5px] h-[40px] px-5">
          Capture
        </button>
      </div>
    </Modal>
  );
}

function ConnectedCameraModal({ cameras, onCapture, onClose }) {
  const { baseUrl, pushToast } = useBackend();
  const [cameraId, setCameraId] = useState(cameras[0]?.camera_id || "");
  const [tick, setTick] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => setTick((n) => n + 1), 700);
    return () => clearInterval(timer);
  }, []);

  async function capture() {
    setBusy(true);
    try {
      // Full resolution and without detection boxes drawn over the face.
      const res = await fetch(snapshotUrl(baseUrl, cameraId, 0, Date.now(), false));
      if (!res.ok) throw new Error("The camera has no frame yet.");
      onCapture(await toJpegDataUrl(await res.blob()));
    } catch (e) {
      pushToast("Capture failed", e.message, "medium");
    }
    setBusy(false);
  }

  return (
    <Modal title="Capture from a connected camera" onClose={onClose}>
      {cameras.length === 0 ? (
        <p className="text-[#6a6888] text-[13px] py-6 text-center">No camera is online right now.</p>
      ) : (
        <>
          <select value={cameraId} onChange={(e) => setCameraId(e.target.value)} className="bg-brand-field border border-brand-border rounded-[5px] h-[42px] px-3 text-[13px]">
            {cameras.map((c) => (
              <option key={c.camera_id} value={c.camera_id}>
                {c.name}
              </option>
            ))}
          </select>
          <img src={snapshotUrl(baseUrl, cameraId, 640, tick, false)} alt="" className="w-full rounded-[5px] bg-black aspect-video object-contain" />
          <p className="text-[11.5px] text-brand-gray">Have the person face this camera, then capture. Take a few from slightly different angles.</p>
        </>
      )}
      <div className="flex gap-3 justify-end">
        <button type="button" onClick={onClose} className="border border-brand-border text-[#4f4b61] text-[13px] rounded-[5px] h-[40px] px-4">
          Done
        </button>
        <button type="button" onClick={capture} disabled={busy || !cameraId} className="bg-brand-red disabled:opacity-50 text-white font-semibold text-[13px] rounded-[5px] h-[40px] px-5">
          {busy ? "Capturing…" : "Capture"}
        </button>
      </div>
    </Modal>
  );
}

function SourceButton({ children, onClick, as = "button" }) {
  const Tag = as;
  return (
    <Tag
      type={as === "button" ? "button" : undefined}
      onClick={onClick}
      className="bg-white border border-brand-border rounded-[5px] h-[46px] flex items-center gap-2 px-4 cursor-pointer text-[#4f4b61] text-[12.5px] font-semibold"
    >
      {children}
    </Tag>
  );
}

export default function EnrollForm({ onEnrolled }) {
  const { enrollIdentity, pushToast, cameras } = useBackend();
  const [name, setName] = useState("");
  const [photos, setPhotos] = useState([]);
  const [saving, setSaving] = useState(false);
  const [modal, setModal] = useState(null);

  const onlineCameras = Object.values(cameras).filter((c) => (c.status || "").toLowerCase() === "online");
  const full = photos.length >= MAX_PHOTOS;

  function addPhoto(dataUrl) {
    setPhotos((prev) => (prev.length >= MAX_PHOTOS ? prev : [...prev, dataUrl]));
  }

  async function addFiles(fileList) {
    const files = Array.from(fileList || []).slice(0, MAX_PHOTOS - photos.length);
    try {
      const urls = await Promise.all(files.map(toJpegDataUrl));
      setPhotos((prev) => [...prev, ...urls].slice(0, MAX_PHOTOS));
    } catch (e) {
      pushToast("Could not add photo", e.message, "medium");
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim() || photos.length === 0) {
      pushToast("Missing details", "Enter a name and add at least one photo.", "medium");
      return;
    }
    setSaving(true);
    try {
      const result = await enrollIdentity(name.trim(), photos);
      pushToast("Face enrolled", `${result.name}: ${result.photos_used} of ${result.photos_received} photo(s) used.`, "medium");
      setName("");
      setPhotos([]);
      if (onEnrolled) onEnrolled(result);
    } catch (err) {
      pushToast("Enrollment failed", err.message, "high");
    }
    setSaving(false);
  }

  const fileInput = (extra) => (
    <input
      type="file"
      accept="image/*"
      className="hidden"
      onChange={(e) => {
        addFiles(e.target.files);
        e.target.value = "";
      }}
      {...extra}
    />
  );

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <p className="text-[12px] text-[#6a6888] leading-relaxed bg-[#f4f3fa] rounded-[5px] px-4 py-3">
        Add 3–5 clear photos of one person (front, slight left, slight right). Each photo should show only that person.
        Running cameras start recognising them immediately.
      </p>

      <div className="flex flex-col gap-3">
        <label className="text-brand-navy text-[16px] font-medium">Full name</label>
        <div className="bg-brand-field border border-brand-border rounded-[5px] h-[52px] flex items-center px-5">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter full name"
            maxLength={64}
            className="bg-transparent outline-none flex-1 min-w-0 text-[14px] placeholder:text-[#c6c6c6]"
          />
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <label className="text-brand-navy text-[16px] font-medium">
          Photos ({photos.length}/{MAX_PHOTOS})
        </label>

        {photos.length > 0 && (
          <div className="flex flex-wrap gap-3">
            {photos.map((src, i) => (
              <div key={i} className="relative size-[72px] rounded-[5px] overflow-hidden border border-brand-border">
                <img src={src} alt="" className="w-full h-full object-cover" />
                <button
                  type="button"
                  onClick={() => setPhotos((prev) => prev.filter((_, j) => j !== i))}
                  className="absolute top-0 right-0 bg-black/60 text-white text-[11px] w-5 h-5 leading-5"
                  title="Remove photo"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}

        {!full && (
          <div className="flex flex-wrap gap-2">
            {canUseLiveCamera() ? (
              <SourceButton onClick={() => setModal("device")}>📷 This device's camera</SourceButton>
            ) : (
              <SourceButton as="label">
                📷 This device's camera
                {fileInput({ capture: "user" })}
              </SourceButton>
            )}
            <SourceButton onClick={() => setModal("connected")}>🎥 A connected camera</SourceButton>
            <SourceButton as="label">
              <img src={onboarding.uploadFile} alt="" className="w-5 h-5" />
              Upload photos
              {fileInput({ multiple: true })}
            </SourceButton>
          </div>
        )}
      </div>

      <button
        type="submit"
        disabled={saving}
        className="bg-brand-red disabled:opacity-60 text-white font-bold text-[16px] rounded-[5px] h-[52px] w-full sm:w-[200px]"
      >
        {saving ? "Enrolling…" : "Enroll face"}
      </button>

      {modal === "device" && <DeviceCameraModal onCapture={addPhoto} onClose={() => setModal(null)} />}
      {modal === "connected" && <ConnectedCameraModal cameras={onlineCameras} onCapture={addPhoto} onClose={() => setModal(null)} />}
    </form>
  );
}
