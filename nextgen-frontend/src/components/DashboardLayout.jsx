import { useState } from "react";
import Sidebar from "./Sidebar";
import Header from "./Header";

export default function DashboardLayout({ title, actionLabel, onAction, children }) {
  // Below the lg breakpoint the sidebar becomes a slide-in drawer.
  const [navOpen, setNavOpen] = useState(false);

  return (
    <div className="flex bg-white min-h-screen">
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      <div className="flex-1 min-w-0 flex flex-col">
        <Header onMenu={() => setNavOpen(true)} />
        <div className="px-4 sm:px-6 lg:px-[36px] pt-[10px]">
          {(title || actionLabel) && (
            <div className="flex items-center justify-between gap-3 border-b border-[#e4e4e4] py-[10px]">
              {title && (
                <p className="text-brand-navy text-[16px] font-semibold tracking-[0.2px]">{title}</p>
              )}
              {actionLabel && (
                <button
                  type="button"
                  onClick={onAction}
                  className="text-[#db222a] text-[14px] font-bold tracking-[0.2px] text-right"
                >
                  {actionLabel}
                </button>
              )}
            </div>
          )}
          <div className="py-[20px]">{children}</div>
        </div>
      </div>
    </div>
  );
}
