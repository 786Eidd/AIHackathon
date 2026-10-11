import { useNavigate } from "react-router-dom";
import { useState } from "react";
import OnboardingSidebar from "../../components/OnboardingSidebar";
import CameraForm from "../../components/CameraForm";
import DiscoveryPanel from "../../components/DiscoveryPanel";
import { useBackend } from "../../context/BackendContext";
import { buildStreamUrl, emptyCameraForm, validateCameraForm } from "../../lib/streamUrl";

export default function Step2CameraConfig() {
  const navigate = useNavigate();
  const { createCamera, pushToast } = useBackend();
  const [form, setForm] = useState(emptyCameraForm);
  const [added, setAdded] = useState(false);
  const [saving, setSaving] = useState(false);

  async function handleAddCamera(e) {
    e.preventDefault();
    const problem = validateCameraForm(form);
    if (problem) {
      pushToast("Missing fields", problem, "medium");
      return;
    }
    setSaving(true);
    try {
      await createCamera({ name: form.name, location: form.location || null, rtsp_url: buildStreamUrl(form), enabled: true });
      setAdded(true);
      pushToast("Camera added", form.name, "medium");
      setForm(emptyCameraForm);
    } catch (e) {
      pushToast("Could not add camera", e.message, "medium");
    }
    setSaving(false);
  }

  return (
    <div className="flex min-h-screen bg-white">
      <OnboardingSidebar currentStep={2} />

      <div className="flex-1 flex flex-col items-center justify-center gap-8 px-5 sm:px-8 py-10">
        <div className="flex flex-col items-center gap-2 w-full max-w-[480px]">
          <h1 className="text-brand-navy text-[32px] font-bold text-center">Camera configuration</h1>
          <p className="text-[#474747] text-[14px] text-center">Cameras on this network are found automatically. Connect them below, then continue.</p>
        </div>

        <div className="w-full max-w-[560px]">
          <DiscoveryPanel />
        </div>

        <p className="text-brand-navy text-[14px] font-semibold">Or add a camera by hand</p>

        <form onSubmit={handleAddCamera} className="flex flex-col items-center gap-[30px] w-full">
          <div className="w-full max-w-[560px]">
            <CameraForm form={form} setForm={setForm} />
          </div>

          <button
            type="submit"
            disabled={saving}
            className="border border-brand-navy text-brand-navy font-medium text-[14px] rounded-[5px] h-12 w-[200px] disabled:opacity-60"
          >
            {saving ? "Adding…" : "Add Camera"}
          </button>

          {added && (
            <div className="bg-[#deecff] text-brand-navy text-[14px] rounded-md py-3 px-4 w-full max-w-[486px] flex items-center justify-center text-center">
              Camera added. Add another one above, or continue.
            </div>
          )}

          <button type="button" onClick={() => navigate("/onboarding/3")} className="bg-brand-red text-white font-bold text-[16px] rounded-[5px] h-[56px] w-full max-w-[200px]">
            Next
          </button>
        </form>
      </div>
    </div>
  );
}
