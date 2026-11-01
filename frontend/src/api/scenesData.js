// scenesData.js — Fallback scene and POI data for standalone / Vercel deployment
export const DEFAULT_SCENES = [
  {
    "id": 10,
    "name": "Ex4 Scene",
    "glb_path": "/static/models/ex4.glb",
    "splat_path": "/static/models/ex4.splat",
    "grid_path": "/static/navigation/ex4_grid.npy",
    "grid_meta_json": "{\n  \"origin\": [\n    -29.694438934326172,\n    -81.98799896240234\n  ],\n  \"cell_size\": 0.1,\n  \"rows\": 1640,\n  \"cols\": 594,\n  \"floor_y\": 0.0\n}",
    "tour_path": "/static/panoramas/ex4/tour.json",
    "created_at": "2026-10-31T21:41:39.117760+00:00"
  },
  {
    "id": 9,
    "name": "Ex3 Scene",
    "glb_path": "/static/models/ex3.glb",
    "splat_path": "/static/models/ex3.splat",
    "grid_path": "/static/navigation/ex3_grid.npy",
    "grid_meta_json": "{\n  \"origin\": [\n    -17.812761306762695,\n    -23.3879451751709\n  ],\n  \"cell_size\": 0.1,\n  \"rows\": 468,\n  \"cols\": 357,\n  \"floor_y\": 0.0\n}",
    "tour_path": "/static/panoramas/ex3/tour.json",
    "created_at": "2026-10-31T21:07:48.637039+00:00"
  },
  {
    "id": 8,
    "name": "Tour Video Scene",
    "glb_path": "/static/models/tour_video.glb",
    "splat_path": "/static/models/tour_video.splat",
    "grid_path": "/static/navigation/tour_video_grid.npy",
    "grid_meta_json": "{\n  \"origin\": [\n    -5.6317973136901855,\n    -8.362476348876953\n  ],\n  \"cell_size\": 0.1,\n  \"rows\": 168,\n  \"cols\": 113,\n  \"floor_y\": 0.0\n}",
    "tour_path": "/static/panoramas/tour_video/tour.json",
    "created_at": "2026-10-31T20:20:10.348181+00:00"
  },
  {
    "id": 7,
    "name": "Ex2 Scene",
    "glb_path": "/static/models/ex2.glb",
    "splat_path": "/static/models/ex2.splat",
    "grid_path": "/static/navigation/ex2_grid.npy",
    "grid_meta_json": "{\n  \"origin\": [\n    -7.484922885894775,\n    -8.03403377532959\n  ],\n  \"cell_size\": 0.1,\n  \"rows\": 161,\n  \"cols\": 150,\n  \"floor_y\": 0.0\n}",
    "tour_path": "/static/panoramas/ex2/tour.json",
    "created_at": "2026-10-31T20:12:08.110089+00:00"
  },
  {
    "id": 4,
    "name": "Roomvid Scene",
    "glb_path": "/static/models/roomvid.glb",
    "splat_path": "/static/models/roomvid.splat",
    "grid_path": "/static/navigation/roomvid_grid.npy",
    "grid_meta_json": "{\n  \"origin\": [\n    -6.657234191894531,\n    -10.359014511108398\n  ],\n  \"cell_size\": 0.1,\n  \"rows\": 208,\n  \"cols\": 134,\n  \"floor_y\": 0.0\n}",
    "tour_path": "/static/panoramas/roomvid/tour.json",
    "created_at": "2026-10-30T17:42:34.792420+00:00"
  },
  {
    "id": 12,
    "name": "Apartment Scene (Full Walkthrough)",
    "glb_path": "/static/models/sample_scene.glb",
    "splat_path": "/static/models/apartment.splat",
    "grid_path": "/static/navigation/sample_scene_grid.npy",
    "grid_meta_json": "{\n  \"origin\": [\n    -6.0,\n    -6.0\n  ],\n  \"cell_size\": 0.1,\n  \"rows\": 120,\n  \"cols\": 120,\n  \"floor_y\": 0.0\n}",
    "tour_path": "/static/panoramas/sample_scene/tour.json",
    "created_at": "2026-11-01T11:00:00.000000+00:00"
  }
];

