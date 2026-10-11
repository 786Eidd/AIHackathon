import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Step1ChangePassword from "./pages/onboarding/Step1ChangePassword";
import Step2CameraConfig from "./pages/onboarding/Step2CameraConfig";
import Step3AddFaces from "./pages/onboarding/Step3AddFaces";
import Step4MobileAccess from "./pages/onboarding/Step4MobileAccess";
import LiveCameras from "./pages/LiveCameras";
import BreachAlerts from "./pages/BreachAlerts";
import CameraManagement from "./pages/CameraManagement";
import FaceManagement from "./pages/FaceManagement";
import Contact from "./pages/Contact";
import Settings from "./pages/Settings";
import CameraLiveView from "./pages/CameraLiveView";
import Events from "./pages/Events";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/onboarding/1" element={<Step1ChangePassword />} />
        <Route path="/onboarding/2" element={<Step2CameraConfig />} />
        <Route path="/onboarding/3" element={<Step3AddFaces />} />
        <Route path="/onboarding/4" element={<Step4MobileAccess />} />
        <Route path="/onboarding" element={<Navigate to="/onboarding/1" replace />} />

        <Route path="/cameras" element={<LiveCameras />} />
        <Route path="/cameras/:id" element={<CameraLiveView />} />
        <Route path="/breach-alerts" element={<BreachAlerts />} />
        <Route path="/events" element={<Events />} />
        <Route path="/camera-management" element={<CameraManagement />} />
        <Route path="/face-management" element={<FaceManagement />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/settings" element={<Settings />} />

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
