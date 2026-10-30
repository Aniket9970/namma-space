"""
test/fixtures/test_astar.py — Unit tests for the A* pathfinding algorithm.
Run from the test/ directory: python fixtures/test_astar.py
"""

import sys
import math
import unittest
from pathlib import Path

# Allow importing from backend/
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))
from navigation.astar import astar


class TestAstar(unittest.TestCase):

    def test_astar_simple(self):
        """Direct horizontal path on a simple open grid."""
        grid = [
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
        ]
        import numpy as np
        g = np.array(grid, dtype=np.uint8)
        path = astar(g, (1, 0), (1, 4))
        self.assertTrue(len(path) > 0)
        self.assertEqual(path[0], (1, 0))
        self.assertEqual(path[-1], (1, 4))

    def test_astar_no_path(self):
        """Wall blocking all paths — should return empty list."""
        import numpy as np
        g = np.array([
            [0, 1, 0],
            [0, 1, 0],
            [0, 1, 0],
        ], dtype=np.uint8)
        path = astar(g, (1, 0), (1, 2))
        self.assertEqual(path, [])

    def test_astar_diagonal(self):
        """Diagonal path should be taken when shorter."""
        import numpy as np
        g = np.zeros((5, 5), dtype=np.uint8)
        path = astar(g, (0, 0), (4, 4))
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (4, 4))
        # Optimal diagonal path length should be 5 (0,0)→(1,1)→...→(4,4)
        self.assertLessEqual(len(path), 6)

    def test_astar_obstacle_snap(self):
        """Start or end inside obstacle — should snap to nearest free cell."""
        import numpy as np
        g = np.zeros((5, 5), dtype=np.uint8)
        g[2, 2] = 1  # place obstacle at start
        path = astar(g, (2, 2), (4, 4))
        self.assertTrue(len(path) > 0)
        self.assertEqual(path[-1], (4, 4))

    def test_astar_same_cell(self):
        """Start equals end — should return single-element list."""
        import numpy as np
        g = np.zeros((3, 3), dtype=np.uint8)
        path = astar(g, (1, 1), (1, 1))
        self.assertEqual(path, [(1, 1)])

    def test_astar_cost_diagonal(self):
        """Check diagonal step count is correct (Manhattan should be longer)."""
        import numpy as np
        g = np.zeros((10, 10), dtype=np.uint8)
        path = astar(g, (0, 0), (5, 5))
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (5, 5))
        # Diagonal path takes 5 steps for a (0,0)→(5,5) move
        self.assertEqual(len(path), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
