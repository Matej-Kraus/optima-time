"""HTTP API and the built UI (SPEC 13). Milestone 1: profile, preview images, live readings.

GET  /api/profile                 the profile
PUT  /api/profile                 validate, save, apply
GET  /api/state                   source status, processing fps and the latest readings
GET  /api/frame.jpg?view=source|rectified&max_width=N   latest frame as JPEG
GET  /api/crop/{field_id}.png     the crop that went to OCR for a field
/                                 the built frontend (frontend/dist)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import cv2
from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from optima_time.config.models import Profile
from optima_time.runner import Runner

NO_CACHE = {"Cache-Control": "no-store"}


def frontend_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "frontend" / "dist"


def create_app(runner: Runner, static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Optima Time", docs_url="/api/docs", openapi_url="/api/openapi.json")

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

    @app.get("/api/state")
    def get_state() -> Response:
        snap = runner.snapshot()
        result = snap.result
        fields = {}
        if result is not None:
            for fid, r in result.fields.items():
                fields[fid] = {
                    "status": r.status.value,
                    "text": r.text,
                    "raw": r.reading.text if r.reading else None,
                    "confidence": round(r.reading.confidence, 3) if r.reading else None,
                    "contrast": round(r.contrast, 1),
                }
        rect = snap.rectified
        body = {
            "source": runner.source_status(),
            "processing_fps": round(snap.processing_fps, 1),
            "frame": {"seq": result.seq, "pts": result.pts, "timings_ms": result.timings_ms}
            if result
            else None,
            "rectified_size": [rect.shape[1], rect.shape[0]] if rect is not None else None,
            "fields": fields,
        }
        return Response(content=_json(body), media_type="application/json", headers=NO_CACHE)

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

    static = static_dir or frontend_dir()
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="ui")
    return app


def _json(body: Any) -> str:
    import json

    return json.dumps(body, ensure_ascii=False)
