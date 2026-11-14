"""HTTP API, the data for vMix over HTTP, and the built UI (SPEC 12.2, 13).

GET  /data/values.xml             the same XML as the file (for an XML Data Source by URL)
GET  /data/values.json            the same values as JSON (debugging)
GET  /api/profile                 the profile
PUT  /api/profile                 validate, save, apply
GET  /api/state                   source, processing, guard, outputs, readings, published values
GET  /api/sources                 NDI sources on the network, capture devices on this PC
GET  /api/profiles; POST /api/profiles/load|save-as|import; GET /api/profiles/export
POST /api/samples/record {"seconds": N}; GET /api/samples/status
GET  /api/diagnostics.zip
GET  /api/preview.mjpg?view=source|rectified&fps=8   MJPEG preview stream
GET  /api/events?limit=N          the latest events (changes, rejections, guard, source, writes)
GET  /api/frame.jpg?view=source|rectified&max_width=N   latest frame as JPEG
GET  /api/crop/{field_id}.png?mode=raw|otsu   the crop that went to OCR (or binarized)
GET  /api/guard/history           anchor match over the last ~24 s
POST /api/fields/{field_id}/hold  {"text": "..."}: publish this, ignore OCR (SPEC 11.6)
POST /api/fields/{field_id}/release
POST /api/values/clear            empty every value that isn't held
POST /api/output/pause | /api/output/live
POST /api/output/test             random valid values to the outputs
POST /api/output/test-clear       empty values to the outputs
POST /api/anchors                 {"roi": {...}}: capture an anchor from the current frame
POST /api/anchors/auto            suggest anchors (static captions away from the fields)
PUT  /api/anchors/{index}         {"roi": {...}}: move/resize an anchor, recapture its template
DELETE /api/anchors/{index}
/                                 the built frontend (frontend/dist)

Every response carries Cache-Control: no-store where values are involved.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import random
import secrets
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, Literal

import cv2
from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from optima_time import __version__
from optima_time.config import profiles
from optima_time.config.models import AnchorConfig, Profile
from optima_time.config.store import save_profile
from optima_time.diagnostics import build_zip
from optima_time.fields.models import ClockField, NumberField, PeriodField, Roi
from optima_time.guard import capture_template, history_frame, suggest_anchors
from optima_time.outputs.base import OutputMode
from optima_time.outputs.xml import build_xml
from optima_time.preprocess import gray_max
from optima_time.runner import Runner
from optima_time.sources.device import list_devices
from optima_time.sources.live import SourceUnavailable
from optima_time.sources.ndi import list_ndi_sources

NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}


def frontend_dir() -> Path:
    """The built UI: next to the code in the repository, or inside the PyInstaller bundle."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "frontend" / "dist"
    return Path(__file__).resolve().parents[3] / "frontend" / "dist"


def _json(body: Any, status: int = 200) -> Response:
    return Response(
        content=json.dumps(body, ensure_ascii=False),
        media_type="application/json",
        headers=NO_CACHE,
        status_code=status,
    )


def random_test_values(profile: Profile, rng: random.Random | None = None) -> dict[str, str]:
    """Random valid values for every enabled field (SPEC 12.1 test data)."""
    rng = rng or random.Random()
    out: dict[str, str] = {}
    for f in profile.fields:
        if not f.enabled:
            continue
        if isinstance(f, ClockField):
            text = f"{rng.randint(0, 19):02d}:{rng.randint(0, 59):02d}"
        elif isinstance(f, PeriodField):
            text = str(rng.randint(f.min_value, f.max_value))
        else:
            assert isinstance(f, NumberField)
            text = str(rng.randint(0, 15))
        value = f.parse(text, None)
        out[f.id] = f.render(value) if value is not None else text
    return out


PIN_COOKIE = "optima_pin"
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}

LOGIN_PAGE = """<!doctype html><html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Optima Time</title>
<style>body{font-family:system-ui;background:#111418;color:#e8eaed;display:grid;place-items:center;
height:100vh;margin:0}form{display:flex;gap:8px}input,button{font:inherit;padding:8px}</style>
</head><body><form method="get" action="/login"><input name="pin" type="password"
placeholder="PIN" autofocus><button>Přihlásit</button></form></body></html>"""


