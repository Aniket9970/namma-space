"""
routers/reconstruction.py — Client router for internal reconstruction service binding.
Uses RECONSTRUCTION_SERVICE_URL injected by Vercel service binding.
"""

import json
import os
import urllib.request
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

# Bound internal service URL injected by Vercel
RECONSTRUCTION_SERVICE_URL = os.environ.get("RECONSTRUCTION_SERVICE_URL")


class TriggerJobBody(BaseModel):
    video_path: str
    scene_name: str
    metric_ref: Optional[float] = 2.0
    skip_splat: Optional[bool] = False


@router.get("/reconstruction/status")
async def get_reconstruction_status():
    """Query the internal reconstruction service for status."""
    service_url = os.environ.get("RECONSTRUCTION_SERVICE_URL")
    if not service_url:
        return {
            "status": "unbound",
            "message": "RECONSTRUCTION_SERVICE_URL binding is not set (running standalone)",
        }

    try:
        url = f"{service_url.rstrip('/')}/status"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "status": "connected",
                "service_url": service_url,
                "reconstruction": data,
            }
    except Exception as e:
        return {
            "status": "error",
            "service_url": service_url,
            "error": str(e),
        }


@router.post("/reconstruction/jobs")
async def trigger_reconstruction_job(body: TriggerJobBody):
    """Dispatch a new job to the internal reconstruction service."""
    service_url = os.environ.get("RECONSTRUCTION_SERVICE_URL")
    if not service_url:
        return {
            "status": "unbound",
            "message": "RECONSTRUCTION_SERVICE_URL binding is not set",
        }

    try:
        url = f"{service_url.rstrip('/')}/jobs"
        payload = json.dumps(body.dict()).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "status": "dispatched",
                "job": data,
            }
    except Exception as e:
        return {
            "status": "error",
            "service_url": service_url,
            "error": str(e),
        }
