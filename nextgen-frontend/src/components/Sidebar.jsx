import { NavLink } from "react-router-dom";
import { icons } from "../assets/figmaAssets";

const navItems = [
  { to: "/cameras", label: "Streaming", icon: icons.liveStreaming },
  { to: "/breach-alerts", label: "Breach Alerts", icon: icons.breachAlert },
  { to: "/camera-management", label: "Camera Management", icon: icons.cameraManagement },
  { to: "/face-management", label: "Face Management", icon: icons.faceId },
  { to: "/contact", label: "Contact /Complaint", icon: icons.contact },
  { to: "/settings", label: "Setting", icon: icons.settings },
];

export default function Sidebar() {
  return (
    <div className="bg-[#fafafa] border-r border-[#eaeaea] h-screen w-[255px] shrink-0 flex flex-col justify-between sticky top-0">
      <div className="flex flex-col pt-[112px]">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
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
      <button
        type="button"
        className="mx-[45px] mb-10 h-[48px] rounded-[6px] bg-[#db222a] text-white font-semibold text-[16px] tracking-[0.2px] flex items-center justify-center gap-2"
      >
        <img src={icons.radioChecked} alt="" className="w-6 h-6" />
        Create Panic
      </button>
    </div>
  );
}
