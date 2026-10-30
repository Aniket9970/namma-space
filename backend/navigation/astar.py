"""
navigation/astar.py
────────────────────────────────────────────────────────────────────────────
A* pathfinding on a 2D numpy occupancy grid.

Grid convention:
    0 = free (walkable)
    1 = occupied (obstacle)

Supports 8-directional movement. Diagonal moves cost sqrt(2).
"""

import heapq
import math
from typing import Optional

import numpy as np


def astar(
    grid: np.ndarray,
    start: tuple[int, int],
    end: tuple[int, int],
) -> list[tuple[int, int]]:
    """
    Find the shortest path from start to end on a 2D grid using A*.

    Parameters
    ----------
    grid  : 2D numpy array (rows × cols), 0=free, 1=occupied
    start : (row, col) of the start cell
    end   : (row, col) of the end cell

    Returns
    -------
    List of (row, col) tuples from start to end (inclusive),
    or an empty list if no path exists.
    """
    rows, cols = grid.shape
    start_row, start_col = start
    end_row, end_col = end

    # Validate
    if not (0 <= start_row < rows and 0 <= start_col < cols):
        return []
    if not (0 <= end_row < rows and 0 <= end_col < cols):
        return []
    if grid[start_row, start_col] == 1:
        # Nudge start to nearest free cell
        start = _nearest_free(grid, start)
        if start is None:
            return []
        start_row, start_col = start
    if grid[end_row, end_col] == 1:
        end = _nearest_free(grid, end)
        if end is None:
            return []
        end_row, end_col = end

    if (start_row, start_col) == (end_row, end_col):
        return [(start_row, start_col)]

    # 8-directional neighbours: (dr, dc, cost)
    NEIGHBOURS = [
        (-1,  0, 1.0),
        ( 1,  0, 1.0),
        ( 0, -1, 1.0),
        ( 0,  1, 1.0),
        (-1, -1, math.sqrt(2)),
        (-1,  1, math.sqrt(2)),
        ( 1, -1, math.sqrt(2)),
        ( 1,  1, math.sqrt(2)),
    ]

    def heuristic(r: int, c: int) -> float:
        # Octile distance (consistent with 8-dir movement)
        dr = abs(r - end_row)
        dc = abs(c - end_col)
        return (dr + dc) + (math.sqrt(2) - 2) * min(dr, dc)

    # open heap: (f, g, row, col)
    open_heap: list[tuple[float, float, int, int]] = []
    heapq.heappush(open_heap, (heuristic(start_row, start_col), 0.0, start_row, start_col))

    came_from: dict[tuple[int, int], Optional[tuple[int, int]]] = {
        (start_row, start_col): None
    }
    g_score: dict[tuple[int, int], float] = {(start_row, start_col): 0.0}

    while open_heap:
        _, g, r, c = heapq.heappop(open_heap)

        if (r, c) == (end_row, end_col):
            return _reconstruct(came_from, (end_row, end_col))

        if g > g_score.get((r, c), math.inf):
            continue  # stale entry

        for dr, dc, cost in NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            if grid[nr, nc] == 1:
                continue

            new_g = g + cost
            if new_g < g_score.get((nr, nc), math.inf):
                g_score[(nr, nc)] = new_g
                came_from[(nr, nc)] = (r, c)
                f = new_g + heuristic(nr, nc)
                heapq.heappush(open_heap, (f, new_g, nr, nc))

    return []  # no path found


def _reconstruct(
    came_from: dict[tuple[int, int], Optional[tuple[int, int]]],
    current: tuple[int, int],
) -> list[tuple[int, int]]:
    path = []
    while current is not None:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path


def _nearest_free(
    grid: np.ndarray,
    cell: tuple[int, int],
    search_radius: int = 5,
) -> Optional[tuple[int, int]]:
    """Find the nearest free cell within search_radius by BFS."""
    from collections import deque

    rows, cols = grid.shape
    visited = set()
    q: deque[tuple[int, int]] = deque([cell])
    visited.add(cell)

    while q:
        r, c = q.popleft()
        if grid[r, c] == 0:
            return (r, c)
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                nr, nc = r + dr, c + dc
                if (nr, nc) not in visited and 0 <= nr < rows and 0 <= nc < cols:
                    dist = abs(nr - cell[0]) + abs(nc - cell[1])
                    if dist <= search_radius:
                        visited.add((nr, nc))
                        q.append((nr, nc))
    return None
