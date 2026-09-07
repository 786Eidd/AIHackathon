import { useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import BreachAlertRow from "../components/BreachAlertRow";
import { useBackend } from "../context/BackendContext";

export default function BreachAlerts() {
  const [tab, setTab] = useState("active");
  const { alerts, cameras, ackAlert, pushToast } = useBackend();

  const all = Object.values(alerts).sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
  const rows = tab === "active" ? all.filter((a) => !a.acknowledged) : all.filter((a) => a.acknowledged);

  async function handleTakeAction(id) {
    try {
      await ackAlert(id);
    } catch (e) {
      pushToast("Action failed", e.message, "medium");
    }
  }

  return (
    <DashboardLayout>
      <div className="flex flex-col">
        <div className="flex items-center gap-[73px] border-b border-[#e4e4e4] pb-2.5">
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
          <div className="bg-[#f2f2f2] h-[63px] flex items-center px-[60px] gap-[341px] text-[#4f4b61] text-[14px] font-medium">
            <p>Breachs</p>
            <div className="flex gap-24 w-[232px]">
              <p>Camera</p>
              <p>Created</p>
            </div>
            <p>Action</p>
          </div>

          <div className="flex flex-col">
            {rows.length === 0 && (
              <div className="text-center text-[#9c9c9c] text-[14px] py-14">
                {tab === "active" ? "No active breaches." : "No resolved breaches yet."}
              </div>
            )}
            {rows.map((row) => {
              const cam = cameras[row.camera_id];
              return (
                <BreachAlertRow
                  key={row.alert_id}
                  name={row.title || "Alert"}
                  message={row.message}
                  ip={(cam && cam.name) || row.camera_id}
                  date={row.created_at ? new Date(row.created_at).toLocaleDateString() : ""}
                  createdAt={row.created_at}
                  acknowledged={row.acknowledged}
                  onTakeAction={() => handleTakeAction(row.alert_id)}
                />
              );
            })}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
