import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { icons, logo } from "../assets/figmaAssets";
import { useBackend } from "../context/BackendContext";
import TakeActionModal from "./TakeActionModal";

const navItems = [
  { to: "/cameras", label: "Streaming", icon: icons.liveStreaming },
  { to: "/breach-alerts", label: "Breach Alerts", icon: icons.breachAlert },
  { to: "/events", label: "Events & Assistant", icon: icons.activity },
  { to: "/camera-management", label: "Camera Management", icon: icons.cameraManagement },
  { to: "/face-management", label: "Face Management", icon: icons.faceId },
  { to: "/contact", label: "Contact /Complaint", icon: icons.contact },
  { to: "/settings", label: "Setting", icon: icons.settings },
];

function PanicConfirm({ busy, onConfirm, onCancel }) {
  const [note, setNote] = useState("");

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-3" onClick={onCancel}>
      <div className="bg-white rounded-[10px] w-full max-w-[460px] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="bg-[#db222a] text-white px-5 py-4">
          <p className="text-[18px] font-bold">Raise a panic alarm?</p>
          <p className="text-[12.5px] opacity-90">Use this when there is an emergency at the site right now.</p>
        </div>
        <div className="p-5 flex flex-col gap-4">
          <ul className="text-[13.5px] text-[#3d3a52] leading-relaxed list-disc pl-5">
            <li>Every camera is switched on.</li>
            <li>A picture is saved from each live camera as evidence.</li>
            <li>A HIGH alert goes to every phone and PC that has this dashboard open.</li>
            <li>You are shown who to call. The system does not phone anyone by itself.</li>
          </ul>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={500}
            placeholder="What is happening? (optional)"
            className="bg-brand-field border border-brand-border rounded-[5px] h-[42px] px-3 text-[13px] outline-none"
          />
          <div className="flex gap-3 justify-end flex-wrap">
            <button type="button" onClick={onCancel} className="border border-brand-border text-[#4f4b61] text-[13px] rounded-[5px] h-[42px] px-5">
              Cancel
            </button>
            <button type="button" onClick={() => onConfirm(note)} disabled={busy} className="bg-[#db222a] disabled:opacity-60 text-white font-bold text-[14px] rounded-[5px] h-[42px] px-5">
              {busy ? "Raising alarm…" : "Yes, raise the alarm"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Sidebar({ open = false, onClose }) {
  const { raisePanic, ackAlert, pushToast } = useBackend();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [panicAlert, setPanicAlert] = useState(null);

  async function confirmPanic(note) {
    setBusy(true);
    try {
      const result = await raisePanic(note);
      setConfirming(false);
      setPanicAlert(result.alert);
    } catch (e) {
      pushToast("Panic alarm failed", e.message, "high");
    }
    setBusy(false);
  }

  async function resolvePanic() {
    try {
      await ackAlert(panicAlert.alert_id);
      setPanicAlert(null);
    } catch (e) {
      pushToast("Action failed", e.message, "medium");
    }
  }

  return (
    <>
      {open && <div className="fixed inset-0 bg-black/40 z-30 lg:hidden" onClick={onClose} />}

      <div
        className={`bg-[#fafafa] border-r border-[#eaeaea] h-screen w-[255px] shrink-0 flex flex-col justify-between
          fixed inset-y-0 left-0 z-40 transition-transform duration-200 overflow-y-auto
          lg:sticky lg:top-0 lg:z-auto lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex flex-col">
          {/* The logo is the way home: the live camera overview. */}
          <Link to="/cameras" onClick={onClose} className="h-[80px] flex items-center px-6 shrink-0" title="Live cameras">
            <img src={logo} alt="NexGen Security & Management" className="h-[44px] w-auto" />
          </Link>
          <div className="flex flex-col pt-[32px]">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  `h-[56px] flex items-center gap-2 pl-[43px] text-[14px] tracking-[0.2px] ${
                    isActive
                      ? "bg-[rgba(229,226,250,0.83)] text-brand-navy font-medium"
                      : "text-[#4f4b61] opacity-70 hover:opacity-100"
                  }`
                }
              >
                <img src={item.icon} alt="" className="w-5 h-5" />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="mx-[45px] my-8 h-[48px] shrink-0 rounded-[6px] bg-[#db222a] hover:bg-[#c11b22] text-white font-semibold text-[16px] tracking-[0.2px] flex items-center justify-center gap-2"
        >
          <img src={icons.radioChecked} alt="" className="w-6 h-6" />
          Create Panic
        </button>
      </div>

      {/* Rendered outside the sliding panel so they cover the whole screen. */}
      {confirming && <PanicConfirm busy={busy} onConfirm={confirmPanic} onCancel={() => setConfirming(false)} />}
      {panicAlert && <TakeActionModal alert={panicAlert} cameraName="Whole site" onResolve={resolvePanic} onClose={() => setPanicAlert(null)} />}
    </>
  );
}
