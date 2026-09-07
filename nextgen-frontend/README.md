# NextGen Security & Management — Web App

Generated from the Figma file `NextGen-Project`, now fully wired to the real
NexGen FastAPI backend (`next-gen-backend/`).

## Run it

1. Start the backend first (see `next-gen-backend/README.md`):
   ```bash
   cd ../next-gen-backend
   .\.venv\Scripts\Activate.ps1
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
   ```
2. In this folder:
   ```bash
   npm install
   npm run dev
   ```
   Vite prints a local URL (typically `http://localhost:5173`) — open it.
3. On the Login screen, confirm the "Backend URL" field points at your
   backend (`http://localhost:8000` by default — copy `.env.example` to
   `.env.local` to change the default) and log in. There's no real
   authentication on the backend (see its README's Security Notes), so this
   screen only sets which API the app talks to.

## What's wired to the real backend

All of this is live, via `src/context/BackendContext.jsx` (REST + a
`ws://.../api/v1/ws/live` WebSocket for real-time push):

- `/cameras` — Live Cameras dashboard: real camera list, live status,
  detection chips (face/weapon) updating in real time, delete.
- `/cameras/:id` — Single camera live view: same live detections, plus an
  optional per-camera "live preview URL" (e.g. a Hikvision ISAPI snapshot
  endpoint) since the backend doesn't push raw video frames over the
  WebSocket, only detections/events/alerts.
- `/breach-alerts` — Active Breach / Logs tabs are real alerts from
  `GET /alerts`, live-updated over the WebSocket; "Take Action" calls
  `POST /alerts/{id}/ack`.
- `/camera-management` — Camera's List is the real camera list (host, FPS,
  status, location); Camera Configuration adds a camera by building an RTSP
  URL from IP/Port/User/Password/path and calling `POST /cameras`, or edits
  an existing one via `PATCH /cameras/{id}` (select one camera + "Modify").
- `/face-management` → "Manage Existing Faces" lists real identities from
  `GET /identities` with a working "Reload from disk" button
  (`POST /identities/reload`).
- `/settings` — General tab shows live `/health` telemetry (device, sample
  FPS, inference width, weapon-model status, Qwen chat status); Arm/unarm tab
  and the header's Arm/Unarm toggle bulk-start or bulk-stop every registered
  camera.
- Onboarding step 2 (camera configuration) registers a real camera the same
  way Camera Management does.

## What's intentionally NOT wired (the backend has no endpoint for it)

- **Face upload** (`/face-management` → "Add Face Details", onboarding step
  3): this backend enrolls faces offline — a script
  (`face-embedder/enroll.py`) builds `identity_store.pkl` from photo
  folders on disk. There's no HTTP upload endpoint, so that form is
  disabled with an explanatory note rather than silently doing nothing.
- **Complaints** (`/contact`): no ticketing API exists, so that list is
  kept in `localStorage` only — it won't sync anywhere else. Flagged in the
  UI.
- **Login itself**: cosmetic only, since the backend has no auth at all.

## Notes carried over from the original scaffold

1. Images/icons in `src/assets/figmaAssets.js` point to temporary
   Figma-hosted URLs that expire ~7 days after export. Before shipping,
   download these and swap the URLs for local files in `src/assets/`.
2. Tailwind CSS matches the Figma-generated styling. `npm install` pulls in
   `tailwindcss`, `postcss`, `autoprefixer`.
