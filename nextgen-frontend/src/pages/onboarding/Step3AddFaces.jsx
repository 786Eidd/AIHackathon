import { useNavigate } from "react-router-dom";
import OnboardingSidebar from "../../components/OnboardingSidebar";
import EnrollForm from "../../components/EnrollForm";

export default function Step3AddFaces() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen bg-white">
      <OnboardingSidebar currentStep={3} />

      <div className="flex-1 flex flex-col items-center justify-center gap-8 px-5 sm:px-8 py-10">
        <div className="flex flex-col items-center gap-2 w-full max-w-[420px]">
          <h1 className="text-brand-navy text-[32px] font-bold">Add Faces</h1>
          <p className="text-[#474747] text-[14px] text-center">
            Enroll the people who should be recognised. Anyone else is flagged as unknown.
          </p>
        </div>

        <div className="w-full max-w-[560px]">
          <EnrollForm />
        </div>

        <button type="button" onClick={() => navigate("/onboarding/4")} className="bg-brand-red text-white font-bold text-[16px] rounded-[5px] h-[56px] w-full max-w-[200px]">
          Next
        </button>
      </div>
    </div>
  );
}
