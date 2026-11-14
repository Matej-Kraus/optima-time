"""HTTP API, the data for vMix over HTTP, and the built UI (SPEC 12.2, 13).

GET  /data/values.xml             the same XML as the file (for an XML Data Source by URL)
GET  /data/values.json            the same values as JSON (debugging)
GET  /api/profile                 the profile
PUT  /api/profile                 validate, save, apply
GET  /api/state                   source, processing, guard, outputs, readings, published values
GET  /api/sources                 NDI sources on the network, capture devices on this PC
GET  /api/events?limit=N          the latest events (changes, rejections, guard, source, writes)
GET  /api/frame.jpg?view=source|rectified&max_width=N   latest frame as JPEG
GET  /api/crop/{field_id}.png     the crop that went to OCR for a field
POST /api/fields/{field_id}/hold  {"text": "..."}: publish this, ignore OCR (SPEC 11.6)
POST /api/fields/{field_id}/release
POST /api/values/clear            empty every value that isn't held
POST /api/output/pause | /api/output/live
POST /api/output/test             random valid values to the outputs
POST /api/output/test-clear       empty values to the outputs
POST /api/anchors                 {"roi": {...}}: capture an anchor from the current frame
DELETE /api/anchors/{index}
/                                 the built frontend (frontend/dist)

Every response carries Cache-Control: no-store where values are involved.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, Literal

import cv2
from fastapi import Body, FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from optima_time.config.models import AnchorConfig, Profile
from optima_time.fields.models import ClockField, NumberField, PeriodField, Roi
from optima_time.guard import capture_template
from optima_time.outputs.base import OutputMode
from optima_time.outputs.xml import build_xml
from optima_time.runner import Runner
from optima_time.sources.device import list_devices
from optima_time.sources.live import SourceUnavailable
from optima_time.sources.ndi import list_ndi_sources

NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}


def frontend_dir() -> Path:
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


def create_app(runner: Runner, static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Optima Time", docs_url="/api/docs", openapi_url="/api/openapi.json")

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
    def get_crop(field_id: str) -> Response:
        result = runner.snapshot().result
        r = result.fields.get(field_id) if result else None
        if r is None or r.crop is None:
            raise HTTPException(404, "no crop")
        ok, data = cv2.imencode(".png", r.crop)
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
