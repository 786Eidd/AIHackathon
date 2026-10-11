import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Listen on all interfaces so the dashboard opens from a phone on the LAN.
  server: { host: true, port: 5173 },
});
