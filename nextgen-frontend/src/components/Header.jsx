import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { icons, logoIcon } from "../assets/figmaAssets";
import { useBackend } from "../context/BackendContext";

function AdminMenu() {
  const navigate = useNavigate();
  const { health, cameras, identities, connected } = useBackend();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const close = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const list = Object.values(cameras);
  const online = list.filter((c) => (c.status || "").toLowerCase() === "online").length;

  const go = (path) => {
    setOpen(false);
    navigate(path);
  };

  const item = "w-full text-left px-4 h-[40px] text-[13.5px] text-[#3d3a52] hover:bg-[#f4f3fa] flex items-center gap-2";

  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((v) => !v)} className="flex items-center gap-1.5" aria-haspopup="menu" aria-expanded={open}>
        <img src={icons.avatar} alt="" className="w-5 h-5" />
        <span className="hidden md:inline text-[#848295] text-[14px] font-medium tracking-[0.2px]">Admin</span>
        <span className="hidden md:inline text-[#848295] text-[10px]">▾</span>
      </button>

      {open && (
        <div className="absolute right-0 top-[34px] w-[260px] bg-white rounded-[8px] shadow-[0_8px_30px_rgba(0,0,0,0.16)] border border-[#ececec] overflow-hidden z-20" role="menu">
          <div className="px-4 py-3 border-b border-[#eee]">
            <p className="text-brand-navy text-[14px] font-semibold">Admin</p>
            <p className="text-[12px] text-[#6a6888]">Site administrator · this device</p>
          </div>

          <div className="px-4 py-3 border-b border-[#eee] grid grid-cols-3 gap-2 text-center">
            <div>
              <p className="text-brand-navy text-[15px] font-bold">
                {online}/{list.length}
              </p>
              <p className="text-[10.5px] text-[#9c9c9c]">cameras live</p>
            </div>
            <div>
              <p className="text-brand-navy text-[15px] font-bold">{identities.length}</p>
              <p className="text-[10.5px] text-[#9c9c9c]">faces enrolled</p>
            </div>
            <div>
              <p className={`text-[15px] font-bold ${connected ? "text-[#3c9e62]" : "text-brand-red"}`}>{connected ? "OK" : "Down"}</p>
              <p className="text-[10.5px] text-[#9c9c9c]">system</p>
            </div>
          </div>

          <button type="button" className={item} onClick={() => go("/settings")}>
            ⚙ Settings & emergency contacts
          </button>
          <button type="button" className={item} onClick={() => go("/camera-management")}>
            🎥 Manage cameras
          </button>
          <button type="button" className={item} onClick={() => go("/face-management")}>
            👤 Manage faces
          </button>
          <button type="button" className={item} onClick={() => go("/onboarding/1")}>
            🧭 Run setup again
          </button>
          {health && !health.weapon_model_loaded && (
            <p className="px-4 py-2 text-[11.5px] text-[#8a6416] bg-[#fff8e6] border-t border-[#f0dcae]">Weapon detection is off: no weapon model is installed.</p>
          )}
          <button type="button" className={`${item} border-t border-[#eee] text-brand-red`} onClick={() => go("/login")}>
            ⎋ Logout
          </button>
        </div>
      )}
    </div>
  );
}

export default function Header({ onMenu }) {
  const navigate = useNavigate();
  const { armed, toggleArm, connected, alerts } = useBackend();
  const unackCount = Object.values(alerts).filter((a) => !a.acknowledged).length;

  return (
    <div className="bg-[#fafafa] border-b border-black/[0.08] h-[64px] lg:h-[80px] w-full flex items-center justify-between gap-3 px-4 lg:px-10 sticky top-0 z-10">
      <div className="flex items-center gap-3 min-w-0">
        {/* The full logo lives in the sidebar; on small screens that is a drawer. */}
        <button type="button" onClick={onMenu} className="lg:hidden text-brand-navy text-[22px] leading-none px-1" aria-label="Open menu">
          ☰
        </button>
        <Link to="/cameras" className="lg:hidden" title="Live cameras">
          <img src={logoIcon} alt="NexGen" className="h-[36px] w-auto" />
        </Link>
        {/* Silent while healthy; only speaks up when the system is unreachable. */}
        {!connected && (
          <span className="flex items-center gap-1.5 text-[12px] font-medium text-brand-red truncate">
            <span className="inline-block size-[7px] rounded-full shrink-0 bg-brand-red" />
            <span>System offline — reconnecting…</span>
          </span>
        )}
      </div>
      <div className="flex items-center gap-4 sm:gap-8 shrink-0">
        <button
          type="button"
          onClick={toggleArm}
          className={`flex items-center justify-center rounded-full h-[31px] px-4 text-[14px] font-medium relative w-[99px] transition-colors ${
            armed ? "bg-[#9389e3] text-[#fff2f2]" : "bg-gray-300 text-gray-700"
          }`}
        >
          <span className="capitalize">{armed ? "arm" : "unarm"}</span>
          <span
            className={`absolute top-[2px] bg-white rounded-full size-[27px] transition-all ${
              armed ? "right-[2px]" : "left-[2px]"
            }`}
          />
        </button>
        <button type="button" onClick={() => navigate("/breach-alerts")} className="relative">
          <img src={icons.bell} alt="Notifications" className="w-5 h-5" />
          {unackCount > 0 && (
            <span className="absolute -top-2 -right-2 bg-brand-red text-white text-[9px] font-bold rounded-full min-w-[15px] h-[15px] flex items-center justify-center px-1">
              {unackCount}
            </span>
          )}
        </button>
        <AdminMenu />
        <button type="button" onClick={() => navigate("/login")} className="hidden md:flex items-center gap-1.5" title="Logout">
          <img src={icons.logout} alt="" className="w-5 h-5" />
          <span className="text-[#848295] text-[14px] font-medium tracking-[0.2px]">Logout</span>
        </button>
      </div>
    </div>
  );
}
