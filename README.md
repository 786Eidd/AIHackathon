<div align="center">

<img src="docs/assets/nexgen-logo.png" alt="NexGen Security & Management" width="260"/>

# NexGen AI Surveillance

**Turn the cameras you already own into a live, AI-powered monitoring system.**

Real-time face recognition and weapon detection over existing RTSP CCTV / DVR / NVR
feeds — no new hardware required.

<img src="docs/assets/hackathon-badge.png" alt="AI Hackathon Pakistan" width="64"/>

Built for **AI Hackathon Pakistan** · Submission **P01601**

</div>

---

## Table of contents

1. [Overview](#overview)
2. [Key features](#key-features)
3. [System architecture](#system-architecture)
4. [Repository structure](#repository-structure)
5. [Tech stack](#tech-stack)
6. [Getting started](#getting-started)
7. [Alibaba Cloud integration](#alibaba-cloud-integration)
8. [API & WebSocket overview](#api--websocket-overview)
9. [What's wired vs. what's cosmetic](#whats-wired-vs-whats-cosmetic)
10. [Security notes](#security-notes)
11. [Roadmap](#roadmap)
12. [Author](#author)

---

## Overview

Most CCTV/DVR/NVR installations (Hikvision and similar) only **record** — nobody
is notified until footage is reviewed after the fact, and watching 8+ live
feeds around the clock for a face or a weapon isn't a job a human can sustain
accurately. Replacing that hardware with "smart cameras" is expensive.

**NexGen AI Surveillance** sits in front of the cameras you already have. It
pulls live RTSP streams from up to 8 cameras at once, runs face recognition
and weapon detection on every sampled frame, tracks events as they unfold, and
pushes prioritized alerts to a React dashboard in real time over WebSocket —
all on ordinary hardware, no GPU required.

## Key features

- **Live multi-camera grid** — every connected camera at once, with live
  detection chips overlaid as they happen.
- **Real-time breach alerts** — prioritized alerts stream over WebSocket the
  moment an event is confirmed; acknowledge straight from the dashboard.
- **Camera management** — add, edit, and remove Hikvision RTSP cameras; a
  built-in URL builder assembles the RTSP string from IP/port/credentials.
- **Face identity registry** — enrolled identities are matched live against
  every camera feed; unmatched faces are flagged and clustered as "unknown".
- **Event timeline & clips** — every open/close of an event is recorded with
  its snapshot, ready for AI-generated summaries.
- **One dashboard, any device** — a React + Tailwind frontend fully wired to
  the live backend, no mock data.

## System architecture

```mermaid
flowchart LR
    subgraph CAMS["📷 Existing Cameras"]
        direction TB
        C1["Camera 1<br/>Hikvision · RTSP"]
        C2["Camera 2<br/>Hikvision · RTSP"]
        CN["Camera N<br/>up to 8 total"]
    end

    subgraph PIPE["Per-Camera Pipeline (× N)"]
        direction TB
        CAP["RTSP Capture Thread<br/><small>OpenCV · continuous read</small>"]
        SAMP["Frame Sampler<br/><small>target FPS · resize</small>"]
        FACE["Face Recognition<br/><small>MTCNN + FaceNet</small>"]
        WEAP["Weapon Detection<br/><small>YOLO · Ultralytics</small>"]
        FUSE["Tracker / Fusion Engine<br/><small>opens &amp; closes events</small>"]
        CAP --> SAMP
        SAMP --> FACE
        SAMP --> WEAP
        FACE --> FUSE
        WEAP --> FUSE
    end

    subgraph CORE["FastAPI Core Backend"]
        direction TB
        EVT["Event &amp; Alert Engine<br/><small>priority · cooldowns</small>"]
        DB[("SQLite Database<br/><small>Camera · Event · Alert · Identity</small>")]
        WS["WebSocket Broadcaster<br/><small>/api/v1/ws/live</small>"]
        REST["REST API<br/><small>/api/v1/*</small>"]
        EVT --> DB
        DB --> REST
        EVT --> WS
    end

    subgraph CLOUD["☁️ Alibaba Cloud"]
        direction TB
        OSS["Object Storage Service<br/><small>model weights · clips · snapshots</small>"]
        QWEN["DashScope · Qwen<br/><small>Qwen-VL event analysis<br/>Qwen-Text chat &amp; summaries</small>"]
    end

    subgraph FRONT["React Dashboard"]
        direction TB
        LOGIN["Login"]
        LIVE["Live Cameras (grid)"]
        VIEW["Camera Live View"]
        ALERTS["Breach Alerts"]
        MGMT["Camera Management"]
        FACES["Face Management"]
        SET["Settings"]
    end

    C1 -->|RTSP| CAP
    C2 -->|RTSP| CAP
    CN -->|RTSP| CAP

    FUSE -->|event opened/closed| EVT
    EVT -->|upload clips/snapshots| OSS
    EVT -.->|event image → description| QWEN
    REST -.->|chat query| QWEN

    WS -->|live detections &amp; alerts| FRONT
    REST -->|REST · CRUD, config, chat| FRONT

    classDef cam fill:#FFFFFF,stroke:#E3E3E3,color:#221F54,stroke-width:1.5px
    classDef pipe fill:#F4F3FA,stroke:#E3E3E3,color:#221F54,stroke-width:1.5px
    classDef detect fill:#221F54,stroke:#221F54,color:#FFFFFF,stroke-width:1.5px
    classDef alert fill:#DA3F3F,stroke:#DA3F3F,color:#FFFFFF,stroke-width:1.5px
    classDef core fill:#F4F3FA,stroke:#E3E3E3,color:#221F54,stroke-width:1.5px
    classDef ws fill:#221F54,stroke:#221F54,color:#FFFFFF,stroke-width:1.5px
    classDef cloud fill:#EAF6F7,stroke:#0F6E7A,color:#0F6E7A,stroke-width:1.5px
    classDef front fill:#F4F3FA,stroke:#E3E3E3,color:#221F54,stroke-width:1.5px

    class C1,C2,CN cam
    class CAP,SAMP,FUSE pipe
    class FACE,WEAP detect
    class EVT alert
    class DB,REST core
    class WS ws
    class OSS,QWEN cloud
    class LOGIN,LIVE,VIEW,ALERTS,MGMT,FACES,SET front
```

Each camera runs on two threads (capture + analyzer) so a slow detector never
lets latency drift — frames are dropped, not queued. Models are loaded once
and shared across all cameras, which is why the backend must run as a single
process (`--workers 1`). See [`next-gen-backend/README.md`](next-gen-backend/README.md#how-it-works)
for the full breakdown.

## Repository structure

```
.
├── next-gen-backend/     FastAPI service — RTSP capture, face + weapon
│                         detection, event/alert engine, REST + WebSocket API
├── nextgen-frontend/     React 18 + Vite + Tailwind dashboard, fully wired
│                         to the backend (no mock data)
├── face-embedder/        Offline face enrollment tooling — builds the
│                         identity_store.pkl the backend matches against
└── docs/assets/          Logos and diagram assets used in this README
```

Each module has its own detailed README — start here, then drill into
[`next-gen-backend/README.md`](next-gen-backend/README.md) or
[`nextgen-frontend/README.md`](nextgen-frontend/README.md) for specifics.

## Tech stack

| Layer | Technologies |
|---|---|
| **Backend** | FastAPI + Uvicorn · SQLAlchemy + SQLite · OpenCV (RTSP capture) · facenet-pytorch (MTCNN + FaceNet) · Ultralytics YOLO (weapon detection) · WebSocket broadcaster |
| **Frontend** | React 18 + Vite · Tailwind CSS · React Router 6 · Context-based live state · auto-reconnecting WebSocket client |
| **Alibaba Cloud** | Object Storage Service (OSS) · DashScope — Qwen-VL · DashScope — Qwen (text / chat) |
| **Face enrollment** | MTCNN detection/alignment · FaceNet (InceptionResnetV1) embeddings · pickle-backed identity store |

## Getting started

### 1. Backend

```bash
cd next-gen-backend
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

`--workers 1` is mandatory — models are loaded once and shared across every
camera's capture thread. Check it's alive:

```bash
curl http://localhost:8000/api/v1/health
```

Interactive API docs: **http://localhost:8000/docs**

Full configuration reference, Docker instructions, model setup, and face
enrollment steps live in [`next-gen-backend/README.md`](next-gen-backend/README.md).

### 2. Frontend

```bash
cd nextgen-frontend
npm install
npm run dev
```

Vite prints a local URL (typically `http://localhost:5173`). On the Login
screen, confirm the **Backend URL** field points at your backend
(`http://localhost:8000` by default).

### 3. Register a camera

Cameras aren't configured via `.env` — register them over the API (or from
the Camera Management screen in the dashboard):

```bash
curl -X POST http://localhost:8000/api/v1/cameras \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "Lobby",
        "rtsp_url": "rtsp://admin:pass@192.168.1.50:554/Streaming/Channels/101",
        "location": "Ground floor, main entrance",
        "enabled": true
      }'
```

### 4. Enroll faces (optional, offline)

Face recognition needs an identity store built from reference photos —
see [`face-embedder/face-embedder-2/README.md`](face-embedder/face-embedder-2/README.md)
and the backend's [Enrolling faces](next-gen-backend/README.md#enrolling-faces)
section.

## Alibaba Cloud integration

| Service | Used for |
|---|---|
| **Object Storage Service (OSS)** | Stores model weights and event clip/snapshot artifacts, served back to clients via signed URLs |
| **DashScope · Qwen-VL** | Generates natural-language descriptions of detected events |
| **DashScope · Qwen (text)** | Powers the `/chat` endpoint — ask questions about recent camera activity in plain language |

Both are entirely optional at runtime: without `DASHSCOPE_API_KEY`, face and
weapon detection still work fully — you only lose scene descriptions and
chat. Without OSS configured, the backend falls back to local file storage
for snapshots and clips.

## API & WebSocket overview

Base path: `/api/v1`. Full reference in
[`next-gen-backend/README.md`](next-gen-backend/README.md#api-reference).

| Method | Path | Notes |
|---|---|---|
| `GET` | `/health` | Device, loaded models, running cameras, WS subscribers |
| `GET`/`POST` | `/cameras` | List / register cameras |
| `GET` | `/cameras/status` | Live pipeline telemetry (FPS, drops, reconnects) |
| `GET` | `/events` | Filterable event history |
| `GET` | `/alerts` · `POST /alerts/{id}/ack` | Alerts + acknowledgement |
| `GET`/`POST` | `/identities` · `/identities/reload` | Enrolled identities |
| `POST` | `/chat` | Ask about recent activity (requires DashScope key) |
| `WS` | `/ws/live` | Real-time push: detections, events, alerts, camera status |

## What's wired vs. what's cosmetic

The frontend is honest about what the backend can actually do — nothing is
silently faked:

- **Fully live**: camera list/status, live detection chips, breach alerts +
  acknowledgement, camera CRUD, identity list + reload, `/health` telemetry,
  arm/unarm.
- **Intentionally not wired** (no backend endpoint exists yet): face-photo
  upload (enrollment is an offline script, see above), complaint ticketing
  (kept in `localStorage` only), and login (the backend has no
  authentication — see Security notes).

## Security notes

Read before exposing this beyond a local demo:

- **No authentication** — every endpoint, including camera CRUD, is open.
- **CORS defaults to `*`** — restrict `CORS_ORIGINS` in production.
- **RTSP credentials are stored in plaintext** and echoed back by the camera
  endpoints.
- The identity store is a **pickle file** — only load ones you generated.
- Face recognition and stored footage are regulated in many jurisdictions
  (GDPR, BIPA, and others); enrollment implies consent obligations.

## Roadmap

- **Now** — full RTSP pipeline, face + weapon detection, live React
  dashboard, Alibaba Cloud storage & AI reasoning integrated.
- **Next** — face enrollment directly from the dashboard; broader
  camera-brand support beyond Hikvision's ISAPI conventions.
- **Later** — mobile app access, edge deployment for offline sites, and
  role-based access for multi-site security teams.

## Author

**Eid Muhammad** — AI Engineer
[github.com/786Eidd](https://github.com/786Eidd) ·
[linkedin.com/in/eidmo](https://linkedin.com/in/eidmo)

Built for **AI Hackathon Pakistan** · Submission **P01601**
