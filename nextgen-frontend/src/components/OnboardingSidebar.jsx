import { useNavigate } from "react-router-dom";
import { loginHero } from "../assets/figmaAssets";
import { onboarding } from "../assets/figmaAssets";

const steps = [
  { num: 1, icon: onboarding.lockActive, title: "Change Password", subtitle: "Select your own password" },
  { num: 2, icon: onboarding.cameraConfigActive, title: "Camera configuration", subtitle: "Configure your IP cameras" },
  { num: 3, icon: onboarding.faceId, title: "Add Faces", subtitle: "Add your face control" },
  { num: 4, icon: onboarding.apiApp, title: "App Integration", subtitle: "Manage everything through your mobile" },
];

export default function OnboardingSidebar({ currentStep, showBack = true }) {
  const navigate = useNavigate();

  return (
    <div className="relative w-[45%] min-w-[500px] bg-[#f5f5f5] hidden lg:flex flex-col justify-between overflow-hidden">
      <img src={loginHero} alt="" className="absolute inset-0 h-full w-full object-cover opacity-[0.10]" />

      <div className="relative flex flex-col items-center pt-[70px]">
        <img src={onboarding.logo} alt="NextGen" className="w-[350px]" />

        <div className="flex flex-col gap-6 mt-[90px] w-[238px]">
          {steps.map((step, i) => {
            const isActive = step.num === currentStep;
            const isDone = step.num < currentStep;
            return (
              <div key={step.num} className="relative">
                {i > 0 && (
                  <span className="absolute -top-6 left-5 h-6 w-px bg-[#e1e1e1]" aria-hidden />
                )}
                <div className="flex items-center justify-between">
                  <div
                    className={`size-10 rounded-md border flex items-center justify-center shrink-0 ${
                      isActive || isDone ? "border-[#e1e1e1] bg-white" : "border-[#e1e1e1] bg-white"
                    }`}
                  >
                    <img src={step.icon} alt="" className="w-6 h-6" />
                  </div>
                  <div className={`w-[189px] ${isActive ? "text-brand-navy" : "text-[#838386]"}`}>
                    <p className="text-[14px] font-medium capitalize">{step.title}</p>
                    <p className="text-[12px]">{step.subtitle}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="relative flex items-center justify-between px-[90px] pb-[90px]">
        {showBack ? (
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="flex items-center gap-1 text-brand-navy text-[14px]"
          >
            <img src={onboarding.backArrow} alt="" className="w-6 h-6 -rotate-90" />
            Back
          </button>
        ) : (
          <span />
        )}
        <button
          type="button"
          onClick={() => navigate("/cameras")}
          className="text-brand-navy text-[14px] underline"
        >
          Skip Now
        </button>
      </div>
    </div>
  );
}
