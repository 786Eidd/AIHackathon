import { useEffect, useState } from "react";
import { useBackend } from "../context/BackendContext";
import { api } from "../lib/api";

const KIND_LABEL = { rtsp: "Camera / recorder", mjpeg: "Phone", webcam: "Webcam" };

// Lists the cameras the box found by itself and connects them. Recorders and
// IP cameras need their login once; every channel showing video is then added.
export default function DiscoveryPanel() {
  const { baseUrl, refreshCameras, pushToast } = useBackend();
  const [devices, setDevices] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [scanned, setScanned] = useState(false);
  const [busyKey, setBusyKey] = useState(null);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");

  const keyOf = (d) => `${d.kind}:${d.host}:${d.port}`;

  async function scan() {
    setScanning(true);
    try {
      const data = await api.discoveryScan(baseUrl);
      setDevices(data.devices || []);
      setScanned(true);
    } catch (e) {
      pushToast("Scan failed", e.message, "medium");
    }
    setScanning(false);
  }

  // Show what the boot-time scan found; scan now if there has not been one.
  useEffect(() => {
    let cancelled = false;
    api
      .discoveryDevices(baseUrl)
      .then((data) => {
        if (cancelled) return;
        if (data.scanned) {
          setDevices(data.devices || []);
          setScanned(true);
        } else {
          scan();
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl]);

  async function connect(device) {
    if (device.kind === "rtsp" && !password) {
      pushToast("Password needed", "Enter the camera / recorder login above first.", "medium");
      return;
    }
    setBusyKey(keyOf(device));
    try {
      const result = await api.discoveryConnect(baseUrl, {
        kind: device.kind,
        host: device.kind === "webcam" ? "" : device.host,
        port: device.port,
        label: device.kind === "rtsp" ? null : device.label,
        username: device.kind === "rtsp" ? username : "",
        password: device.kind === "rtsp" ? password : "",
      });
      if (result.status === "ok") {
        const count = result.added.length;
        pushToast(
          count ? `${count} camera${count > 1 ? "s" : ""} connected` : "Already connected",
          count ? result.added.map((c) => c.name).join(", ") : device.label,
          "medium"
        );
      } else {
        pushToast("Could not connect", result.message || result.status, "high");
      }
      await refreshCameras();
      const data = await api.discoveryDevices(baseUrl);
      setDevices(data.devices || []);
    } catch (e) {
      pushToast("Could not connect", e.message, "high");
    }
    setBusyKey(null);
  }

  const pending = devices.filter((d) => !d.already_added);
  const needsLogin = pending.some((d) => d.kind === "rtsp");

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <p className="text-brand-navy text-[16px] font-semibold">Cameras found automatically</p>
          <p className="text-[12px] text-[#6a6888]">
            Scans this network for IP cameras, recorders and phone camera apps, plus cameras plugged into this device.
          </p>
        </div>
        <button
          type="button"
          onClick={scan}
          disabled={scanning}
          className="bg-brand-navy disabled:opacity-60 text-white text-[13px] font-medium rounded-[5px] h-[38px] px-5 shrink-0"
        >
          {scanning ? "Scanning…" : "Scan again"}
        </button>
      </div>

      {needsLogin && (
        <div className="bg-[#f4f3fa] rounded-[5px] px-4 py-3 flex flex-col gap-2">
          <p className="text-[12px] text-[#4f4b61]">
            Camera / recorder login — entered once, used for the devices below. Every channel that is showing video is added.
          </p>
          <div className="flex gap-2 flex-wrap">
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Username"
              autoComplete="off"
              className="bg-white border border-brand-border rounded-[5px] h-[40px] px-3 text-[13px] outline-none w-full sm:w-[200px]"
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              autoComplete="new-password"
              className="bg-white border border-brand-border rounded-[5px] h-[40px] px-3 text-[13px] outline-none w-full sm:w-[200px]"
            />
          </div>
        </div>
      )}

      <div className="border border-[#d9d9d9] rounded-[8px] overflow-hidden">
        {scanning && devices.length === 0 && <div className="text-center text-[#9c9c9c] text-[13px] py-10">Scanning the network…</div>}
        {!scanning && scanned && devices.length === 0 && (
          <div className="text-center text-[#9c9c9c] text-[13px] py-10 px-4 leading-relaxed">
            Nothing found. Check that the cameras or recorder are powered on and plugged into the same network as this device, then scan
            again. You can also add a camera by hand below.
          </div>
        )}
        {devices.map((d) => {
          const key = keyOf(d);
          return (
            <div key={key} className="flex items-center gap-x-4 gap-y-2 flex-wrap px-4 py-3 border-b border-[#eee] last:border-b-0">
              <div className="flex-1 min-w-[180px]">
                <p className="text-brand-navy text-[14px] font-semibold">{d.label}</p>
                <p className="text-[#6a6888] text-[12px]">
                  {KIND_LABEL[d.kind]} · {d.kind === "webcam" ? "attached to this device" : `${d.host}:${d.port}`}
                  {d.vendor && d.kind === "rtsp" ? ` · ${d.vendor}` : ""}
                </p>
              </div>
              {d.already_added ? (
                <span className="text-[#3c9e62] text-[13px] font-semibold">✓ Connected</span>
              ) : (
                <button
                  type="button"
                  onClick={() => connect(d)}
                  disabled={busyKey !== null}
                  className="bg-[#3c9e62] disabled:opacity-60 text-white text-[13px] font-medium rounded-[5px] h-[34px] px-4"
                >
                  {busyKey === key ? "Connecting…" : "Connect"}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
