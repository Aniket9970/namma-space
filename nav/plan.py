"""
nav/plan.py
───────────
Python Reference Path Planner for Milestone M5.
Implements:
1. NavGrid: Occupancy grid abstraction (free=0, obstacle=1, unknown=2).
2. A* Pathfinding: 8-connected grid search with Euclidean distance heuristic.
3. Theta* Pathfinding: Any-angle pathfinding checking line-of-sight across grid cells.
4. Path Smoothing: String-pulling / raycast shortcutting.
5. Coordinate Conversion: World coordinates (x, z in metres) <-> Grid indices (row, col).
6. Visualization: Debug renderer producing out/nav/nav_paths.png.
"""

import heapq
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


class NavGrid:
    def __init__(
        self,
        grid: np.ndarray,
        resolution_m: float = 0.05,
        origin_x: float = 0.0,
        origin_z: float = 0.0,
        floor_y: float = 0.0,
    ):
        self.grid = grid.astype(np.uint8)  # 0=free, 1=obstacle, 2=unknown
        self.rows, self.cols = grid.shape
        self.res = float(resolution_m)
        self.origin_x = float(origin_x)
        self.origin_z = float(origin_z)
        self.floor_y = float(floor_y)

    @classmethod
    def from_json(cls, json_path: Path | str) -> "NavGrid":
        data = json.loads(Path(json_path).read_text(encoding="utf-8"))
        res = data.get("resolution_m", 0.05)
        origin = data.get("origin", [0.0, 0.0])
        w = data.get("width")
        h = data.get("height")
        raw_data = data.get("data", [])
        grid = np.array(raw_data, dtype=np.uint8).reshape((h, w))
        floor_y = data.get("floor_y", 0.0)
        return cls(grid, resolution_m=res, origin_x=origin[0], origin_z=origin[1], floor_y=floor_y)

    def world_to_grid(self, x: float, z: float) -> Tuple[int, int]:
        """Convert world (x, z in metres) to grid (row, col)."""
        col = int(math.floor((x - self.origin_x) / self.res))
        row = int(math.floor((z - self.origin_z) / self.res))
        return row, col

    def grid_to_world(self, row: int, col: int) -> Tuple[float, float]:
        """Convert grid (row, col) to world center (x, z in metres)."""
        x = self.origin_x + (col + 0.5) * self.res
        z = self.origin_z + (row + 0.5) * self.res
        return round(x, 4), round(z, 4)

    def is_in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols

    def is_walkable(self, row: int, col: int) -> bool:
        """Walkable if strictly within bounds and value == 0 (free)."""
        if not self.is_in_bounds(row, col):
            return False
        return self.grid[row, col] == 0

    def find_nearest_walkable(self, row: int, col: int, max_radius: int = 15) -> Optional[Tuple[int, int]]:
        """If target cell is obstacle or out of bounds, find closest walkable neighbor."""
        if self.is_walkable(row, col):
            return row, col
        for r in range(1, max_radius + 1):
            for dr in range(-r, r + 1):
                for dc in range(-r, r + 1):
                    if abs(dr) == r or abs(dc) == r:
                        nr, nc = row + dr, col + dc
                        if self.is_walkable(nr, nc):
                            return nr, nc
        return None

    def line_of_sight(self, r0: int, c0: int, r1: int, c1: int) -> bool:
        """
        Bresenham raycast line-of-sight check.
        Returns True if line segment between (r0, c0) and (r1, c1) traverses only walkable cells.
        """
        dr = abs(r1 - r0)
        dc = abs(c1 - c0)
        r = r0
        c = c0
        sr = 1 if r1 > r0 else -1
        sc = 1 if c1 > c0 else -1

        if dr > dc:
            err = dr // 2
            while r != r1:
                if not self.is_walkable(r, c):
                    return False
                err -= dc
                if err < 0:
                    c += sc
                    err += dr
                r += sr
        else:
            err = dc // 2
            while c != c1:
                if not self.is_walkable(r, c):
                    return False
                err -= dr
                if err < 0:
                    r += sr
                    err += dc
                c += sc

        return self.is_walkable(r1, c1)