def create_app(runner: Runner, static_dir: Path | None = None, pin: str | None = None) -> FastAPI:
    app = FastAPI(title="Optima Time", docs_url="/api/docs", openapi_url="/api/openapi.json")
    # the cookie carries a token derived from the PIN with a per-process secret, not the PIN
    token = hmac.new(secrets.token_bytes(32), (pin or "").encode(), hashlib.sha256).hexdigest()

    # --- access from the network (SPEC 13.4): only with the PIN; localhost always

    @app.middleware("http")
    async def require_pin(request: Request, call_next):
        client = request.client.host if request.client else ""
        if pin and client not in LOCAL_HOSTS and request.url.path != "/login":
            given = request.cookies.get(PIN_COOKIE, "")
            if not hmac.compare_digest(given, token):
                if request.url.path.startswith(("/api", "/data")):
                    return Response("PIN required", status_code=401)
                return HTMLResponse(LOGIN_PAGE, status_code=401)
        return await call_next(request)

    @app.get("/login", include_in_schema=False)
    def login(request: Request) -> Response:
        given = request.query_params.get("pin", "")
        if not pin or not hmac.compare_digest(given, pin):
            time.sleep(0.5)  # slow down guessing
            return HTMLResponse(LOGIN_PAGE, status_code=401)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(PIN_COOKIE, token, httponly=True, samesite="strict")
        return response

    # --- data for vMix

    @app.get("/data/values.xml")
    def data_xml() -> Response:
        return Response(
            content=build_xml(runner.state.values()),
            media_type="application/xml; charset=utf-8",
            headers=NO_CACHE,
        )

    @app.get("/data/values.json")
    def data_json() -> Response:
        return _json(runner.state.values())

    # --- profile

    @app.get("/api/profile")
    def get_profile() -> dict[str, Any]:
        return runner.profile.model_dump(mode="json")

    @app.put("/api/profile")
    def put_profile(body: dict[str, Any]) -> dict[str, Any]:
        try:
            profile = Profile.model_validate(body)
        except ValidationError as error:
            raise HTTPException(422, detail=error.errors(include_url=False)) from error
        runner.update_profile(profile)
        return profile.model_dump(mode="json")

    # --- live state

    @app.get("/api/state")
    def get_state() -> Response:
        snap = runner.snapshot()
        result = snap.result
        published = runner.state.fields()
        fields = {}
        for fid, pub in published.items():
            r = result.fields.get(fid) if result else None
            fields[fid] = pub | {
                "read_status": r.status.value if r else None,
                "read_text": r.text if r else None,
                "raw": r.reading.text if r and r.reading else None,
                "confidence": round(r.reading.confidence, 3) if r and r.reading else None,
                "contrast": round(r.contrast, 1) if r else None,
            }
        rect = snap.rectified
        body = {
            "version": __version__,
            "source": runner.source_status(),
            "processing_fps": round(snap.processing_fps, 1),
            "frame": {"seq": result.seq, "pts": result.pts, "timings_ms": result.timings_ms}
            if result
            else None,
            "guard": {"state": result.guard.state.value, "scores": result.guard.scores}
            if result
            else None,
            "outputs": runner.outputs_status(),
            "process": runner.process_status(),
            "rectified_size": [rect.shape[1], rect.shape[0]] if rect is not None else None,
            "fields": fields,
        }
        return _json(body)

    @app.get("/api/sources")
    def get_sources() -> Response:
        """NDI sources on the network and capture devices on this PC."""
        try:
            ndi: list[str] | None = list_ndi_sources(wait_s=1.0)
            ndi_error = None
        except SourceUnavailable as error:
            ndi, ndi_error = None, str(error)
        devices = [d.as_dict() for d in list_devices()]
        return _json({"ndi": ndi, "ndi_error": ndi_error, "devices": devices})

    @app.get("/api/guard/history")
    def guard_history() -> Response:
        """Anchor match over the last ~24 s (lowest anchor score, 10 per second)."""
        now = time.time()
        points = [
            {"ago": round(now - t, 1), "score": score, "state": state}
            for t, score, state in runner.guard_history
        ]
        return _json({"threshold": runner.profile.guard.threshold, "points": points})

    @app.get("/api/events")
    def get_events(limit: int = 100) -> Response:
        events = list(runner.state.events)[-max(1, min(limit, 300)) :]
        return _json([asdict(e) for e in reversed(events)])

    @app.get("/api/frame.jpg")
    def get_frame(
        view: Literal["source", "rectified"] = "source", max_width: int = 960
    ) -> Response:
        snap = runner.snapshot()
        image = (
            snap.rectified if view == "rectified" else (snap.frame.image if snap.frame else None)
        )
        if image is None:
            raise HTTPException(404, "no frame yet")
        h, w = image.shape[:2]
        if w > max_width > 0:
            image = cv2.resize(
                image, (max_width, round(h * max_width / w)), interpolation=cv2.INTER_AREA
            )
        ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            raise HTTPException(500, "encoding failed")
        return Response(content=data.tobytes(), media_type="image/jpeg", headers=NO_CACHE)

    @app.get("/api/crop/{field_id}.png")
    def get_crop(field_id: str, mode: Literal["raw", "otsu"] = "raw") -> Response:
        """The crop that went to OCR; mode=otsu shows it binarized (Otsu) for inspection.
        (OCR itself always reads the raw colour crop, DECISIONS D3.)"""
        result = runner.snapshot().result
        r = result.fields.get(field_id) if result else None
        if r is None or r.crop is None:
            raise HTTPException(404, "no crop")
        image = r.crop
        if mode == "otsu":
            _, image = cv2.threshold(gray_max(image), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        ok, data = cv2.imencode(".png", image)
        if not ok:
            raise HTTPException(500, "encoding failed")
        return Response(content=data.tobytes(), media_type="image/png", headers=NO_CACHE)

    # --- operator actions

    def _field(field_id: str) -> None:
        if field_id not in runner.state.values():
            raise HTTPException(404, f"unknown field {field_id!r}")

    @app.post("/api/fields/{field_id}/hold")
    def hold(field_id: str, text: Annotated[str, Body(embed=True, max_length=64)]) -> Response:
        _field(field_id)
        runner.state.hold(field_id, text)
        return _json(runner.state.fields()[field_id])

    @app.post("/api/fields/{field_id}/release")
    def release(field_id: str) -> Response:
        _field(field_id)
        runner.state.release(field_id)
        return _json(runner.state.fields()[field_id])

    @app.post("/api/values/clear")
    def clear_values() -> Response:
        runner.state.clear_values()
        return _json(runner.state.values())

    @app.post("/api/output/{action}")
    def output(action: Literal["pause", "live", "test", "test-clear"]) -> Response:
        hub = runner.hub
        if action == "pause":
            hub.set_mode(OutputMode.PAUSED)
        elif action == "live":
            hub.set_mode(OutputMode.LIVE)
        elif action == "test":
            hub.write_test(random_test_values(runner.profile))
        else:
            hub.write_test(dict.fromkeys(runner.state.values(), ""))
        return _json(runner.outputs_status())

    # --- profiles (SPEC 13.3)

    def _current() -> dict[str, Any]:
        path = runner.profile_path
        return {"name": runner.profile.name, "path": str(path) if path else None}

    @app.get("/api/profiles")
    def get_profiles() -> Response:
        return _json(
            {
                "current": _current(),
                "profiles": profiles.list_profiles(),
                "folder": str(profiles.profiles_dir()),
            }
        )

    @app.post("/api/profiles/load")
    def load_profile_(name: Annotated[str, Body(embed=True, max_length=200)]) -> Response:
        try:
            profile, path = profiles.load(name)
        except (FileNotFoundError, ValueError) as error:
            raise HTTPException(404, str(error)) from error
        runner.switch_profile(profile, path)
        return _json(_current())

    @app.post("/api/profiles/save-as")
    def save_as(name: Annotated[str, Body(embed=True, max_length=64)]) -> Response:
        try:
            path = profiles.save_as(runner.profile, name)
        except FileExistsError as error:
            raise HTTPException(409, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        profile, path = profiles.load(str(path))
        runner.switch_profile(profile, path)
        return _json(_current())

    @app.get("/api/profiles/export")
    def export_profile() -> Response:
        name = profiles.safe_name(runner.profile.name or "profil")
        return Response(
            runner.profile.model_dump_json(indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{name}.json"'},
        )

    @app.post("/api/profiles/import")
    def import_profile(
        name: Annotated[str, Body(max_length=64)], profile: Annotated[dict, Body()]
    ) -> Response:
        try:
            parsed = Profile.model_validate(profile)
            path = profiles.profiles_dir() / f"{profiles.safe_name(name)}.json"
        except (ValidationError, ValueError) as error:
            raise HTTPException(422, str(error)) from error
        if path.exists():
            raise HTTPException(409, f"profil {path.stem!r} už existuje")
        save_profile(parsed.model_copy(update={"name": path.stem}), path)
        runner.switch_profile(*profiles.load(str(path)))
        return _json(_current())

    # --- samples and diagnostics (SPEC 13.3)

    @app.post("/api/samples/record")
    def record(seconds: Annotated[float, Body(embed=True, gt=0, le=1800)]) -> Response:
        try:
            runner.recorder.start(runner.profile, seconds)
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error
        return _json(asdict(runner.recorder.status))

    @app.get("/api/samples/status")
    def record_status() -> Response:
        return _json(asdict(runner.recorder.status))

    @app.get("/api/diagnostics.zip")
    def diagnostics() -> Response:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        return Response(
            build_zip(runner, runner.log_dir),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="diagnostika-{stamp}.zip"'},
        )

    # --- preview stream (SPEC 13.1): MJPEG, at most `fps`, independent of the processing

    @app.get("/api/preview.mjpg")
    def preview(
        view: Literal["source", "rectified"] = "source", fps: float = 8, max_width: int = 960
    ) -> StreamingResponse:
        period = 1 / max(1.0, min(fps, 15.0))

        def frames():
            last_seq = -1
            while True:
                snap = runner.snapshot()
                seq = snap.result.seq if snap.result else -1
                image = (
                    snap.rectified
                    if view == "rectified"
                    else (snap.frame.image if snap.frame else None)
                )
                if image is not None and seq != last_seq:
                    last_seq = seq
                    h, w = image.shape[:2]
                    if w > max_width > 0:
                        image = cv2.resize(
                            image,
                            (max_width, round(h * max_width / w)),
                            interpolation=cv2.INTER_AREA,
                        )
                    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    if ok:
                        yield (
                            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                            + data.tobytes()
                            + b"\r\n"
                        )
                time.sleep(period)

        return StreamingResponse(
            frames(), media_type="multipart/x-mixed-replace; boundary=frame", headers=NO_CACHE
        )

    # --- anchors

    @app.post("/api/anchors")
    def add_anchor(roi: Annotated[Roi, Body(embed=True)]) -> dict[str, Any]:
        rectified = runner.snapshot().rectified
        if rectified is None:
            raise HTTPException(409, "no frame yet")
        try:
            template = capture_template(rectified, roi)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        profile = runner.profile.model_copy(deep=True)
        if len(profile.guard.anchors) >= 3:
            raise HTTPException(422, "at most 3 anchors")
        profile.guard.anchors.append(AnchorConfig(roi=roi, template=template))
        runner.update_profile(profile)
        return profile.model_dump(mode="json")

    @app.post("/api/anchors/auto")
    def auto_anchors() -> dict[str, Any]:
        """Find captions that don't change (away from the fields) and use them as anchors,
        replacing the current ones. Edit or delete them afterwards as needed."""
        rectified = runner.snapshot().rectified
        if rectified is None:
            raise HTTPException(409, "zatím není obraz")
        profile = runner.profile.model_copy(deep=True)
        if not profile.fields:
            raise HTTPException(422, "nejdřív nakresli pole, kotvy se hledají mimo ně")
        frames = runner.recent_history() or [history_frame(rectified)]
        anchors = []
        for roi in suggest_anchors(frames, [f.roi for f in profile.fields]):
            try:
                anchors.append(AnchorConfig(roi=roi, template=capture_template(rectified, roi)))
            except ValueError:
                continue
        if not anchors:
            raise HTTPException(422, "nenašel jsem žádný nápis, který se nemění; označ kotvu ručně")
        profile.guard.anchors = anchors
        runner.update_profile(profile)
        return profile.model_dump(mode="json")

    @app.put("/api/anchors/{index}")
    def update_anchor(index: int, roi: Annotated[Roi, Body(embed=True)]) -> dict[str, Any]:
        """Move or resize an anchor; its template is captured again from the current frame."""
        rectified = runner.snapshot().rectified
        if rectified is None:
            raise HTTPException(409, "zatím není obraz")
        profile = runner.profile.model_copy(deep=True)
        if not 0 <= index < len(profile.guard.anchors):
            raise HTTPException(404, "no such anchor")
        try:
            template = capture_template(rectified, roi)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        profile.guard.anchors[index] = AnchorConfig(roi=roi, template=template)
        runner.update_profile(profile)
        return profile.model_dump(mode="json")

    @app.delete("/api/anchors/{index}")
    def delete_anchor(index: int) -> dict[str, Any]:
        profile = runner.profile.model_copy(deep=True)
        if not 0 <= index < len(profile.guard.anchors):
            raise HTTPException(404, "no such anchor")
        del profile.guard.anchors[index]
        runner.update_profile(profile)
        return profile.model_dump(mode="json")

    static = static_dir or frontend_dir()
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="ui")
    return app
