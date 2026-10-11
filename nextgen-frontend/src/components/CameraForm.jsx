import { SOURCE_TYPES, buildStreamUrl } from "../lib/streamUrl";

function Field({ label, value, onChange, placeholder, type = "text", wide = false }) {
  return (
    <div className={`flex flex-col gap-3 ${wide ? "sm:col-span-2" : ""}`}>
      <label className="text-brand-navy text-[16px] font-medium">{label}</label>
      <div className="bg-brand-field border border-brand-border rounded-[5px] h-[52px] flex items-center px-5">
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="bg-transparent outline-none flex-1 min-w-0 text-[14px] placeholder:text-[#c6c6c6]"
        />
      </div>
    </div>
  );
}

function Select({ label, value, onChange, options }) {
  return (
    <div className="flex flex-col gap-3">
      <label className="text-brand-navy text-[16px] font-medium">{label}</label>
      <div className="bg-brand-field border border-brand-border rounded-[5px] h-[52px] flex items-center px-4">
        <select value={value} onChange={(e) => onChange(e.target.value)} className="bg-transparent outline-none flex-1 min-w-0 text-[14px]">
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

const HINTS = {
  hikvision:
    "Use the camera's (or NVR's) IP and login. On an NVR/DVR each camera is a channel: 1, 2, 3… Sub stream is recommended — it is lighter and plenty for detection.",
  webcam:
    "Uses a camera attached to the computer running the backend. Device 0 is normally the built-in webcam; try 1 for a USB camera.",
  mobile:
    'Install the free "IP Webcam" app on an Android phone, tap "Start server", and enter the IP it shows (phone and PC must be on the same Wi-Fi). For iPhone, use any RTSP/MJPEG camera app and add its URL under "Custom URL".',
  custom: "Any rtsp://, rtsps://, http(s):// or rtmp:// stream URL, or webcam://0.",
};

export default function CameraForm({ form, setForm }) {
  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }));

  function changeSource(source) {
    setForm((f) => ({
      ...f,
      source,
      port: source === "mobile" ? "8080" : source === "hikvision" ? "554" : f.port,
      user: source === "hikvision" ? f.user || "admin" : source === "mobile" ? "" : f.user,
    }));
  }

  const preview = buildStreamUrl(form).replace(/:\/\/([^:@/]+):[^@]*@/, "://$1:•••@");

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap gap-2">
        {SOURCE_TYPES.map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => changeSource(s.key)}
            className={`h-[38px] px-4 rounded-[5px] text-[13px] font-medium border ${
              form.source === s.key ? "bg-brand-navy text-white border-brand-navy" : "border-brand-border text-[#4f4b61]"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      <p className="text-[12px] text-[#6a6888] leading-relaxed bg-[#f4f3fa] rounded-[5px] px-4 py-3">{HINTS[form.source]}</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-[18px] gap-y-[18px]">
        <Field label="Name" value={form.name} onChange={set("name")} placeholder="Front door" />
        <Field label="Location" value={form.location} onChange={set("location")} placeholder="Ground floor" />

        {form.source === "hikvision" && (
          <>
            <Field label="IP address" value={form.ip} onChange={set("ip")} placeholder="192.168.1.64" />
            <Field label="RTSP port" value={form.port} onChange={set("port")} placeholder="554" />
            <Field label="Username" value={form.user} onChange={set("user")} placeholder="admin" />
            <Field label="Password" type="password" value={form.pass} onChange={set("pass")} placeholder="Camera password" />
            <Field label="Channel" value={form.channel} onChange={set("channel")} placeholder="1" />
            <Select
              label="Stream"
              value={form.stream}
              onChange={set("stream")}
              options={[
                { value: "sub", label: "Sub stream (recommended)" },
                { value: "main", label: "Main stream (full resolution)" },
              ]}
            />
          </>
        )}

        {form.source === "webcam" && (
          <Select
            label="Device"
            value={form.device}
            onChange={set("device")}
            options={["0", "1", "2", "3"].map((d) => ({ value: d, label: d === "0" ? "0 — default webcam" : `${d}` }))}
          />
        )}

        {form.source === "mobile" && (
          <>
            <Field label="Phone IP address" value={form.ip} onChange={set("ip")} placeholder="192.168.1.23" />
            <Field label="Port" value={form.port} onChange={set("port")} placeholder="8080" />
            <Field label="Username (if set in app)" value={form.user} onChange={set("user")} placeholder="optional" />
            <Field label="Password (if set in app)" type="password" value={form.pass} onChange={set("pass")} placeholder="optional" />
          </>
        )}

        {form.source === "custom" && (
          <Field wide label="Stream URL" value={form.url} onChange={set("url")} placeholder="rtsp://user:pass@192.168.1.50:554/cam/realmonitor?channel=1&subtype=1" />
        )}
      </div>

      {form.source !== "custom" && (
        <p className="text-[11.5px] text-brand-gray break-all">
          Connects to <code className="bg-[#f2f2f2] px-1 rounded">{preview}</code>
        </p>
      )}
    </div>
  );
}
