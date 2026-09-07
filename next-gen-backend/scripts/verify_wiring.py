"""Offline wiring check: route table, schema creation, tracker state machine.

Runs without a camera, a GPU, or any network access. Intended as a smoke test
after changing the streaming pipeline or the API surface.

    python scripts/verify_wiring.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("AUTO_START_CAMERAS", "false")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("LOG_LEVEL", "WARNING")

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok    {label}")
    else:
        suffix = f" -- {detail}" if detail else ""
        print(f"  FAIL  {label}{suffix}")
        failures.append(label)


def _flatten(routes) -> set[str]:
    """
    Collects "METHOD /path" for every route.

    Recent FastAPI versions keep `include_router` results as a lazy wrapper
    object rather than copying the child routes onto the parent, so a flat scan
    of `app.routes` silently reports an empty API. Follow `original_router`
    where present.
    """
    found: set[str] = set()

    for route in routes:
        nested = getattr(route, "original_router", None) or getattr(route, "routes", None)

        if nested is not None:
            found |= _flatten(getattr(nested, "routes", nested))
            continue

        path = getattr(route, "path", None)
        if not path:
            continue

        for method in sorted(getattr(route, "methods", None) or ["WS"]):
            if method in ("HEAD", "OPTIONS"):
                continue
            found.add(f"{method} {path}")

    return found


def check_routes() -> None:
    print("[1] route table")
    from app.main import app

    routes = _flatten(app.routes)

    for line in sorted(routes):
        print(f"        {line}")

    expected = {
        "GET /api/v1/health",
        "GET /api/v1/identities",
        "POST /api/v1/identities/reload",
        "POST /api/v1/chat",
        "GET /api/v1/cameras",
        "POST /api/v1/cameras",
        "GET /api/v1/cameras/status",
        "GET /api/v1/cameras/{camera_id}",
        "PATCH /api/v1/cameras/{camera_id}",
        "DELETE /api/v1/cameras/{camera_id}",
        "POST /api/v1/cameras/{camera_id}/start",
        "POST /api/v1/cameras/{camera_id}/stop",
        "POST /api/v1/cameras/{camera_id}/restart",
        "GET /api/v1/cameras/{camera_id}/detections",
        "GET /api/v1/events",
        "GET /api/v1/events/{event_id}",
        "GET /api/v1/alerts",
        "POST /api/v1/alerts/{alert_id}/ack",
        "WS /api/v1/ws/live",
    }

    missing = expected - routes
    check("all expected routes registered", not missing, f"missing={sorted(missing)}")

    stale = {r for r in routes if "/videos" in r or "/jobs" in r or "/batch" in r}
    check("no batch-era routes survive", not stale, f"found={sorted(stale)}")


class StubStreamManager:
    """
    Stands in for StreamManager so the HTTP layer can be exercised without
    loading models or opening sockets. Only the surface the API touches.
    """

    def __init__(self):
        self.running: set[str] = set()
        self.calls: list[tuple] = []

    @property
    def running_count(self) -> int:
        return len(self.running)

    def is_running(self, camera_id: str) -> bool:
        return camera_id in self.running

    def start_camera(self, camera_id, name, rtsp_url, sample_fps=None) -> bool:
        self.calls.append(("start", camera_id))
        if camera_id in self.running:
            return False
        self.running.add(camera_id)
        return True

    def stop_camera(self, camera_id) -> bool:
        self.calls.append(("stop", camera_id))
        was_running = camera_id in self.running
        self.running.discard(camera_id)
        return was_running

    def restart_camera(self, camera_id, name, rtsp_url, sample_fps=None) -> bool:
        self.calls.append(("restart", camera_id))
        self.running.add(camera_id)
        return True

    def camera_status(self, camera_id) -> dict:
        return {"camera_id": camera_id, "running": self.is_running(camera_id), "open_tracks": []}

    def all_status(self) -> list:
        return [self.camera_status(c) for c in sorted(self.running)]

    def recent_detections(self, camera_id, limit) -> list:
        return []


def check_requests() -> None:
    """
    Exercises the API for real. Route introspection alone would not catch a
    broken dependency, a bad response model, or `/cameras/status` being
    shadowed by `/cameras/{camera_id}`.

    TestClient is used without its context manager on purpose: entering it
    would run the lifespan, which loads the models and starts camera threads.
    A stub manager is injected instead.
    """
    print("[5] request handling")

    try:
        from fastapi.testclient import TestClient
    except Exception as exc:  # httpx is a test-only dependency
        print(f"  skip  TestClient unavailable ({exc}); run `pip install httpx` to enable")
        return

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.models import Base
    from app.db.session import get_db
    from app.main import app
    from app.services import runtime

    stub = StubStreamManager()
    runtime._stream_manager = stub

    with tempfile.TemporaryDirectory() as tmp:
        engine = create_engine(
            f"sqlite:///{Path(tmp) / 'api.db'}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=engine)
        TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        def override_get_db():
            db = TestingSession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        try:
            response = client.get("/api/v1/health")
            check("GET /health returns 200", response.status_code == 200, response.text[:200])
            if response.status_code == 200:
                check("health reports streaming state", "streaming" in response.json())

            response = client.get("/api/v1/cameras")
            check("GET /cameras returns 200", response.status_code == 200, response.text[:200])

            response = client.get("/api/v1/cameras/status")
            check(
                "GET /cameras/status is not shadowed by /cameras/{id}",
                response.status_code == 200,
                response.text[:200],
            )

            response = client.post(
                "/api/v1/cameras",
                json={"name": "Lobby", "rtsp_url": "rtsp://user:pass@10.0.0.5:554/stream1"},
            )
            check("POST /cameras creates a camera", response.status_code == 201, response.text[:300])

            body = response.json() if response.status_code == 201 else {}
            camera_id = body.get("camera_id")

            check("enabled camera is auto-started on create", body.get("started") is True, f"body={body}")

            response = client.post(
                "/api/v1/cameras",
                json={"name": "Dup", "rtsp_url": "rtsp://user:pass@10.0.0.5:554/stream1"},
            )
            check("duplicate stream URL is rejected", response.status_code == 409, response.text[:200])

            response = client.post(
                "/api/v1/cameras",
                json={"name": "Bad", "rtsp_url": "file:///etc/passwd"},
            )
            check("POST /cameras rejects a non-stream URL", response.status_code == 422, response.text[:200])

            if camera_id:
                response = client.get(f"/api/v1/cameras/{camera_id}")
                check("GET /cameras/{id} returns the camera", response.status_code == 200, response.text[:200])

                response = client.get(f"/api/v1/cameras/{camera_id}/detections")
                check(
                    "GET /cameras/{id}/detections returns 200",
                    response.status_code == 200,
                    response.text[:200],
                )

                response = client.patch(f"/api/v1/cameras/{camera_id}", json={"location": "Ground floor"})
                check("PATCH /cameras/{id} updates", response.status_code == 200, response.text[:200])

                response = client.post(f"/api/v1/cameras/{camera_id}/stop")
                check("POST /cameras/{id}/stop returns 200", response.status_code == 200, response.text[:200])
                check("stop clears operator intent", not stub.is_running(camera_id))

                response = client.post(f"/api/v1/cameras/{camera_id}/start")
                check("POST /cameras/{id}/start returns 200", response.status_code == 200, response.text[:200])
                check("start re-runs the pipeline", stub.is_running(camera_id))

                response = client.post(f"/api/v1/cameras/{camera_id}/restart")
                check("POST /cameras/{id}/restart returns 200", response.status_code == 200, response.text[:200])

                response = client.delete(f"/api/v1/cameras/{camera_id}")
                check("DELETE /cameras/{id} returns 200", response.status_code == 200, response.text[:200])
                check("delete stops the pipeline", not stub.is_running(camera_id))

            response = client.get("/api/v1/cameras/does-not-exist")
            check("unknown camera returns 404", response.status_code == 404, response.text[:200])

            response = client.get("/api/v1/events")
            check("GET /events returns 200", response.status_code == 200, response.text[:200])

            response = client.get("/api/v1/events/nope")
            check("unknown event returns 404", response.status_code == 404, response.text[:200])

            response = client.get("/api/v1/alerts")
            check("GET /alerts returns 200", response.status_code == 200, response.text[:200])

            response = client.get("/openapi.json")
            check("OpenAPI schema builds", response.status_code == 200, response.text[:300])

            with client.websocket_connect("/api/v1/ws/live") as ws:
                message = ws.receive_json()
                check(
                    "websocket sends a snapshot on connect",
                    message.get("type") == "snapshot",
                    f"got={message.get('type')}",
                )
        finally:
            app.dependency_overrides.clear()
            runtime._stream_manager = None
            engine.dispose()



def check_schema() -> None:
    print("[2] schema creation")
    from sqlalchemy import create_engine, inspect

    from app.db.models import Base

    with tempfile.TemporaryDirectory() as tmp:
        engine = create_engine(f"sqlite:///{Path(tmp) / 'verify.db'}")
        Base.metadata.create_all(bind=engine)
        tables = set(inspect(engine).get_table_names())
        engine.dispose()

    check("cameras/events/alerts created", {"cameras", "events", "alerts"} <= tables, f"got={sorted(tables)}")
    check("no video/job/batch tables", not ({"videos", "jobs", "batches"} & tables), f"got={sorted(tables)}")


def check_tracker() -> None:
    print("[3] tracker state machine")
    from app.streaming.tracker import LiveEventTracker

    tracker = LiveEventTracker(camera_id="cam-1", gap_seconds=3.0)

    opened, closed = tracker.observe_face(
        {"identity_name": "alice", "similarity_score": 0.7, "bbox": [0, 0, 10, 10]}, timestamp=100.0
    )
    check("first sighting opens a track", opened is not None and closed is None)

    opened, closed = tracker.observe_face(
        {"identity_name": "alice", "similarity_score": 0.9, "bbox": [0, 0, 10, 10]}, timestamp=102.0
    )
    check("sighting inside gap extends, does not reopen", opened is None and closed is None)

    track = tracker.snapshot()[0]
    check(
        "representative detection is the most confident one",
        abs(float(track["best_similarity_score"]) - 0.9) < 1e-6,
        f"best_similarity_score={track['best_similarity_score']}",
    )
    check("detection_count accumulates", track["detection_count"] == 2, f"count={track['detection_count']}")

    opened, closed = tracker.observe_face(
        {"identity_name": "alice", "similarity_score": 0.8, "bbox": [0, 0, 10, 10]}, timestamp=110.0
    )
    check("sighting past the gap closes and reopens", opened is not None and closed is not None)
    if closed is not None:
        check(
            "closed track ends at its last sighting, not now",
            abs(float(closed["last_seen"]) - 102.0) < 1e-6,
            f"last_seen={closed['last_seen']}",
        )

    stale = tracker.close_stale(now=200.0)
    check("close_stale closes the idle track", len(stale) == 1, f"closed={len(stale)}")
    check("tracker is empty afterwards", tracker.snapshot() == [])

    tracker.observe_weapon({"object_class": "knife", "confidence": 0.8, "bbox": [0, 0, 10, 10]}, timestamp=300.0)
    check("close_all drains remaining tracks", len(tracker.close_all()) == 1)


def check_unknown_clusterer() -> None:
    print("[4] unknown-face clusterer")
    import numpy as np

    from app.streaming.tracker import UnknownFaceClusterer

    clusterer = UnknownFaceClusterer(threshold=0.56, ttl_seconds=10.0)

    a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    a_noisy = np.array([0.97, 0.05, 0.02], dtype=np.float32)
    b = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    first = clusterer.assign(a, timestamp=0.0)
    check("first unknown gets a label", first == "unknown_1", f"got={first}")

    again = clusterer.assign(a_noisy, timestamp=1.0)
    check("near-identical embedding reuses the label", again == first, f"got={again}")

    other = clusterer.assign(b, timestamp=1.0)
    check("a different face gets a new label", other == "unknown_2", f"got={other}")

    revisit = clusterer.assign(a, timestamp=2.0)
    check("labels stay stable across frames", revisit == first, f"got={revisit}")

    after_ttl = clusterer.assign(a, timestamp=100.0)
    check("stale clusters are evicted past the TTL", after_ttl not in (first, other), f"got={after_ttl}")


def main() -> int:
    for step in (check_routes, check_schema, check_tracker, check_unknown_clusterer, check_requests):
        try:
            step()
        except Exception as exc:  # noqa: BLE001 - report and keep going
            print(f"  ERROR {step.__name__}: {type(exc).__name__}: {exc}")
            failures.append(step.__name__)

    print()
    if failures:
        print(f"FAILED ({len(failures)}): {failures}")
        return 1
    print("All offline checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
