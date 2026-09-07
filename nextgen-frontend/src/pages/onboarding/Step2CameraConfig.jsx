import { useNavigate } from "react-router-dom";
import { useState } from "react";
import OnboardingSidebar from "../../components/OnboardingSidebar";
import { useBackend } from "../../context/BackendContext";

const fields = [
  { key: "name", label: "Name", placeholder: "Enter name" },
  { key: "location", label: "Location", placeholder: "lab room e.g" },
  { key: "ip", label: "IP", placeholder: "192.168.2.1 e.g" },
  { key: "port", label: "Port", placeholder: "554 e.g" },
  { key: "username", label: "Username", placeholder: "Enter username" },
  { key: "password", label: "Password", placeholder: "Enter password", type: "password" },
];

export default function Step2CameraConfig() {
  const navigate = useNavigate();
  const { createCamera, pushToast } = useBackend();
  const [values, setValues] = useState({ port: "554" });
  const [added, setAdded] = useState(false);
  const [saving, setSaving] = useState(false);

  function update(key, value) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  async function handleAddCamera(e) {
    e.preventDefault();
    if (!values.name || !values.ip) {
      pushToast("Missing fields", "Name and IP are required.", "medium");
      return;
    }
    const auth = values.username ? `${values.username}:${values.password || ""}@` : "";
    const rtsp_url = `rtsp://${auth}${values.ip}:${values.port || "554"}/Streaming/Channels/101`;
    setSaving(true);
    try {
      await createCamera({ name: values.name, location: values.location || null, rtsp_url, enabled: true });
      setAdded(true);
      pushToast("Camera added", values.name, "medium");
    } catch (e) {
      pushToast("Could not add camera", e.message, "medium");
    }
    setSaving(false);
  }

  return (
    <div className="flex min-h-screen bg-white">
      <OnboardingSidebar currentStep={2} />

      <div className="flex-1 flex flex-col items-center justify-center gap-10 px-8">
        <div className="flex flex-col items-center gap-2 w-[366px]">
          <h1 className="text-brand-navy text-[32px] font-bold text-center">Camera configuration</h1>
          <p className="text-[#474747] text-[14px] text-center">Add your first Hikvision-style RTSP camera (you can add more later).</p>
        </div>

        <form onSubmit={handleAddCamera} className="flex flex-col items-center gap-[30px] w-full">
          <div className="grid grid-cols-2 gap-x-[18px] gap-y-[18px] w-[518px]">
            {fields.map((field) => (
              <div key={field.key} className="flex flex-col gap-3">
                <label className="text-brand-navy text-[16px] font-medium">{field.label}</label>
                <div className="bg-brand-field border border-brand-border rounded-[5px] h-[52px] flex items-center px-5">
                  <input
                    type={field.type ?? "text"}
                    value={values[field.key] ?? ""}
                    onChange={(e) => update(field.key, e.target.value)}
                    placeholder={field.placeholder}
                    className="bg-transparent outline-none flex-1 text-[14px] placeholder:text-[#c6c6c6]"
                  />
                </div>
              </div>
            ))}
          </div>

          <button
            type="submit"
            disabled={saving}
            className="border border-brand-navy text-brand-navy font-medium text-[14px] rounded-[5px] h-12 w-[200px] disabled:opacity-60"
          >
            {saving ? "Adding…" : "Add Camera"}
          </button>

          {added && (
            <div className="bg-[#deecff] text-brand-navy text-[14px] rounded-md py-3 px-4 w-[486px] flex items-center justify-center text-center">
              Camera added and registered with the backend. You can add more later from Camera Management.
            </div>
          )}

          <button type="button" onClick={() => navigate("/onboarding/3")} className="bg-brand-red text-white font-bold text-[16px] rounded-[5px] h-[56px] w-[200px]">
            Next
          </button>
        </form>
      </div>
    </div>
  );
}
