"""
pipeline/stages/export.py
─────────────────────────
Stage 7: Web Asset Packaging & Database Registration.
Generates out/tour.json and out/pois.json conforming to data contracts.
Copies deliverables to backend/static/ and registers scene in SQLite database.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
from typing import Any, Dict

from .base import BaseStage
from ..config import PipelineConfig


class ExportStage(BaseStage):
    def __init__(self):
        super().__init__(
            name="export",
            description="Package tour.json manifest and sync deliverables to backend",
        )

    def is_cached(self, out_dir: Path, config: PipelineConfig) -> bool:
        tour_json = out_dir / "tour.json"
        pois_json = out_dir / "pois.json"
        return tour_json.exists() and pois_json.exists()

    def execute(
        self,
        input_path: Path,
        out_dir: Path,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        nodes = context.get("nodes", [])
        if not nodes:
            # Fallback default node
            nodes = [{
                "id": "n000",
                "position": [0.0, config.general.eye_height, 0.0],
                "rotation": [0.0, 0.0, 0.0, 1.0],
                "pano": {
                    "type": "equirect",
                    "url": "panos/n000.jpg",
                    "lod_url": "panos/n000_lod.jpg",
                    "depth_url": "depth/n000.png",
                },
                "neighbors": [],
            }]

        tour_manifest = {
            "meta": {
                "units": config.general.units,
                "up": config.general.coordinate_system.split("-")[0],
                "floor_y": config.general.target_floor_y,
                "scale_method": config.general.scale_method,
            },
            "nodes": nodes,
            "proxy_mesh": "mesh/proxy.glb",
            "navmesh": "mesh/navmesh.glb",
            "navgrid": "nav/navgrid.json",
        }

        tour_path = out_dir / "tour.json"
        tour_path.write_text(json.dumps(tour_manifest, indent=2), encoding="utf-8")
        print(f"[OK] Generated Master Tour Manifest -> {tour_path} ({len(nodes)} nodes)")

        # Generate default POIs contract
        pois = []
        for i, n in enumerate(nodes):
            name = f"Area {i+1}" if i > 0 else "Entrance"
            pois.append({
                "id": f"poi_{n['id']}",
                "name": name,
                "category": "Navigation",
                "aliases": [name.lower()],
                "position": [n["position"][0], config.general.target_floor_y, n["position"][2]],
                "node_id": n["id"],
                "source": "manual",
            })

        pois_path = out_dir / "pois.json"
        pois_path.write_text(json.dumps(pois, indent=2), encoding="utf-8")
        print(f"[OK] Generated POI Catalog -> {pois_path} ({len(pois)} POIs)")

        # Sync assets to backend/static
        backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
        backend_static = backend_dir / "static"
        if backend_static.exists():
            slug = input_path.stem.lower().replace(" ", "_").replace("-", "_") if input_path.is_file() else "sample_scene"
            dest_tour_dir = backend_static / "panoramas" / slug
            dest_tour_dir.mkdir(parents=True, exist_ok=True)

            # Copy panos
            panos_src = out_dir / "panos"
            if panos_src.exists():
                for f in panos_src.glob("*.jpg"):
                    shutil.copy2(str(f), str(dest_tour_dir / f.name))

            # Copy tour.json
            shutil.copy2(str(tour_path), str(dest_tour_dir / "tour.json"))

            # Copy models
            models_dest = backend_static / "models"
            models_dest.mkdir(parents=True, exist_ok=True)
            proxy_src = out_dir / "mesh" / "proxy.glb"
            if proxy_src.exists():
                shutil.copy2(str(proxy_src), str(models_dest / f"{slug}.glb"))
                shutil.copy2(str(proxy_src), str(models_dest / "scene.glb"))

            # Copy nav
            nav_dest = backend_static / "navigation"
            nav_dest.mkdir(parents=True, exist_ok=True)
            navgrid_src = out_dir / "nav" / "navgrid.json"
            if navgrid_src.exists():
                shutil.copy2(str(navgrid_src), str(nav_dest / "navgrid.json"))

            # Sync SQLite scene
            db_path = backend_dir / "namma_space.db"
            if db_path.exists():
                try:
                    conn = sqlite3.connect(str(db_path))
                    cur = conn.cursor()
                    scene_name = f"{slug.replace('_', ' ').title()} Scene"
                    existing = cur.execute("SELECT id FROM scenes WHERE name = ?", (scene_name,)).fetchone()
                    tour_url = f"/static/panoramas/{slug}/tour.json"
                    glb_url = f"/static/models/{slug}.glb"
                    grid_url = f"/static/navigation/{slug}_grid.npy"
                    now_str = datetime.now(timezone.utc).isoformat()
                    if not existing:
                        cur.execute(
                            "INSERT INTO scenes (name, glb_path, splat_path, grid_path, tour_path, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (scene_name, glb_url, f"/static/models/{slug}.splat", grid_url, tour_url, now_str)
                        )
                    else:
                        cur.execute(
                            "UPDATE scenes SET glb_path = ?, tour_path = ? WHERE id = ?",
                            (glb_url, tour_url, existing[0])
                        )
                    conn.commit()
                    conn.close()
                    print(f"[OK] Synced scene '{scene_name}' in backend database.")
                except Exception as e:
                    print(f"[WARN] Database sync exception: {e}")

        context["tour_manifest"] = tour_manifest
        context["pois"] = pois
        return context

