import { useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import EmergencyContacts from "../components/EmergencyContacts";
import { useBackend } from "../context/BackendContext";

export default function Settings() {
  const [tab, setTab] = useState("general");
  const [allowMobile, setAllowMobile] = useState(() => localStorage.getItem("nexgen_allow_mobile") === "1");
  const { health, armed, toggleArm, cameras, baseUrl, setBaseUrl, connect, connected } = useBackend();
  const [urlDraft, setUrlDraft] = useState(baseUrl);

  function updateAllowMobile(v) {
    setAllowMobile(v);
    localStorage.setItem("nexgen_allow_mobile", v ? "1" : "0");
  }

  async function handleReconnect() {
    await connect(urlDraft);
  }

  const runningCount = Object.values(cameras).filter((c) => (c.status || "").toLowerCase() === "online").length;

  return (
    <DashboardLayout title="Setting">
      <div className="flex items-center gap-6 sm:gap-[73px] border-b border-[#e4e4e4] pb-2.5 mb-6">
        <button
          type="button"
          onClick={() => setTab("general")}
          className={`text-[16px] tracking-[0.2px] pb-1 border-b-4 -mb-[13px] ${
            tab === "general" ? "text-brand-navy font-medium border-brand-navy" : "text-[#4f4b61]/50 border-transparent"
          }`}
        >
          General setting
        </button>
        <button
          type="button"
          onClick={() => setTab("armunarm")}
          className={`text-[16px] tracking-[0.2px] pb-1 border-b-4 -mb-[13px] ${
            tab === "armunarm" ? "text-brand-navy font-medium border-brand-navy" : "text-[#4f4b61]/50 border-transparent"
          }`}
        >
          Arm/unarm
        </button>
      </div>

      {tab === "general" ? (
        <div className="flex flex-col gap-6">
          <div className="border border-[#d9d9d9] rounded-[5px] p-4 sm:p-6">
            <p className="text-brand-navy text-[16px] font-medium mb-3">Emergency contacts</p>
            <div className="border-t border-[#e4e4e4] mb-4" />
            <EmergencyContacts />
          </div>

          <div className="border border-[#d9d9d9] rounded-[5px] p-6">
            <p className="text-brand-navy text-[16px] font-medium mb-3">Permissions</p>
            <div className="border-t border-[#e4e4e4] mb-4" />
            <label className="flex items-center gap-1.5 cursor-pointer w-fit">
              <input
                type="checkbox"
                checked={allowMobile}
                onChange={(e) => updateAllowMobile(e.target.checked)}
                className="w-4 h-[18px] rounded border border-[#b0a9a9]"
              />
              <span className="text-brand-navy text-[14px]">Allow to connect the mobile</span>
            </label>
          </div>

          <div className="border border-[#d9d9d9] rounded-[5px] p-6">
            <p className="text-brand-navy text-[16px] font-medium mb-3">Backend connection</p>
            <div className="border-t border-[#e4e4e4] mb-4" />
            <div className="flex items-center gap-3 mb-4">
              <span className={`inline-block size-[8px] rounded-full ${connected ? "bg-[#3c9e62]" : "bg-brand-red"}`} />
              <span className="text-[13px] text-[#6a6888]">{connected ? "Connected" : "Unreachable"}</span>
            </div>
            <div className="flex gap-3 max-w-[520px]">
              <input
                value={urlDraft}
                onChange={(e) => setUrlDraft(e.target.value)}
                className="flex-1 bg-brand-field border border-brand-border rounded-[5px] h-[44px] px-4 text-[13px]"
              />
              <button onClick={handleReconnect} className="border border-brand-navy text-brand-navy font-medium text-[13px] rounded-[5px] h-[44px] px-5">
                Reconnect
              </button>
            </div>
          </div>

          <div className="border border-[#d9d9d9] rounded-[5px] p-6">
            <p className="text-brand-navy text-[16px] font-medium mb-3">Streaming defaults (from backend <code>/health</code>)</p>
            <div className="border-t border-[#e4e4e4] mb-4" />
            <div className="flex flex-wrap gap-x-10 gap-y-3 text-[13px] text-[#6a6888]">
              <Stat label="Device" value={health?.device} />
              <Stat label="Sample FPS" value={health?.streaming?.sample_fps} />
              <Stat label="Inference width" value={health?.streaming?.inference_width} />
              <Stat label="Max cameras" value={health?.streaming?.max_cameras} />
              <Stat label="Weapon model" value={health?.weapon_model_loaded ? "loaded" : "not loaded"} />
              <Stat label="Identities loaded" value={health?.identity_count} />
              <Stat label="Qwen chat" value={health?.qwen_enabled ? "enabled" : "disabled"} />
            </div>
            <p className="text-[11.5px] text-brand-gray mt-4">These come from the backend's <code>.env</code> and aren't editable here.</p>
          </div>
        </div>
      ) : (
        <div className="border border-[#d9d9d9] rounded-[5px] p-6 max-w-[700px]">
          <p className="text-brand-navy text-[16px] font-medium mb-3">Arm / Unarm</p>
          <div className="border-t border-[#e4e4e4] mb-4" />
          <p className="text-[13px] text-[#6a6888] mb-4">
            The Arm/Unarm switch in the header starts every registered camera (Arm) or stops every running camera
            (Unarm) in one click.
          </p>
          <div className="flex items-center gap-8">
            <div>
              <p className="text-brand-navy text-[20px] font-bold">{armed ? "Armed" : "Unarmed"}</p>
              <p className="text-[12px] text-[#9c9c9c]">{runningCount} camera(s) currently running</p>
            </div>
            <button onClick={toggleArm} className="bg-brand-red text-white font-bold text-[14px] rounded-[5px] h-[44px] px-6">
              Toggle
            </button>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <div className="text-[10.5px] uppercase tracking-wide text-[#b0adc2]">{label}</div>
      <div className="text-brand-navy font-semibold text-[14px]">{value ?? "—"}</div>
    </div>
  );
}
