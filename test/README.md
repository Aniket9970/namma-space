# Test Data

This directory is intended to hold sample data for development and testing.

## Sample Data Structure

```
test/
├── README.md          ← you are here
├── sample_frames/     ← place test JPEG frames here (not committed — too large)
│   ├── frame_000000.jpg
│   ├── frame_000001.jpg
│   └── ...
├── sample_output/     ← example reconstruction outputs for local testing
│   ├── models/
│   │   ├── scene.glb       ← a small test GLB mesh (~5 MB)
│   │   └── scene.splat     ← a small test splat (~20 MB)
│   └── navigation/
│       ├── grid.npy            ← numpy occupancy grid
│       └── occupancy_meta.json ← grid metadata
└── fixtures/
    └── test_astar.py   ← unit tests for the A* algorithm
```

## Setting Up Test Data

1. **Download test assets** or generate them with a small room video (any ~30 second clip).
2. Run the frame extraction script:
   ```bash
   cd reconstruction
   python extract_frames.py --input ../test/sample_video.mp4 --fps 1 --output ../test/sample_frames
   ```
3. Copy generated `.glb` and occupancy files to `test/sample_output/` and then to `backend/static/` for testing the web viewer.

## Running the A* Unit Tests

```bash
cd test
python fixtures/test_astar.py
```

Expected output:
```
test_astar_simple ... ok
test_astar_no_path ... ok
test_astar_diagonal ... ok
test_astar_obstacle_snap ... ok
----------------------------------------------------------------------
Ran 4 tests in 0.003s

OK
```
