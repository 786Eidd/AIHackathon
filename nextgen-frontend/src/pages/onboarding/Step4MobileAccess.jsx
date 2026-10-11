import { useNavigate } from "react-router-dom";
import { useState } from "react";
import OnboardingSidebar from "../../components/OnboardingSidebar";
import { onboarding } from "../../assets/figmaAssets";

export default function Step4MobileAccess() {
  const navigate = useNavigate();
  const [accessType, setAccessType] = useState("remote");

  return (
    <div className="flex min-h-screen bg-white">
      <OnboardingSidebar currentStep={4} />

      <div className="flex-1 flex flex-col items-center justify-center gap-10 px-5 sm:px-8 py-10">
        <div className="flex flex-col items-center gap-2 w-full max-w-[502px]">
          <h1 className="text-brand-navy text-[32px] font-bold">Get access to you mobile</h1>
          <p className="text-[#474747] text-[14px] text-center">
            Please manage and control all in your mobile application
          </p>
        </div>

        <div className="flex gap-x-[60px] gap-y-3 flex-wrap justify-center">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <span
              className={`size-3.5 rounded-full inline-block ${
                accessType === "remote" ? "bg-brand-red" : "border-2 border-brand-navy"
              }`}
              onClick={() => setAccessType("remote")}
            />
            <span className="text-brand-navy text-[16px]">Remote Access</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <span
              className={`size-3.5 rounded-full inline-block ${
                accessType === "local" ? "bg-brand-red" : "border-2 border-brand-navy"
              }`}
              onClick={() => setAccessType("local")}
            />
            <span className="text-brand-navy text-[16px]">Local Access</span>
          </label>
        </div>

        <div className="flex flex-col items-center gap-10">
          <img src={onboarding.qrCode} alt="Scan to connect mobile app" className="size-[200px]" />
          <div className="flex gap-x-[43px] gap-y-3 flex-wrap justify-center">
            <img src={onboarding.appStore} alt="Download on the App Store" className="h-14 w-[200px] object-cover rounded-md" />
            <img src={onboarding.playStore} alt="Get it on Google Play" className="h-14 w-[200px] object-cover rounded-md" />
          </div>
        </div>

        <button
          type="button"
          onClick={() => navigate("/cameras")}
          className="bg-brand-red text-white font-bold text-[16px] rounded-[5px] h-[56px] w-full max-w-[200px]"
        >
          Get Started
        </button>
      </div>
    </div>
  );
}
