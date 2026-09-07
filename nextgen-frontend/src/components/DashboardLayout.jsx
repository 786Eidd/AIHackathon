import Sidebar from "./Sidebar";
import Header from "./Header";

export default function DashboardLayout({ title, actionLabel, onAction, children }) {
  return (
    <div className="flex bg-white min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header />
        <div className="px-[36px] pt-[10px]">
          {(title || actionLabel) && (
            <div className="flex items-center justify-between border-b border-[#e4e4e4] py-[10px]">
              {title && (
                <p className="text-brand-navy text-[16px] font-semibold tracking-[0.2px]">{title}</p>
              )}
              {actionLabel && (
                <button
                  type="button"
                  onClick={onAction}
                  className="text-[#db222a] text-[14px] font-bold tracking-[0.2px]"
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
