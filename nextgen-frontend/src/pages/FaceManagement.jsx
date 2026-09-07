import { useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { onboarding } from "../assets/figmaAssets";
import { useBackend } from "../context/BackendContext";

export default function FaceManagement() {
  const [tab, setTab] = useState("add");
  const [fullName, setFullName] = useState("");
  const [faceType, setFaceType] = useState("permanent");
  const { identities, reloadIdentities, pushToast } = useBackend();
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

  return (
    <DashboardLayout>
      <div className="flex flex-col gap-8">
        <div className="flex items-center gap-[73px] border-b border-[#e4e4e4] pb-2.5">
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
          <form onSubmit={(e) => e.preventDefault()} className="flex flex-col gap-6 max-w-[1097px]">
            <div className="bg-[#fff8e6] border border-[#f0dcae] text-[#8a6416] text-[12px] rounded-[6px] px-4 py-3 leading-relaxed">
              This NexGen backend enrolls faces offline — a Python script (<code>face-embedder/enroll.py</code>) builds{" "}
              <code>identity_store.pkl</code> from photo folders on the server. There's no upload endpoint yet, so this
              form can't push a photo to the backend. Drop photos into{" "}
              <code>face-embedder/data/enrollment/&lt;name&gt;/</code>, re-run enrollment, copy the resulting{" "}
              <code>identity_store.pkl</code> into <code>next-gen-backend/storage/models/</code>, then use "Reload
              from disk" on the other tab.
            </div>
            <div className="flex gap-[62px] flex-wrap">
              <div className="flex flex-col gap-3 w-[518px]">
                <label className="text-brand-navy text-[16px] font-medium">Full name</label>
                <div className="bg-brand-field border border-brand-border rounded-[5px] h-[52px] flex items-center px-5">
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Enter full name"
                    className="bg-transparent outline-none flex-1 text-[14px] placeholder:text-[#c6c6c6]"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-3 w-[518px]">
                <label className="text-brand-navy text-[16px] font-medium">Upload Image</label>
                <label className="bg-white border border-brand-border rounded-[5px] h-[52px] flex items-center gap-2 px-5 cursor-pointer w-fit opacity-60">
                  <img src={onboarding.uploadFile} alt="" className="w-6 h-6" />
                  <span className="text-[#606060] text-[12px] font-semibold">Upload you face</span>
                  <input type="file" accept="image/*" className="hidden" disabled />
                </label>
              </div>
            </div>

            <div className="flex gap-[60px] items-center flex-wrap">
              {[
                { key: "permanent", label: "Face Permeant" },
                { key: "staff", label: "Face - Staff and Workers" },
                { key: "visitor", label: "Face Temporary (Visitors)" },
              ].map((type) => (
                <label key={type.key} className="flex items-center gap-1.5 cursor-pointer">
                  <span
                    className={`size-3.5 rounded-full inline-block ${faceType === type.key ? "bg-brand-navy" : "border-2 border-brand-navy"}`}
                    onClick={() => setFaceType(type.key)}
                  />
                  <span className="text-brand-navy text-[14px]">{type.label}</span>
                </label>
              ))}
            </div>

            <button
              type="submit"
              disabled
              title="No backend endpoint for this yet — see the note above"
              className="bg-brand-red/40 cursor-not-allowed text-white font-bold text-[16px] rounded-[5px] h-[56px] w-[200px]"
            >
              Add
            </button>
          </form>
        ) : (
          <div className="flex flex-col gap-4 max-w-[900px]">
            <div className="flex items-center justify-between">
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
              <div className="bg-[#f2f2f2] h-[52px] flex items-center px-8 gap-40 text-[#4f4b61] text-[14px] font-medium">
                <p className="w-[300px]">Name</p>
                <p>Action</p>
              </div>
              {identities.length === 0 && <div className="px-8 py-10 text-[#9c9c9c] text-[13px]">No identities enrolled yet.</div>}
              {identities.map((name) => (
                <div key={name} className="flex items-center px-8 gap-40 h-[56px] border-t border-[#eee] text-[14px] text-[#221f54]">
                  <p className="w-[300px] font-medium">👤 {name}</p>
                  <button
                    disabled
                    title="No delete-identity endpoint on this backend yet"
                    className="text-brand-red/40 text-[14px] font-medium cursor-not-allowed"
                  >
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