def plan_path_astar(
    navgrid: NavGrid,
    start_world: Tuple[float, float],
    goal_world: Tuple[float, float],
) -> Optional[List[Tuple[float, float]]]:
    """
    Standard 8-connected A* search with Euclidean heuristic.
    Returns path as list of (x, z) world coordinates in metres.
    """
    s_r, s_c = navgrid.world_to_grid(start_world[0], start_world[1])
    g_r, g_c = navgrid.world_to_grid(goal_world[0], goal_world[1])

    start_cell = navgrid.find_nearest_walkable(s_r, s_c)
    goal_cell = navgrid.find_nearest_walkable(g_r, g_c)

    if not start_cell or not goal_cell:
        return None

    s_r, s_c = start_cell
    g_r, g_c = goal_cell

    if (s_r, s_c) == (g_r, g_c):
        return [navgrid.grid_to_world(s_r, s_c)]

    # 8-connected movements: (dr, dc, cost)
    SQRT2 = math.sqrt(2.0)
    moves = [
        (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
        (-1, -1, SQRT2), (-1, 1, SQRT2), (1, -1, SQRT2), (1, 1, SQRT2),
    ]

    def heuristic(r: int, c: int) -> float:
        return math.hypot(r - g_r, c - g_c)

    frontier = []
    heapq.heappush(frontier, (heuristic(s_r, s_c), 0.0, (s_r, s_c)))
    cost_so_far = {(s_r, s_c): 0.0}
    came_from = {(s_r, s_c): None}

    found = False
    while frontier:
        _, current_cost, current = heapq.heappop(frontier)
        if current == (g_r, g_c):
            found = True
            break

        cr, cc = current
        for dr, dc, step_cost in moves:
            nr, nc = cr + dr, cc + dc
            if not navgrid.is_walkable(nr, nc):
                continue
            # Prevent diagonal corner cutting through obstacles
            if dr != 0 and dc != 0:
                if not navgrid.is_walkable(cr + dr, cc) or not navgrid.is_walkable(cr, cc + dc):
                    continue

            new_cost = current_cost + step_cost
            if (nr, nc) not in cost_so_far or new_cost < cost_so_far[(nr, nc)]:
                cost_so_far[(nr, nc)] = new_cost
                priority = new_cost + heuristic(nr, nc)
                heapq.heappush(frontier, (priority, new_cost, (nr, nc)))
                came_from[(nr, nc)] = current

    if not found:
        return None

    # Reconstruct grid path
    curr = (g_r, g_c)
    grid_path = []
    while curr is not None:
        grid_path.append(curr)
        curr = came_from[curr]
    grid_path.reverse()

    # Convert to world coordinates
    world_path = [navgrid.grid_to_world(r, c) for r, c in grid_path]
    return world_path


def plan_path_thetastar(
    navgrid: NavGrid,
    start_world: Tuple[float, float],
    goal_world: Tuple[float, float],
) -> Optional[List[Tuple[float, float]]]:
    """
    Theta* Any-Angle Pathfinding.
    Checks line-of-sight from parent cell directly to neighbor, eliminating grid octile artifacts.
    """
    s_r, s_c = navgrid.world_to_grid(start_world[0], start_world[1])
    g_r, g_c = navgrid.world_to_grid(goal_world[0], goal_world[1])

    start_cell = navgrid.find_nearest_walkable(s_r, s_c)
    goal_cell = navgrid.find_nearest_walkable(g_r, g_c)

    if not start_cell or not goal_cell:
        return None

    s_r, s_c = start_cell
    g_r, g_c = goal_cell

    if (s_r, s_c) == (g_r, g_c):
        return [navgrid.grid_to_world(s_r, s_c)]

    def heuristic(r: int, c: int) -> float:
        return math.hypot(r - g_r, c - g_c)

    frontier = []
    heapq.heappush(frontier, (heuristic(s_r, s_c), 0.0, (s_r, s_c)))
    cost_so_far = {(s_r, s_c): 0.0}
    parent = {(s_r, s_c): (s_r, s_c)}

    SQRT2 = math.sqrt(2.0)
    moves = [
        (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
        (-1, -1, SQRT2), (-1, 1, SQRT2), (1, -1, SQRT2), (1, 1, SQRT2),
    ]

    found = False
    while frontier:
        _, current_cost, current = heapq.heappop(frontier)
        if current == (g_r, g_c):
            found = True
            break

        cr, cc = current
        p_node = parent[current]

        for dr, dc, step_cost in moves:
            nr, nc = cr + dr, cc + dc
            neighbor = (nr, nc)
            if not navgrid.is_walkable(nr, nc):
                continue
            if dr != 0 and dc != 0:
                if not navgrid.is_walkable(cr + dr, cc) or not navgrid.is_walkable(cr, cc + dc):
                    continue

            # Theta* check: can neighbor see current's parent directly?
            pr, pc = p_node
            if navgrid.line_of_sight(pr, pc, nr, nc):
                # Line of sight clear: link neighbor directly to parent!
                alt_cost = cost_so_far[p_node] + math.hypot(nr - pr, nc - pc)
                if neighbor not in cost_so_far or alt_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = alt_cost
                    parent[neighbor] = p_node
                    priority = alt_cost + heuristic(nr, nc)
                    heapq.heappush(frontier, (priority, alt_cost, neighbor))
            else:
                # Normal A* expansion
                alt_cost = cost_so_far[current] + step_cost
                if neighbor not in cost_so_far or alt_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = alt_cost
                    parent[neighbor] = current
                    priority = alt_cost + heuristic(nr, nc)
                    heapq.heappush(frontier, (priority, alt_cost, neighbor))

    if not found:
        return None

    # Reconstruct path
    curr = (g_r, g_c)
    grid_path = []
    while curr != parent[curr]:
        grid_path.append(curr)
        curr = parent[curr]
    grid_path.append(curr)
    grid_path.reverse()

    world_path = [navgrid.grid_to_world(r, c) for r, c in grid_path]
    return world_path


def smooth_path(navgrid: NavGrid, world_path: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    String-pulling / raycast shortcutting.
    Reduces path to minimal waypoint corners while strictly preserving clearance.
    """
    if len(world_path) <= 2:
        return world_path

    smoothed = [world_path[0]]
    curr_idx = 0

    while curr_idx < len(world_path) - 1:
        # Greedily look ahead for furthest visible waypoint
        furthest_idx = curr_idx + 1
        for test_idx in range(len(world_path) - 1, curr_idx, -1):
            r0, c0 = navgrid.world_to_grid(world_path[curr_idx][0], world_path[curr_idx][1])
            r1, c1 = navgrid.world_to_grid(world_path[test_idx][0], world_path[test_idx][1])
            if navgrid.line_of_sight(r0, c0, r1, c1):
                furthest_idx = test_idx
                break

        smoothed.append(world_path[furthest_idx])
        curr_idx = furthest_idx

    return smoothed


def render_nav_debug(
    navgrid: NavGrid,
    paths: Dict[str, List[Tuple[float, float]]],
    out_png: Path,
    camera_poses: Optional[List[Tuple[float, float]]] = None,
):
    """
    Render 2D visualization of the navigation grid, obstacles, and planned paths.
    """
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 10))
    fig.patch.set_facecolor("#1e1e1e")
    ax.set_facecolor("#121212")

    # Colormap: 0=free (#2a2a2a), 1=obstacle (#cc3333), 2=unknown (#0a0a0a)
    display_grid = np.zeros((*navgrid.grid.shape, 3), dtype=np.uint8)
    display_grid[navgrid.grid == 0] = [45, 55, 65]    # Free / walkable
    display_grid[navgrid.grid == 1] = [210, 40, 40]   # Obstacle
    display_grid[navgrid.grid == 2] = [15, 15, 18]    # Unknown / unobserved

    extent = [
        navgrid.origin_x,
        navgrid.origin_x + navgrid.cols * navgrid.res,
        navgrid.origin_z + navgrid.rows * navgrid.res,
        navgrid.origin_z,
    ]

    ax.imshow(display_grid, extent=extent, interpolation="nearest")

    # Draw camera poses if provided
    if camera_poses:
        cx = [p[0] for p in camera_poses]
        cz = [p[1] for p in camera_poses]
        ax.plot(cx, cz, "-o", color="#00ffcc", markersize=3, linewidth=1.2, alpha=0.7, label="Camera Path")

    # Plot paths
    colors = {"A*": "#ffbb00", "Theta*": "#33ff77", "Smoothed": "#ff33dd"}
    for name, p_pts in paths.items():
        if not p_pts:
            continue
        xs = [pt[0] for pt in p_pts]
        zs = [pt[1] for pt in p_pts]
        color = colors.get(name, "#ffffff")
        ax.plot(xs, zs, "-o", color=color, markersize=5, linewidth=2.5, label=f"Path: {name}")
        ax.scatter([xs[0]], [zs[0]], color="#00ff00", s=80, zorder=5, label=f"{name} Start" if name == "A*" else None)
        ax.scatter([xs[-1]], [zs[-1]], color="#ff0000", s=80, zorder=5, label=f"{name} Goal" if name == "A*" else None)

    ax.set_xlabel("X (metres)", color="#ffffff")
    ax.set_ylabel("Z (metres)", color="#ffffff")
    ax.set_title("Namma Space — 2D Occupancy Grid & Obstacle-Aware Paths (M5)", color="#ffffff", fontsize=12)
    ax.tick_params(colors="#aaaaaa")
    ax.grid(True, color="#444444", linestyle="--", linewidth=0.5)
    ax.legend(loc="upper right", facecolor="#222222", edgecolor="#555555", labelcolor="#ffffff")

    plt.tight_layout()
    plt.savefig(str(out_png), dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print(f"[OK] NavGrid debug render saved -> {out_png}")

