import { useNavigate } from "react-router-dom";
import { useState } from "react";
import OnboardingSidebar from "../../components/OnboardingSidebar";
import { onboarding } from "../../assets/figmaAssets";

const faceTypes = [
  { key: "permanent", label: "Face Permeant", color: "border-2 border-brand-navy" },
  { key: "staff", label: "Face - Staff and Workers", color: "border-2 border-brand-navy" },
  { key: "visitor", label: "Face Temporary (Visitors)", color: "bg-brand-red" },
];

export default function Step3AddFaces() {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [faceType, setFaceType] = useState("permanent");

  return (
    <div className="flex min-h-screen bg-white">
      <OnboardingSidebar currentStep={3} />

      <div className="flex-1 flex flex-col items-center justify-center gap-8 px-8">
        <div className="flex flex-col items-center gap-2 w-[420px]">
          <h1 className="text-brand-navy text-[32px] font-bold">Add Faces</h1>
          <p className="text-[#474747] text-[14px] text-center">Please Add faces for security purposes</p>
        </div>

        <div className="bg-[#fff8e6] border border-[#f0dcae] text-[#8a6416] text-[11.5px] rounded-[6px] px-4 py-3 w-[522px] leading-relaxed">
          Face enrollment on this backend happens offline via a Python script, not through this form yet — fill it in
          to preview the flow, then run enrollment from <code>face-embedder/</code> and reload identities from
          Face Management once you've deployed the backend for real.
        </div>

        <form onSubmit={(e) => e.preventDefault()} className="flex flex-col items-center gap-[30px] w-full">
          <div className="flex flex-col gap-[18px] w-[522px]">
            <div className="flex flex-col gap-3">
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

            <div className="flex flex-col gap-3">
              <label className="text-brand-navy text-[16px] font-medium">Upload Image</label>
              <label className="bg-white border border-brand-border rounded-[5px] h-[52px] flex items-center gap-2 px-5 cursor-pointer w-fit opacity-60">
                <img src={onboarding.uploadFile} alt="" className="w-6 h-6" />
                <span className="text-[#606060] text-[12px] font-semibold">Upload you face</span>
                <input type="file" accept="image/*" className="hidden" disabled />
              </label>
            </div>

            <div className="flex flex-col gap-3">
              {faceTypes.map((type) => (
                <label key={type.key} className="flex items-center gap-1.5 cursor-pointer">
                  <span
                    className={`size-3.5 rounded-full inline-block ${faceType === type.key ? "bg-brand-navy" : type.color}`}
                    onClick={() => setFaceType(type.key)}
                  />
                  <span className="text-brand-navy text-[14px]">{type.label}</span>
                </label>
              ))}
            </div>
          </div>

          <button type="button" onClick={() => navigate("/onboarding/4")} className="bg-brand-red text-white font-bold text-[16px] rounded-[5px] h-[56px] w-[200px]">
            Next
          </button>
        </form>
      </div>
    </div>
  );
}
