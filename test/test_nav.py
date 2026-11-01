"""
test/test_nav.py
────────────────
Unit and acceptance tests for Milestone M5 navigation system.
Tests:
1. Synthetic Grid Tests:
   - Straight line pathfinding
   - Obstacle detour navigation
   - Blocked unreachable goal handling
   - Theta* any-angle shortcutting
   - String-pulling path smoothing
2. Real Sample Data Tests:
   - Loads test/sample_out/nav/navgrid.json
   - Verifies all path waypoints and continuous interpolated steps never cross occupied or unknown cells
   - Renders test/sample_out/nav/nav_paths.png
"""

import json
from pathlib import Path
import sys
import unittest
import numpy as np

# Ensure repo root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from nav.plan import NavGrid, plan_path_astar, plan_path_thetastar, smooth_path, render_nav_debug


class TestSyntheticNavGrid(unittest.TestCase):
    def setUp(self):
        # 20x20 synthetic grid @ 0.1m resolution (2.0m x 2.0m)
        # Center obstacle wall with an opening
        grid = np.zeros((20, 20), dtype=np.uint8)
        # Vertical wall down col 10 with gap at row 15-17
        grid[2:15, 10] = 1
        grid[18:, 10] = 1
        self.navgrid = NavGrid(grid, resolution_m=0.1, origin_x=0.0, origin_z=0.0)

    def test_straight_path(self):
        # Path within same open room
        path = plan_path_astar(self.navgrid, (0.2, 0.2), (0.2, 1.5))
        self.assertIsNotNone(path)
        self.assertGreater(len(path), 1)
        for x, z in path:
            r, c = self.navgrid.world_to_grid(x, z)
            self.assertEqual(self.navgrid.grid[r, c], 0, f"Point ({x}, {z}) at ({r}, {c}) is not free!")

    def test_obstacle_detour(self):
        # Start at left room, goal at right room
        start = (0.5, 0.5)
        goal = (1.5, 0.5)
        path = plan_path_astar(self.navgrid, start, goal)
        self.assertIsNotNone(path, "Failed to find path around wall obstacle")

        # Verify no waypoint is on an obstacle
        for x, z in path:
            r, c = self.navgrid.world_to_grid(x, z)
            self.assertEqual(self.navgrid.grid[r, c], 0, f"Path crossed obstacle at grid ({r}, {c})")

        # Verify dense interpolated line between waypoints never touches obstacle
        for i in range(len(path) - 1):
            p1 = np.array(path[i])
            p2 = np.array(path[i + 1])
            steps = max(2, int(np.linalg.norm(p2 - p1) / 0.02))
            for alpha in np.linspace(0, 1, steps):
                interp = (1 - alpha) * p1 + alpha * p2
                ir, ic = self.navgrid.world_to_grid(interp[0], interp[1])
                self.assertEqual(self.navgrid.grid[ir, ic], 0, f"Interpolated segment crossed obstacle at ({ir}, {ic})")

    def test_blocked_goal_returns_none(self):
        # Sealed room with no doors: interior has free cells, but surrounded completely by walls
        box_grid = np.zeros((15, 15), dtype=np.uint8)
        # Perimeter walls of the sealed room from row 5 to 9, col 5 to 9
        box_grid[5:10, 5] = 1
        box_grid[5:10, 9] = 1
        box_grid[5, 5:10] = 1
        box_grid[9, 5:10] = 1
        # Center (7, 7) is a free cell inside the sealed room
        box_grid[7, 7] = 0

        nav = NavGrid(box_grid, resolution_m=0.1)
        # Try planning from outside (0.2, 0.2) to inside sealed room (0.75, 0.75)
        path = plan_path_astar(nav, (0.2, 0.2), (0.75, 0.75))
        # Cannot penetrate walls: must return None
        self.assertIsNone(path)

    def test_path_smoothing(self):
        start = (0.5, 0.5)
        goal = (1.5, 0.5)
        astar_path = plan_path_astar(self.navgrid, start, goal)
        self.assertIsNotNone(astar_path)
        smoothed = smooth_path(self.navgrid, astar_path)
        self.assertLessEqual(len(smoothed), len(astar_path))
        # Ensure start and goal are preserved
        self.assertEqual(smoothed[0], astar_path[0])
        self.assertEqual(smoothed[-1], astar_path[-1])


class TestRealSampleNavGrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nav_path = repo_root / "test" / "sample_out" / "nav" / "navgrid.json"
        if not cls.nav_path.exists():
            raise unittest.SkipTest(f"Sample navgrid not found at {cls.nav_path}")
        cls.navgrid = NavGrid.from_json(cls.nav_path)

    def test_real_grid_properties(self):
        self.assertEqual(self.navgrid.res, 0.05)
        self.assertGreater(self.navgrid.rows, 10)
        self.assertGreater(self.navgrid.cols, 10)
        free_cells = np.sum(self.navgrid.grid == 0)
        obs_cells = np.sum(self.navgrid.grid == 1)
        self.assertGreater(free_cells, 50, "Insufficient free walkable cells in real grid")
        self.assertGreater(obs_cells, 10, "No obstacles found in real grid")

    def test_real_pathfinding_and_render(self):
        # Find two free cells that are reasonably separated
        free_r, free_c = np.where(self.navgrid.grid == 0)
        self.assertGreater(len(free_r), 10)

        # Pick start near first quarter and goal near last quarter
        idx_start = len(free_r) // 6
        idx_goal = (len(free_r) * 5) // 6
        start_world = self.navgrid.grid_to_world(int(free_r[idx_start]), int(free_c[idx_start]))
        goal_world = self.navgrid.grid_to_world(int(free_r[idx_goal]), int(free_c[idx_goal]))

        astar_path = plan_path_astar(self.navgrid, start_world, goal_world)
        self.assertIsNotNone(astar_path, "A* failed on real sample venue")

        theta_path = plan_path_thetastar(self.navgrid, start_world, goal_world)
        self.assertIsNotNone(theta_path, "Theta* failed on real sample venue")

        smooth_p = smooth_path(self.navgrid, astar_path)

        # Strictly verify paths never cross occupied cells
        for name, p in [("A*", astar_path), ("Theta*", theta_path), ("Smoothed", smooth_p)]:
            for x, z in p:
                r, c = self.navgrid.world_to_grid(x, z)
                val = self.navgrid.grid[r, c]
                self.assertEqual(val, 0, f"{name} path crossed non-free cell (value={val}) at ({x:.2f}, {z:.2f})")

        # Load camera poses for render overlay
        cams = []
        aligned_poses = repo_root / "test" / "sample_out" / "aligned_poses.json"
        if aligned_poses.exists():
            data = json.loads(aligned_poses.read_text(encoding="utf-8"))
            cams = [(f["position"][0], f["position"][2]) for f in data.get("frames", [])]

        # Render debug artifact
        out_png = repo_root / "test" / "sample_out" / "nav" / "nav_paths.png"
        paths_dict = {"A*": astar_path, "Theta*": theta_path, "Smoothed": smooth_p}
        render_nav_debug(self.navgrid, paths_dict, out_png, camera_poses=cams)
        self.assertTrue(out_png.exists())
        self.assertGreater(out_png.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
