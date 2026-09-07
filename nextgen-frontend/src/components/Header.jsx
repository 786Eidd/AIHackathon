import { useNavigate } from "react-router-dom";
import { logo, icons } from "../assets/figmaAssets";
import { useBackend } from "../context/BackendContext";

export default function Header() {
  const navigate = useNavigate();
  const { armed, toggleArm, connected, baseUrl, alerts } = useBackend();
  const unackCount = Object.values(alerts).filter((a) => !a.acknowledged).length;

  function handleLogout() {
    navigate("/login");
  }

  return (
    <div className="bg-[#fafafa] border-b border-black/[0.08] h-[80px] w-full flex items-center justify-between px-10 sticky top-0 z-10">
      <div className="flex items-center gap-3">
        <img src={logo} alt="NextGen" className="h-[43px] object-contain" />
        <span
          className="hidden lg:flex items-center gap-1.5 text-[11px] text-[#9c9c9c] border-l border-black/10 pl-3 ml-1"
          title={baseUrl}
        >
          <span className={`inline-block size-[7px] rounded-full ${connected ? "bg-[#3c9e62]" : "bg-brand-red"}`} />
          {connected ? "Backend connected" : "Backend unreachable"}
        </span>
      </div>
      <div className="flex items-center gap-8">
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
        <div className="flex items-center gap-1.5">
          <img src={icons.avatar} alt="" className="w-5 h-5" />
          <span className="text-[#848295] text-[14px] font-medium tracking-[0.2px]">Admin</span>
        </div>
        <button type="button" onClick={handleLogout} className="flex items-center gap-1.5">
          <img src={icons.logout} alt="" className="w-5 h-5" />
          <span className="text-[#848295] text-[14px] font-medium tracking-[0.2px]">Logout</span>
        </button>
      </div>
    </div>
  );
}
