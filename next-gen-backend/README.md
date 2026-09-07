# NexGen AI Surveillance — Backend

Turns existing CCTV/DVR/NVR cameras into an AI monitoring system. The service
pulls **N live RTSP streams** continuously, runs face recognition and weapon
detection on each, tracks events as they unfold, and pushes alerts to clients
over WebSocket in real time.

This backend analyses **live streams only**. There is no upload-a-video-file
endpoint.

---

## Table of contents

1. [How it works](#how-it-works)
2. [Requirements](#requirements)
3. [Quick start (Docker)](#quick-start-docker)
4. [Quick start (bare metal / Jetson)](#quick-start-bare-metal--jetson)
5. [Configuration](#configuration)
6. [Setting up the models](#setting-up-the-models)
7. [Enrolling faces](#enrolling-faces)
8. [Registering cameras](#registering-cameras)
9. [API reference](#api-reference)
10. [WebSocket protocol](#websocket-protocol)
11. [Events and alerts](#events-and-alerts)
12. [Tuning for your hardware](#tuning-for-your-hardware)
13. [Verification](#verification)
14. [Troubleshooting](#troubleshooting)
15. [Security notes](#security-notes)

---

## How it works

Each camera gets **two threads**:

```
RTSP camera ──▶ capture thread ──▶ [latest frame slot] ──▶ analyzer thread ──▶ events
                (drains socket                            (samples at
                 at full rate)                             STREAM_SAMPLE_FPS)
```

- The **capture thread** reads as fast as the camera sends, keeping only the
  newest frame. If inference is slow, frames are **dropped** rather than
  queued — latency stays flat instead of drifting minutes behind reality.
- The **analyzer thread** samples that slot at `STREAM_SAMPLE_FPS`, runs the
  detectors, and feeds a per-camera event tracker.

Models are loaded **once** and shared by every camera behind locks. This is why
the service must run as a **single process** (`--workers 1`): a second worker
would load a second copy of the models and start duplicate capture threads,
producing duplicate events.

Events are tracked as an online state machine. An appearance **opens** an event
(so alerts fire immediately, not after the subject leaves) and **closes** it
once the subject has been absent for `EVENT_GAP_SECONDS`.

Raw per-frame detections are **not** written to the database — they live in a
bounded in-memory ring buffer per camera. Only **events** and **alerts** are
persisted.

---

## Requirements

| | Minimum | Recommended |
|---|---|---|
| Device | Raspberry Pi 5 (8 GB), CPU-only | NVIDIA Jetson Orin / any CUDA GPU |
| Python | 3.10+ | 3.11 / 3.12 |
| Cameras | 1 | 5–8 per device (default `MAX_CAMERAS=8`) |
| Also needed | `ffmpeg` (RTSP demuxing) | + NVIDIA Container Toolkit for Docker GPU |

Cameras must expose an **RTSP** (or RTMP/HTTP) URL. Most DVR/NVRs do; check the
vendor's manual for the path format, e.g.
`rtsp://user:pass@192.168.1.50:554/Streaming/Channels/101` (Hikvision) or
`rtsp://user:pass@192.168.1.50:554/cam/realmonitor?channel=1&subtype=0` (Dahua).

---

## Quick start (Docker)

```bash
# 1. Configure. The repo ships a ready-to-edit .env with LOCAL paths, and a
#    .env.docker template with container paths (/app/storage/...).
#    docker compose reads .env, so for a container run copy the template over:
cp .env.docker .env
```

Then edit `.env`:

- **Storage** — `.env.docker` sets `STORAGE_BACKEND=oss`. Either fill in the
  `OSS_*` values, or switch to `STORAGE_BACKEND=local` to keep snapshots and
  clips on the mounted volume.
- **`DASHSCOPE_API_KEY`** — only needed for the VLM features. Detection works
  without it.
- **Keep the `/app/storage/...` paths.** They land on the mounted volume and
  therefore survive a rebuild; a relative path like `./nexgen.db` would be
  written inside the container and lost.

```bash
# 2. (Optional) Pull models down from OSS, if you keep them there.
docker compose --profile setup run --rm download-models

# 3. Start.
docker compose up -d --build

# 4. Check it is alive.
curl http://localhost:8000/api/v1/health
```

Open **http://localhost:8000/docs** for interactive API docs.

### Reaching cameras on your LAN

Cameras usually sit on the same network as the host. If the container cannot
reach them, uncomment this line in `docker-compose.yml`:

```yaml
    # network_mode: host
```

Note that `network_mode: host` and `ports:` are mutually exclusive — with host
networking the service is already on the host's port 8000.

### GPU

`docker-compose.yml` already requests all NVIDIA GPUs. On a machine without
one, remove the `deploy.resources.reservations.devices` block or set
`DEVICE=cpu` in `.env`.

The first boot loads models and can take a couple of minutes; the healthcheck
allows for this via `start_period: 120s`.

---

## Quick start (bare metal / Jetson)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

# The .env in the repo is already set up for a local run (SQLite in the
# project root, local file storage). Add DASHSCOPE_API_KEY if you want the
# VLM features; nothing else is required to start.

uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

> **On Jetson**, do **not** install `torch`/`torchvision` from PyPI — they have
> no CUDA support for aarch64. Use NVIDIA's JetPack wheels, then install the
> rest of `requirements.txt` without them.

**`--workers 1` is mandatory.** See [How it works](#how-it-works).

The SQLite schema is created automatically on startup. There are no migrations.

---

## Configuration

Everything is set through environment variables (or a `.env` file). `.env` is
the fully commented reference — read it. `.env.docker` is the same set tuned
for containers (absolute `/app/...` paths, OSS storage).

### Core

| Variable | Default | Notes |
|---|---|---|
| `DEVICE` | `auto` | `auto` \| `cuda` \| `cpu` |
| `DATABASE_URL` | `sqlite:///./nexgen.db` | SQLite on edge; PostgreSQL for a central server |
| `STORAGE_BACKEND` | `local` | `local` \| `oss` — where snapshots/clips go |
| `LOCAL_STORAGE_DIR` | `storage` | Used when backend is `local` |
| `LOG_LEVEL` / `LOG_JSON` | `INFO` / `true` | JSON logs include a request id |
| `CORS_ORIGINS` | `*` | Comma-separated, or `*` |

### Streaming

| Variable | Default | What it does |
|---|---|---|
| `MAX_CAMERAS` | `8` | Hard cap; starting one more returns HTTP 409 |
| `AUTO_START_CAMERAS` | `true` | Restart all `enabled` cameras on boot |
| `STREAM_SAMPLE_FPS` | `3.0` | Frames/sec analysed **per camera** |
| `STREAM_INFERENCE_WIDTH` | `960` | Downscale width for inference; `0` disables. **Biggest performance lever** |
| `STREAM_RTSP_TRANSPORT` | `tcp` | `tcp` is reliable, `udp` is lower latency |
| `STREAM_SOCKET_TIMEOUT_SECONDS` | `10.0` | RTSP socket timeout |
| `STREAM_READ_STALL_SECONDS` | `15.0` | Socket open but no frames → reconnect |
| `STREAM_RECONNECT_INITIAL_SECONDS` | `2.0` | Backoff start |
| `STREAM_RECONNECT_MAX_SECONDS` | `60.0` | Backoff ceiling |
| `INFERENCE_MAX_CONCURRENT` | `2` | Concurrent detector calls across **all** cameras |

### Event tracking

| Variable | Default | What it does |
|---|---|---|
| `EVENT_GAP_SECONDS` | `3.0` | Absence before an appearance is closed out |
| `ALERT_COOLDOWN_SECONDS` | `30.0` | Suppresses repeat alerts of the same type per camera |
| `UNKNOWN_TRACK_TTL_SECONDS` | `120.0` | How long an `unknown_N` label is remembered |
| `UNKNOWN_FACE_CLUSTER_THRESHOLD` | `0.56` | Similarity for "same stranger" |
| `LIVE_DETECTION_BUFFER_SIZE` | `200` | In-memory detections kept per camera |

### Detection thresholds

| Variable | Default |
|---|---|
| `FACE_MATCH_THRESHOLD` | `0.60` — cosine similarity to call a face *known* |
| `FACE_MIN_CONFIDENCE` | `0.70` — detector confidence floor |
| `FACE_MIN_SIZE` | `30` — minimum face box size in **native** pixels |
| `WEAPON_CONFIDENCE_THRESHOLD` | `0.50` |
| `WEAPON_IOU_THRESHOLD` | `0.45` |

### Evidence clips

| Variable | Default |
|---|---|
| `ENABLE_EVENT_CLIPS` | `true` — MP4 clips for medium/high-risk events |
| `CLIP_PRE_SECONDS` | `4.0` — recorded from *before* the trigger |
| `CLIP_POST_SECONDS` | `6.0` |

### Qwen VLM (optional)

Everything here is optional. **Without `DASHSCOPE_API_KEY`, face and weapon
detection still work fully** — you only lose scene descriptions and chat.

| Variable | Default | Notes |
|---|---|---|
| `DASHSCOPE_API_KEY` | *(empty)* | Disables all VLM features when unset |
| `ENABLE_QWEN_EVENT_ANALYSIS` | `true` | Enrich high-risk alert wording |
| `ENABLE_QWEN_TEMPORAL` | `true` | Multi-frame analysis of triggered events |
| `ENABLE_QWEN_SCENE_POLLING` | `true` | Periodic scene check |
| `QWEN_SCENE_INTERVAL_SECONDS` | `300.0` | **Billed per camera per interval** |
| `QWEN_MAX_CONCURRENT` | `2` | Cap on in-flight cloud calls |

> **Cost warning.** Scene polling at 300 s across 8 cameras is roughly
> 96 API calls/hour, continuously. Raise the interval or set
> `ENABLE_QWEN_SCENE_POLLING=false` if that matters.
>
> Cloud calls never block detection — they run on a separate executor, and
> alerts are always created with a template message first, then enriched.

---

## Setting up the models

Two model artifacts are needed. Place them where `.env` points:

| Artifact | Default path | Required? |
|---|---|---|
| Face identity store | `storage/models/identity_store.pkl` | For face **recognition** |
| Weapon detector | `storage/models/weapon_detector.pt` | For weapon detection |

**FaceNet (InceptionResnetV1) and MTCNN download themselves** on first use via
`facenet-pytorch` — no manual step, but the first boot needs internet.

### Weapon detector

Any **YOLO `.pt`** checkpoint trained on weapon classes works — drop it at
`WEAPON_MODEL_PATH`. Class names are normalised automatically, so labels
containing `knife`/`dagger`/`blade` map to `knife`, and
`gun`/`pistol`/`rifle`/`shotgun`/`handgun`/`firearm` map to `firearm`.

If the file is missing, the service still starts; `/api/v1/health` reports
`"weapon_model_loaded": false` and weapon detection is simply skipped.

### Loading models from OSS

Set `FACE_STORE_OSS_KEY` / `WEAPON_MODEL_OSS_KEY` plus the `OSS_*` credentials,
then:

```bash
python scripts/download_models.py          # pull down to local paths
python scripts/upload_models_to_oss.py     # push local models up
```

In Docker, `docker compose --profile setup run --rm download-models` does the
same, or set `DOWNLOAD_MODELS=true` to run it on every container start.

---

## Enrolling faces

Recognition needs an identity store built from reference photos. Lay them out
one directory per person:

```
data/enrollment/
    alice/   front.jpg  left.jpg  right.jpg
    bob/     front.jpg  ...
```

Use 3–5 photos per person covering different angles and lighting. Then:

```python
# enroll.py — run once from the project root
from pathlib import Path
from app.face import FaceEmbedder, IdentityStore, enroll_from_directory

embedder = FaceEmbedder()
store = IdentityStore()

reports = enroll_from_directory(Path("data/enrollment"), embedder, store)

store.save("storage/models/identity_store.pkl")

for r in reports:
    print(r)
```

Each report includes `min_pairwise_similarity` — the lowest similarity among
one person's *own* photos. A low value warns that a photo is probably a bad
crop, an extreme angle, or the wrong person.

Then load it without restarting the service:

```bash
curl -X POST http://localhost:8000/api/v1/identities/reload
```

Running cameras pick up the new store on their next match.

> There is no HTTP enrollment endpoint — enrollment is an offline batch step.

---

## Registering cameras

Cameras are **not** configured in `.env`. Register them over the API; they are
persisted and (with `AUTO_START_CAMERAS=true`) resume automatically after a
restart.

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

An `enabled` camera starts streaming immediately. Then watch it connect:

```bash
curl http://localhost:8000/api/v1/cameras/status
```

`status` moves `offline → connecting → online`, or `error` with `last_error`
set. Per-camera `sample_fps` overrides `STREAM_SAMPLE_FPS` — useful for giving
a critical entrance more frames than a car park.

**`enabled` vs `status`** are deliberately separate: `enabled` is operator
intent, `status` is the live connection state. `POST /stop` sets
`enabled=false`, so a stopped camera stays stopped across reboots.

---

## API reference

Base path: `/api/v1`. Interactive docs at `/docs`.

### Health

| | |
|---|---|
| `GET /health` | Device, which models loaded, cameras running, WS subscribers |

### Cameras

| Method | Path | Notes |
|---|---|---|
| `GET` | `/cameras` | All registered cameras + running state |
| `POST` | `/cameras` | Register (and auto-start if `enabled`). `201` |
| `GET` | `/cameras/status` | Live pipeline telemetry: FPS, drops, reconnects, open tracks |
| `GET` | `/cameras/{id}` | One camera + its pipeline detail |
| `PATCH` | `/cameras/{id}` | Update. Changing `rtsp_url`/`sample_fps`/`name` restarts the pipeline |
| `DELETE` | `/cameras/{id}` | Stops the pipeline. **Events and alerts are retained** |
| `POST` | `/cameras/{id}/start` | Also sets `enabled=true` |
| `POST` | `/cameras/{id}/stop` | Also sets `enabled=false` |
| `POST` | `/cameras/{id}/restart` | Tear down and reconnect |
| `GET` | `/cameras/{id}/detections?limit=50` | Raw ring-buffer detections (not persisted) |

`rtsp_url` must start with `rtsp://`, `rtsps://`, `rtmp://`, `http://` or
`https://` — otherwise `422`. A duplicate URL returns `409`. Exceeding
`MAX_CAMERAS` returns `409` on start, but the camera is still registered.

### Events

| Method | Path | Notes |
|---|---|---|
| `GET` | `/events` | Filters: `camera_id`, `risk_level`, `event_type`, `status`, `minutes`, `limit`, `offset` |
| `GET` | `/events/{id}` | Full payload, its alerts, plus signed `snapshot_url`/`clip_url` |

Media URLs are resolved **on read** because OSS signed links expire
(`ARTIFACT_URL_EXPIRES`, default 1 h). Don't cache them.

### Alerts

| Method | Path | Notes |
|---|---|---|
| `GET` | `/alerts` | Filters: `camera_id`, `priority`, `acknowledged`, `minutes`, `limit`, `offset` |
| `POST` | `/alerts/{id}/ack` | Acknowledge; broadcasts `alert.acknowledged` |

### Identities

| Method | Path | Notes |
|---|---|---|
| `GET` | `/identities` | Enrolled names |
| `POST` | `/identities/reload` | Re-read the store from disk/OSS, no restart |

### Chat

`POST /chat` — ask about recent activity in plain language. Scoped by camera
and a lookback window, not by a video file.

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question": "Any unknown people at the lobby in the last hour?",
       "camera_id": "cam_ab12cd34ef56",
       "minutes": 60}'
```

Omit `camera_id` to ask across every camera. Requires `DASHSCOPE_API_KEY`.

---

## WebSocket protocol

```
ws://localhost:8000/api/v1/ws/live            # everything
ws://localhost:8000/api/v1/ws/live?camera_id=cam_ab12cd34ef56   # one camera
```

Every message is `{"type": ..., "camera_id": ..., ...}`.

| `type` | When |
|---|---|
| `snapshot` | **First message.** Current cameras + 20 recent alerts, so a client renders immediately |
| `detection` | Per-sampled-frame faces/weapons |
| `event.opened` | An appearance began — fires immediately |
| `event.closed` | Finalised with duration and detection count |
| `event.clip_ready` | MP4 finished encoding and uploading |
| `event.analysis` | VLM analysis attached |
| `alert` | New alert (template wording) |
| `alert.updated` | Same alert, VLM-enriched wording |
| `alert.acknowledged` | Someone acked it |
| `camera.status` | Connection state changed |
| `ping` | Every 20 s idle, to survive proxies |

Quick test:

```bash
# pip install websockets
python -c "
import asyncio, websockets
async def main():
    async with websockets.connect('ws://localhost:8000/api/v1/ws/live') as ws:
        while True: print(await ws.recv())
asyncio.run(main())
"
```

Each subscriber has a **bounded queue that drops the oldest message** when it
overflows, so one slow client can never stall the detection pipeline. A client
that needs guaranteed history should reconcile via `GET /events`.

---

## Events and alerts

| `event_type` | `risk_level` | Trigger |
|---|---|---|
| `known_face_detected` | `info` | Enrolled person seen |
| `unknown_face_detected` | `medium` | Unrecognised person |
| `armed_unknown_person` | `high` | Unknown face **and** a weapon in frame together |
| `knife_detected`, `firearm_detected` | `high` | Weapon detector |
| `suspicious_scene` | `high` | Periodic VLM scene check |
| `temporal_security_event` | `medium`/`high` | Multi-frame VLM analysis |

Alert priority maps `high→HIGH`, `medium→MEDIUM`, `low→LOW`, `info→INFO`.
**`info` and `low` events are recorded but never alerted** — so a known
employee walking past does not page anyone.

Strangers get stable labels (`unknown_1`, `unknown_2`, …) via online clustering
with a TTL. These are **per-camera and per-session**: `unknown_1` on the lobby
camera is unrelated to `unknown_1` on the car park camera, and the labels reset
when a camera restarts.

Artifacts are stored at `artifacts/{camera_id}/{YYYYMMDD}/{category}/{file}`.

---

## Tuning for your hardware

Total load ≈ `number_of_cameras × STREAM_SAMPLE_FPS` inferences/sec. If the
device cannot keep up, frames are dropped — the system degrades in *temporal
resolution*, not in latency, and never crashes.

`GET /cameras/status` reports per camera:

| Field | Meaning |
|---|---|
| `capture.source_fps` | Rate the camera is actually delivering |
| `capture.frames_received` / `frames_dropped` | Dropped = decoded but superseded before analysis. Steady growth is **normal and by design** |
| `capture.reconnect_count` | Rising steadily means an unstable link |
| `capture.last_frame_age_seconds` | Should stay near zero on a healthy stream |
| `analyzer.frames_analyzed` | Frames that actually went through the detectors |
| `analyzer.last_analysis_age_seconds` | Growing well past `1/sample_fps` means the device is saturated |
| `analyzer.open_tracks` / `unknown_tracks` | Current appearances being tracked |

Reach for these in order:

1. **Lower `STREAM_INFERENCE_WIDTH`** (960 → 640). Biggest win. Detection
   thresholds are applied in native pixels, so `FACE_MIN_SIZE` keeps its
   meaning.
2. **Lower `STREAM_SAMPLE_FPS`** (3.0 → 1.5). Halves the work; slower reaction.
3. **Use each camera's sub-stream** rather than the 4K main stream.
4. **Raise `INFERENCE_MAX_CONCURRENT`** only if the GPU is idle *and* has spare
   VRAM. Too high causes thrashing.
5. **Per-camera `sample_fps`** — spend frames where they matter.

Rough starting points:

| Device | Cameras | `STREAM_SAMPLE_FPS` | `STREAM_INFERENCE_WIDTH` |
|---|---|---|---|
| Raspberry Pi 5, CPU | 1–2 | `1.0` | `640` |
| Jetson Orin Nano | 4–6 | `2.0` | `640` |
| Jetson Orin NX / AGX | 8 | `3.0` | `960` |
| Desktop RTX GPU | 8+ | `5.0` | `1280` |

SQLite runs in **WAL mode** with a busy timeout so concurrent analyzer threads
don't hit `database is locked`. Past ~8 cameras, or for a central server
aggregating several edge boxes, move to PostgreSQL via `DATABASE_URL`.

---

## Verification

An offline check covers the route table, schema creation, the event-tracker
state machine, the unknown-face clusterer, and real HTTP/WebSocket requests —
**no camera, GPU, or model files required**:

```bash
pip install httpx        # test-only dependency
python scripts/verify_wiring.py
```

Exit code `0` means everything passed. This deliberately does **not** cover
live RTSP behaviour (reconnect, throughput, clip encoding) — that needs real
cameras. The first real test is: register one camera, watch
`GET /api/v1/cameras/status`, and connect to the WebSocket.

---

## Troubleshooting

**Camera stuck in `connecting`, or `status: error`**

Check `last_error` from `GET /cameras/{id}`. Verify the URL independently:

```bash
ffprobe -rtsp_transport tcp "rtsp://user:pass@host:554/path"
```

Common causes: wrong stream path for the vendor, credentials with characters
that need URL-encoding (`@` → `%40`), the camera's connection limit already
reached, or UDP being dropped — try `STREAM_RTSP_TRANSPORT=tcp`.

**Container can't reach the camera** — see
[Reaching cameras on your LAN](#reaching-cameras-on-your-lan).

**`ModuleNotFoundError: No module named 'torch'`** — `app/core/config.py`
imports torch for device detection, so it is required even for CPU-only runs.

**Everything returns `503 Stream manager is not initialized`** — startup did
not finish. Check the logs: this is normal only during boot.

**No faces ever recognised** — confirm `GET /identities` is non-empty; if the
store didn't load, `/health` shows `identity_count: 0`. Lower
`FACE_MATCH_THRESHOLD` (0.60 → 0.55) to loosen matching, or `FACE_MIN_SIZE` if
subjects are far from the camera.

**Everyone matches the wrong person** — threshold too low, or enrollment photos
are poor. Check `min_pairwise_similarity` from enrollment.

**Duplicate events for the same person** — `EVENT_GAP_SECONDS` too low, or the
unknown clusterer is splitting one stranger into several. Raise
`EVENT_GAP_SECONDS`, or lower `UNKNOWN_FACE_CLUSTER_THRESHOLD`.

**No clips** — clips are only recorded for **medium/high** events, and need
`ENABLE_EVENT_CLIPS=true`. Encoding is asynchronous; `clip_key` is patched in
afterwards and `event.clip_ready` is broadcast.

**Alerts stop arriving after the first one** — `ALERT_COOLDOWN_SECONDS`
suppresses repeats of the same event type per camera. Events still accumulate.

**Duplicate events across the board** — you are running more than one worker.
Use `--workers 1`.

---

## Security notes

Please read before exposing this service.

- **There is no authentication.** Every endpoint, including camera CRUD, is
  open. Do not put this on a public interface without a reverse proxy
  enforcing auth/TLS.
- **CORS defaults to `*`.** Restrict `CORS_ORIGINS` in production.
- **RTSP credentials are stored in plaintext** in the `rtsp_url` column and are
  **echoed back** by the camera endpoints. Anyone who can reach the API can
  read your camera passwords.
- The identity store is a **pickle** file. Only load ones you generated —
  unpickling untrusted data executes arbitrary code.
- Face recognition and stored footage are regulated in many jurisdictions
  (GDPR, BIPA, and others). Enrolment implies consent obligations that are
  yours to meet.

---

## Project layout

```
app/
  api/          endpoints.py (health, identities, chat), cameras.py, live.py
  streaming/    capture, inference, tracker, analyzer, clips, broadcaster, manager
  pipelines/    fusion_engine (risk scoring), weapon_detector, prompts
  face/         face_embedding, vector_store, enroll
  db/           models.py (Camera, Event, Alert), session.py
  integrations/ qwen.py, storage.py
  services/     runtime.py (shared model singletons)
scripts/        download_models, upload_models_to_oss, verify_wiring
```
