import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { loginHero, loginLogo, icons } from "../assets/figmaAssets";
import { useBackend } from "../context/BackendContext";

export default function Login() {
  const navigate = useNavigate();
  const { baseUrl, connect, pushToast } = useBackend();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [url, setUrl] = useState(baseUrl);
  const [checking, setChecking] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setChecking(true);
    const result = await connect(url);
    setChecking(false);
    if (!result.ok) {
      pushToast("Could not reach backend", "Check the URL and that uvicorn is running.", "high");
      return;
    }
    navigate("/onboarding/1");
  }

  return (
    <div className="flex min-h-screen bg-white">
      <div className="relative w-[45%] min-w-[500px] bg-[#e1e1e1] hidden lg:block">
        <img src={loginHero} alt="Security cameras" className="absolute inset-0 h-full w-full object-cover" />
        <img
          src={loginLogo}
          alt="NexGen Security & Management"
          className="absolute top-[40px] left-1/2 -translate-x-1/2 w-[320px] bg-white/85 rounded-[10px] px-5 py-3"
        />
        <div className="absolute bottom-0 left-0 right-0 h-[44px] bg-white/50 flex items-center justify-center">
          <p className="text-brand-navy text-[13px] font-semibold">Copyright © 2026 NexGen. All Rights Reserved</p>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center px-5 sm:px-8 py-8">
        <form onSubmit={handleSubmit} className="w-full max-w-[522px] flex flex-col gap-10">
          <img src={loginLogo} alt="NexGen Security & Management" className="h-[56px] w-auto self-start lg:hidden" />
          <div>
            <h1 className="text-brand-navy text-[30px] font-bold">Login</h1>
            <p className="text-brand-gray text-[18px]">Enter your information below</p>
          </div>

          <div className="flex flex-col gap-[18px]">
            <div className="flex flex-col gap-3">
              <label className="text-brand-navy text-[16px] font-medium">Username</label>
              <div className="flex items-center gap-2 bg-brand-field border border-brand-border rounded-[5px] h-[52px] px-4">
                <img src={icons.user} alt="" className="w-[22px] h-6" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username"
                  className="bg-transparent outline-none flex-1 text-[14px] placeholder:text-[#c6c6c6]"
                />
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <label className="text-brand-navy text-[16px] font-medium">Password</label>
              <div className="flex items-center gap-2 bg-brand-field border border-brand-border rounded-[5px] h-[52px] px-4">
                <img src={icons.lock} alt="" className="w-6 h-6" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  className="bg-transparent outline-none flex-1 text-[14px] placeholder:text-[#c6c6c6]"
                />
              </div>
            </div>

            <div className="flex flex-col gap-3 pt-2 border-t border-dashed border-brand-border">
              <label className="text-brand-navy text-[13px] font-medium mt-2">Backend URL</label>
              <div className="flex items-center gap-2 bg-brand-field border border-brand-border rounded-[5px] h-[46px] px-4">
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="http://localhost:8000"
                  className="bg-transparent outline-none flex-1 text-[13px] placeholder:text-[#c6c6c6]"
                />
              </div>
              <p className="text-[11.5px] text-brand-gray leading-relaxed">
                This backend ships with no authentication (see its README's Security Notes) — the username/password
                above aren't checked against anything real, this is only where you point the app at your running
                NexGen API before continuing.
              </p>
            </div>
          </div>

          <button
            type="submit"
            disabled={checking}
            className="bg-brand-red hover:opacity-90 disabled:opacity-60 transition-opacity text-white font-bold text-[16px] rounded-[5px] h-[56px] w-full"
          >
            {checking ? "Connecting…" : "Login"}
          </button>
        </form>
      </div>
    </div>
  );
}
