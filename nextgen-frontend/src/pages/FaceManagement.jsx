import { useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import EnrollForm from "../components/EnrollForm";
import { useBackend } from "../context/BackendContext";

export default function FaceManagement() {
  const [tab, setTab] = useState("add");
  const { identities, reloadIdentities, deleteIdentity, pushToast } = useBackend();
  const [reloading, setReloading] = useState(false);

  async function handleReload() {
    setReloading(true);
    try {
      await reloadIdentities();
    } catch (e) {
      pushToast("Reload failed", e.message, "medium");
    }
    setReloading(false);
  }

  async function handleRemove(name) {
    if (!window.confirm(`Remove "${name}"? They will be reported as unknown from now on.`)) return;
    try {
      await deleteIdentity(name);
      pushToast("Identity removed", name, "medium");
    } catch (e) {
      pushToast("Remove failed", e.message, "medium");
    }
  }

  return (
    <DashboardLayout>
      <div className="flex flex-col gap-8">
        <div className="flex items-center gap-6 sm:gap-[73px] border-b border-[#e4e4e4] pb-2.5">
          <button
            type="button"
            onClick={() => setTab("add")}
            className={`text-[16px] tracking-[0.2px] pb-1 border-b-4 -mb-[13px] ${
              tab === "add" ? "text-brand-navy font-medium border-brand-navy" : "text-[#4f4b61]/50 border-transparent"
            }`}
          >
            Add Face Details
          </button>
          <button
            type="button"
            onClick={() => setTab("manage")}
            className={`text-[16px] tracking-[0.2px] pb-1 border-b-4 -mb-[13px] ${
              tab === "manage" ? "text-brand-navy font-medium border-brand-navy" : "text-[#4f4b61]/50 border-transparent"
            }`}
          >
            Manage Existing Faces
          </button>
        </div>

        {tab === "add" ? (
          <div className="max-w-[640px]">
            <EnrollForm onEnrolled={() => setTab("manage")} />
          </div>
        ) : (
          <div className="flex flex-col gap-4 max-w-[900px]">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <p className="text-brand-navy text-[16px] font-semibold">Enrolled identities ({identities.length})</p>
              <button
                onClick={handleReload}
                disabled={reloading}
                className="border border-brand-navy text-brand-navy font-medium text-[13px] rounded-[5px] h-[38px] px-4"
              >
                {reloading ? "Reloading…" : "↻ Reload from disk"}
              </button>
            </div>
            <div className="border border-[#cbcbcb] rounded-[10px] overflow-hidden">
              <div className="bg-[#f2f2f2] h-[52px] flex items-center justify-between px-4 sm:px-8 gap-4 text-[#4f4b61] text-[14px] font-medium">
                <p>Name</p>
                <p>Action</p>
              </div>
              {identities.length === 0 && <div className="px-8 py-10 text-[#9c9c9c] text-[13px]">No identities enrolled yet.</div>}
              {identities.map((name) => (
                <div key={name} className="flex items-center justify-between px-4 sm:px-8 gap-4 h-[56px] border-t border-[#eee] text-[14px] text-[#221f54]">
                  <p className="flex-1 min-w-0 truncate font-medium">👤 {name}</p>
                  <button onClick={() => handleRemove(name)} className="text-brand-red text-[14px] font-medium">
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