export const DEFAULT_POIS = [
  // Scene 4: Roomvid Scene
  {
    "id": 10,
    "scene_id": 4,
    "name": "Entrance",
    "description": "Entryway into the space",
    "x": 0.0,
    "y": 0.0,
    "z": -1.5,
    "grid_row": null,
    "grid_col": null
  },
  {
    "id": 11,
    "scene_id": 4,
    "name": "Central Space",
    "description": "Central area of the room",
    "x": 0.0,
    "y": 0.0,
    "z": 1.0,
    "grid_row": null,
    "grid_col": null
  },
  {
    "id": 12,
    "scene_id": 4,
    "name": "Far Corner",
    "description": "Opposite corner of the space",
    "x": -1.2,
    "y": 0.0,
    "z": 3.0,
    "grid_row": null,
    "grid_col": null
  },
  // Scene 7: Ex2 Scene
  {
    "id": 16,
    "scene_id": 7,
    "name": "Entrance",
    "description": "Entryway into the space",
    "x": 0.0,
    "y": 0.0,
    "z": -1.5,
    "grid_row": null,
    "grid_col": null
  },
  {
    "id": 17,
    "scene_id": 7,
    "name": "Central Space",
    "description": "Central area of the room",
    "x": 0.0,
    "y": 0.0,
    "z": 1.0,
    "grid_row": null,
    "grid_col": null
  },
  {
    "id": 18,
    "scene_id": 7,
    "name": "Far Corner",
    "description": "Opposite corner of the space",
    "x": -1.2,
    "y": 0.0,
    "z": 3.0,
    "grid_row": null,
    "grid_col": null
  },
  // Scene 8: Tour Video Scene
  {
    "id": 19,
    "scene_id": 8,
    "name": "Entrance",
    "description": "Entryway into the space",
    "x": 0.0,
    "y": 0.0,
    "z": -1.5,
    "grid_row": null,
    "grid_col": null
  },
  {
    "id": 20,
    "scene_id": 8,
    "name": "Central Space",
    "description": "Central area of the room",
    "x": 0.0,
    "y": 0.0,
    "z": 1.0,
    "grid_row": null,
    "grid_col": null
  },
  {
    "id": 21,
    "scene_id": 8,
    "name": "Far Corner",
    "description": "Opposite corner of the space",
    "x": -1.2,
    "y": 0.0,
    "z": 3.0,
    "grid_row": null,
    "grid_col": null
  },
  // Scene 9: Ex3 Scene
  {
    "id": 22,
    "scene_id": 9,
    "name": "Entrance",
    "description": "Entryway into the space",
    "x": 0.0,
    "y": 0.0,
    "z": -1.5,
    "grid_row": null,
    "grid_col": null
  },
  {
    "id": 23,
    "scene_id": 9,
    "name": "Central Space",
    "description": "Central area of the room",
    "x": 0.0,
    "y": 0.0,
    "z": 1.0,
    "grid_row": null,
    "grid_col": null
  },
  {
    "id": 24,
    "scene_id": 9,
    "name": "Far Corner",
    "description": "Opposite corner of the space",
    "x": -1.2,
    "y": 0.0,
    "z": 3.0,
    "grid_row": null,
    "grid_col": null
  },
  // Scene 10: Ex4 Scene (Primary Default)
  {
    "id": 25,
    "scene_id": 10,
    "name": "Entrance",
    "description": "Entryway into the space",
    "x": 0.0,
    "y": 0.0,
    "z": -1.5,
    "grid_row": null,
    "grid_col": null
  },
  {
    "id": 26,
    "scene_id": 10,
    "name": "Central Space",
    "description": "Central area of the room",
    "x": 0.0,
    "y": 0.0,
    "z": 1.0,
    "grid_row": null,
    "grid_col": null
  },
  {
    "id": 27,
    "scene_id": 10,
    "name": "Far Corner",
    "description": "Opposite corner of the space",
    "x": -1.2,
    "y": 0.0,
    "z": 3.0,
    "grid_row": null,
    "grid_col": null
  },
  // Scene 12: Apartment Scene
  {
    "id": 104,
    "scene_id": 12,
    "name": "Living Room Center",
    "description": "Main open space of apartment",
    "x": 0.0,
    "y": 0.0,
    "z": 0.0,
    "grid_row": null,
    "grid_col": null
  },
  {
    "id": 105,
    "scene_id": 12,
    "name": "Balcony Window",
    "description": "Window with outdoor lighting",
    "x": 2.2,
    "y": 0.0,
    "z": -3.1,
    "grid_row": null,
    "grid_col": null
  }
];
