// Local, self-contained assets. These used to be temporary Figma-hosted URLs
// that expired a week after export; everything here is now either a file in
// /public or an inline SVG, so the UI has no external image dependencies.

function icon(body, { stroke = "#4f4b61", fill = "none", width = 2 } = {}) {
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="${fill}" stroke="${stroke}" ` +
    `stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

function image(svg) {
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

const NAVY = "#221f54";
const RED = "#da3f3f";
const GRAY = "#848295";

const paths = {
  video: '<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/>',
  activity: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
  alert:
    '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
  camera:
    '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>',
  faceId:
    '<path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"/><circle cx="12" cy="10" r="2.5"/><path d="M8 16c.8-1.6 2.3-2.4 4-2.4s3.2.8 4 2.4"/>',
  message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  sliders:
    '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>',
  radio: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.5" fill="#ffffff"/>',
  bell: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
  user: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  logout:
    '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
  eye: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
  trash:
    '<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>',
  lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  chevronUp: '<polyline points="18 15 12 9 6 15"/>',
  upload:
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
  calendar:
    '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
  phone: '<rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/>',
};

export const logo = "/nexgen-logo.svg";
export const loginLogo = "/nexgen-logo.svg";

export const icons = {
  liveStreaming: icon(paths.video),
  activity: icon(paths.activity),
  breachAlert: icon(paths.alert),
  cameraManagement: icon(paths.camera),
  faceId: icon(paths.faceId),
  contact: icon(paths.message),
  settings: icon(paths.sliders),
  radioChecked: icon(paths.radio, { stroke: "#ffffff" }),
  bell: icon(paths.bell, { stroke: GRAY }),
  avatar: icon(paths.user, { stroke: GRAY }),
  logout: icon(paths.logout, { stroke: GRAY }),
  viewCamera: icon(paths.eye, { stroke: "#ffffff" }),
  deleteIcon: icon(paths.trash, { stroke: RED }),
  user: icon(paths.user, { stroke: "#9c9c9c" }),
  lock: icon(paths.lock, { stroke: "#9c9c9c" }),
};

// Photo used on the login / onboarding side panel.
export const loginHero = "/login-hero.webp";

export const logoIcon = "/nexgen-icon.svg";

export const onboarding = {
  logo: "/nexgen-logo.svg",
  lockActive: icon(paths.lock, { stroke: NAVY }),
  lockInactive: icon(paths.lock, { stroke: "#838386" }),
  cameraConfigActive: icon(paths.camera, { stroke: NAVY }),
  cameraConfigInactive: icon(paths.camera, { stroke: "#838386" }),
  faceId: icon(paths.faceId, { stroke: NAVY }),
  apiApp: icon(paths.phone, { stroke: NAVY }),
  backArrow: icon(paths.chevronUp, { stroke: NAVY }),
  fieldLock: icon(paths.lock, { stroke: "#9c9c9c" }),
  uploadFile: icon(paths.upload, { stroke: "#606060" }),
  calendar: icon(paths.calendar, { stroke: "#606060" }),
  // There is no mobile app yet, so this is a labelled placeholder rather
  // than a QR code that would scan to nothing.
  qrCode: image(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
      <rect x="2" y="2" width="196" height="196" rx="12" fill="#fbfbfb" stroke="#e3e3e3" stroke-width="2" stroke-dasharray="8 6"/>
      <g transform="translate(76 52) scale(2)" fill="none" stroke="${NAVY}" stroke-width="1.6" stroke-linecap="round">${paths.phone}</g>
      <text x="100" y="138" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="${NAVY}">Mobile app</text>
      <text x="100" y="158" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#838386">coming soon</text>
    </svg>`
  ),
  appStore: storeBadge("App Store"),
  playStore: storeBadge("Google Play"),
};

function storeBadge(name) {
  return image(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 56">
      <rect width="200" height="56" rx="8" fill="#d9d9de"/>
      <text x="100" y="24" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#6a6888">Coming soon to</text>
      <text x="100" y="42" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#4f4b61">${name}</text>
    </svg>`
  );
}
