import { useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import BreachAlertRow from "../components/BreachAlertRow";
import TakeActionModal from "../components/TakeActionModal";
import { useBackend } from "../context/BackendContext";
import { mediaUrl } from "../lib/api";

export default function BreachAlerts() {
  const [tab, setTab] = useState("active");
  const [actionId, setActionId] = useState(null);
  const { alerts, cameras, ackAlert, pushToast, baseUrl } = useBackend();

  const all = Object.values(alerts).sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
  const rows = tab === "active" ? all.filter((a) => !a.acknowledged) : all.filter((a) => a.acknowledged);

  async function handleResolve(id) {
    try {
      await ackAlert(id);
      setActionId(null);
    } catch (e) {
      pushToast("Action failed", e.message, "medium");
    }
  }

  const actionAlert = actionId ? alerts[actionId] : null;
  const cameraLabel = (id) => cameras[id]?.name || (id === "site" ? "Whole site" : id);

  return (
    <DashboardLayout>
      <div className="flex flex-col">
        <div className="flex items-center gap-6 sm:gap-[73px] border-b border-[#e4e4e4] pb-2.5">
          <button
            type="button"
            onClick={() => setTab("active")}
            className={`text-[16px] tracking-[0.2px] pb-1 border-b-4 -mb-[13px] ${
              tab === "active" ? "text-brand-navy font-medium border-brand-navy" : "text-[#4f4b61]/50 border-transparent"
            }`}
          >
            Active Breach
          </button>
          <button
            type="button"
            onClick={() => setTab("logs")}
            className={`text-[16px] tracking-[0.2px] pb-1 border-b-4 -mb-[13px] ${
              tab === "logs" ? "text-brand-navy font-medium border-brand-navy" : "text-[#4f4b61]/50 border-transparent"
            }`}
          >
            Logs/History
          </button>
        </div>

        <div className="border border-[#cbcbcb] rounded-[10px] overflow-hidden mt-5">
          <div className="bg-[#f2f2f2] h-[63px] hidden lg:flex items-center px-[28px] gap-10 text-[#4f4b61] text-[14px] font-medium">
            <p className="w-[280px]">Breach</p>
            <div className="flex gap-16 w-[219px]">
              <p className="flex-1">Camera</p>
              <p>Created</p>
            </div>
            <p className="ml-auto w-[134px] text-center">Action</p>
          </div>

          <div className="flex flex-col">
            {rows.length === 0 && (
              <div className="text-center text-[#9c9c9c] text-[14px] py-14">
                {tab === "active" ? "No active breaches." : "No resolved breaches yet."}
              </div>
            )}
            {rows.map((row) => {
              return (
                <BreachAlertRow
                  key={row.alert_id}
                  name={(row.title || "Alert").replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())}
                  message={row.message}
                  ip={cameraLabel(row.camera_id)}
                  date={row.created_at ? new Date(row.created_at).toLocaleDateString() : ""}
                  createdAt={row.created_at}
                  acknowledged={row.acknowledged}
                  thumbnail={mediaUrl(baseUrl, row.snapshot_url)}
                  onTakeAction={() => setActionId(row.alert_id)}
                />
              );
            })}
          </div>
        </div>
      </div>

      {actionAlert && (
        <TakeActionModal
          alert={actionAlert}
          cameraName={cameraLabel(actionAlert.camera_id)}
          onResolve={() => handleResolve(actionAlert.alert_id)}
          onClose={() => setActionId(null)}
        />
      )}
    </DashboardLayout>
  );
}
