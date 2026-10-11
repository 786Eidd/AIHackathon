// Builds and parses camera source URLs for the camera form.
//
// The backend accepts anything OpenCV/FFmpeg can open plus webcam://N, so the
// form offers presets for the common cases and a raw "custom" escape hatch.

export const SOURCE_TYPES = [
  { key: "hikvision", label: "Hikvision (RTSP)" },
  { key: "webcam", label: "This PC's webcam" },
  { key: "mobile", label: "Mobile phone" },
  { key: "custom", label: "Custom URL" },
];

export const emptyCameraForm = {
  name: "",
  location: "",
  source: "hikvision",
  ip: "",
  port: "554",
  user: "admin",
  pass: "",
  channel: "1",
  stream: "sub",
  device: "0",
  url: "",
};

function authPart(user, pass) {
  if (!user) return "";
  // Passwords routinely contain @ : / # which would otherwise corrupt the URL.
  return `${encodeURIComponent(user)}:${encodeURIComponent(pass || "")}@`;
}

export function buildStreamUrl(form) {
  switch (form.source) {
    case "webcam":
      return `webcam://${form.device || "0"}`;
    case "mobile":
      // Android "IP Webcam" app serves MJPEG at /video on port 8080.
      return `http://${authPart(form.user, form.pass)}${form.ip.trim()}:${form.port || "8080"}/video`;
    case "custom":
      return form.url.trim();
    default: {
      // Hikvision: channel N main stream = N01, sub stream = N02.
      const id = `${form.channel || "1"}0${form.stream === "main" ? "1" : "2"}`;
      return `rtsp://${authPart(form.user, form.pass)}${form.ip.trim()}:${form.port || "554"}/Streaming/Channels/${id}`;
    }
  }
}

function safeDecode(value) {
  try {
    return decodeURIComponent(value);
  } catch (e) {
    return value;
  }
}

export function parseStreamUrl(url) {
  const base = { ...emptyCameraForm, user: "", url: url || "" };
  const value = (url || "").trim();

  if (/^webcam:\/\/\d+$/i.test(value)) {
    return { ...base, source: "webcam", device: value.slice(9) };
  }

  let parsed;
  try {
    parsed = new URL(value.replace(/^rtsps?:/i, "http:"));
  } catch (e) {
    return { ...base, source: "custom" };
  }

  const common = {
    ip: parsed.hostname,
    user: safeDecode(parsed.username),
    pass: safeDecode(parsed.password),
  };

  const hik = /^\/Streaming\/Channels\/(\d+)0([12])\/?$/i.exec(parsed.pathname);
  if (/^rtsp:/i.test(value) && hik && !parsed.search) {
    return {
      ...base,
      ...common,
      source: "hikvision",
      port: parsed.port || "554",
      channel: hik[1],
      stream: hik[2] === "1" ? "main" : "sub",
    };
  }

  if (/^http:/i.test(value) && parsed.pathname === "/video" && !parsed.search) {
    return { ...base, ...common, source: "mobile", port: parsed.port || "8080" };
  }

  // Anything else (Dahua query strings, RTMP, HTTPS...) is kept verbatim so
  // editing never silently rewrites it.
  return { ...base, source: "custom" };
}

export function hostOf(url) {
  const value = url || "";
  if (/^webcam:\/\//i.test(value)) return `Local webcam ${value.slice(9)}`;
  try {
    return new URL(value.replace(/^[a-z]+:/i, "http:")).host || "—";
  } catch (e) {
    return "—";
  }
}

export function validateCameraForm(form) {
  if (!form.name.trim()) return "Name is required.";
  if (form.source === "custom") {
    return form.url.trim() ? null : "Stream URL is required.";
  }
  if (form.source === "webcam") return null;
  return form.ip.trim() ? null : "IP address is required.";
}
