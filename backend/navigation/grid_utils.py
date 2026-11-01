"""
navigation/grid_utils.py — Conversion helpers between world and grid coordinates.
"""


def world_to_grid(
    x: float,
    z: float,
    origin: tuple[float, float],
    cell_size: float,
) -> tuple[int, int]:
    """
    Convert 3D world (x, z) coordinates to grid (col, row).

    Parameters
    ----------
    x, z      : world position (Three.js X and Z)
    origin    : (origin_x, origin_z) — world position of grid[0, 0] corner
    cell_size : metres per grid cell

    Returns
    -------
    (col, row) integer grid indices
    """
    origin_x, origin_z = origin
    col = int((x - origin_x) / cell_size)
    row = int((z - origin_z) / cell_size)
    return col, row


def grid_to_world(
    row: int,
    col: int,
    origin: tuple[float, float],
    cell_size: float,
    floor_y: float = 0.0,
) -> tuple[float, float]:
    """
    Convert grid (row, col) to world (x, z) — centre of cell.

    Parameters
    ----------
    row, col  : grid indices
    origin    : (origin_x, origin_z) — world position of grid[0, 0] corner
    cell_size : metres per grid cell
    floor_y   : (unused here, kept for signature compatibility)

    Returns
    -------
    (world_x, world_z) at the centre of the specified cell
    """
    origin_x, origin_z = origin
    world_x = origin_x + (col + 0.5) * cell_size
    world_z = origin_z + (row + 0.5) * cell_size
    return world_x, world_z
