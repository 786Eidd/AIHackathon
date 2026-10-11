import { useNavigate } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import CameraList from "../components/CameraList";

export default function LiveCameras() {
  const navigate = useNavigate();

  return (
    <DashboardLayout title="Live Cameras" actionLabel="Add new Camera" onAction={() => navigate("/camera-management")}>
      <CameraList />
    </DashboardLayout>
  );
}
