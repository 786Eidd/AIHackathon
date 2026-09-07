import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import { BackendProvider } from "./context/BackendContext.jsx";
import Toasts from "./components/Toasts.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BackendProvider>
      <App />
      <Toasts />
    </BackendProvider>
  </React.StrictMode>
);
