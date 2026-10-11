import { useNavigate } from "react-router-dom";
import { useState } from "react";
import OnboardingSidebar from "../../components/OnboardingSidebar";
import { onboarding } from "../../assets/figmaAssets";

export default function Step1ChangePassword() {
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  function handleNext(e) {
    e.preventDefault();
    navigate("/onboarding/2");
  }

  return (
    <div className="flex min-h-screen bg-white">
      <OnboardingSidebar currentStep={1} showBack={false} />

      <form onSubmit={handleNext} className="flex-1 flex flex-col items-center justify-center gap-10 px-5 sm:px-8 py-10">
        <div className="flex flex-col items-center gap-2 w-full max-w-[366px]">
          <h1 className="text-brand-navy text-[32px] font-bold">Change Your Password</h1>
          <p className="text-[#474747] text-[14px] text-center">
            Please choose your own password for more control
          </p>
        </div>

        <div className="flex flex-col gap-[18px] w-full max-w-[522px]">
          <div className="flex flex-col gap-3">
            <label className="text-brand-navy text-[16px] font-medium">New Password</label>
            <div className="flex items-center gap-2.5 bg-brand-field border border-brand-border rounded-[5px] h-[52px] px-5">
              <img src={onboarding.fieldLock} alt="" className="w-6 h-6" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter new password"
                className="bg-transparent outline-none flex-1 text-[14px] placeholder:text-[#c6c6c6]"
              />
            </div>
          </div>

          <div className="flex flex-col gap-3">
            <label className="text-brand-navy text-[16px] font-medium">Re- Enter Password</label>
            <div className="flex items-center gap-2.5 bg-brand-field border border-brand-border rounded-[5px] h-[52px] px-5">
              <img src={onboarding.fieldLock} alt="" className="w-6 h-6" />
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Re-enter new password"
                className="bg-transparent outline-none flex-1 text-[14px] placeholder:text-[#c6c6c6]"
              />
            </div>
          </div>
        </div>

        <button
          type="submit"
          className="bg-brand-red text-white font-bold text-[16px] rounded-[5px] h-[56px] w-full max-w-[200px]"
        >
          Next
        </button>
      </form>
    </div>
  );
}
