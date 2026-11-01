"""
reconstruction/main.py — Internal Reconstruction Service for Namma Space.
Provides health, status, and job dispatch for 3D reconstruction pipelines.
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List
import datetime

app = FastAPI(
    title="Namma Space Reconstruction Service",
    description="Internal microservice for 3D reconstruction and spatial processing jobs.",
    version="1.0.0",
)


class JobRequest(BaseModel):
    video_path: str
    scene_name: str
    metric_ref: Optional[float] = 2.0
    skip_splat: Optional[bool] = False


# In-memory job registry for internal tracking
JOBS = []


@app.get("/")
@app.get("/health")
def health():
    return {"status": "ok", "service": "reconstruction", "timestamp": datetime.datetime.utcnow().isoformat()}


@app.get("/status")
def status():
    return {
        "status": "idle",
        "service": "reconstruction",
        "available_stages": [
            "frame_extraction",
            "pose_estimation",
            "photosphere_alignment",
            "occupancy_grid",
            "gaussian_splatting_export",
        ],
        "active_jobs": len([j for j in JOBS if j.get("status") == "running"]),
        "total_jobs": len(JOBS),
    }


@app.post("/jobs")
def create_job(req: JobRequest):
    job = {
        "id": len(JOBS) + 1,
        "video_path": req.video_path,
        "scene_name": req.scene_name,
        "metric_ref": req.metric_ref,
        "skip_splat": req.skip_splat,
        "status": "queued",
        "created_at": datetime.datetime.utcnow().isoformat(),
    }
    JOBS.append(job)
    return job
