# Standard Operating Procedure — Indoor Space Capture
### Namma Space | Techfest IIT Bombay

---

## 1. Pre-Capture Checklist

Before entering the space, verify the following:

- [ ] **Battery** — Smartphone ≥ 80% charged. Bring a power bank.
- [ ] **Storage** — Minimum 10 GB free space for a medium room (30–60 m²).
- [ ] **Stabiliser** — Use a gimbal if possible. Otherwise ensure "Cinematic/Stabilised" mode is ON.
- [ ] **Camera app settings** locked in (see Section 2).
- [ ] **Area cleared** — Ask people to step out of the space; moving subjects ruin reconstruction.
- [ ] **Lighting ON** — All overhead lights on. Avoid shooting when lights are off.
- [ ] **Reflective hazards noted** — Mark mirrors, glass, and glossy floors for special treatment.
- [ ] **Room access** — Identify all doors to adjacent rooms for multi-room stitching.

---

## 2. Camera Settings

Use the **Pro/Manual** camera mode for consistent frames:

| Setting | Recommended Value | Reason |
|---|---|---|
| Resolution | 4K (3840 × 2160) | Maximum detail for reconstruction |
| Frame rate | 24–30 fps | Smooth motion; fast enough for 2 fps extraction |
| ISO | ≤ 400 | Minimise noise |
| Shutter speed | ≥ 1/60 s | Avoid motion blur |
| Focus | **Manual / locked** | Prevent focus hunting during sweep |
| White balance | **Manual / locked** (Daylight or Fluorescent depending on room) | Consistent exposure across frames |
| Stabilisation | ON | Reduce Laplacian rejection rate |
| HDR | **OFF** | HDR alters per-frame tone-mapping; inconsistent |

---

## 3. Walking Technique

### 3.1 Approach — Slow and Steady
- Walk at approximately **0.3–0.5 m/s** (shuffling pace).
- Hold the phone at **chest/eye height**, pointing slightly downward (~10–15° below horizontal) to capture both walls and floor.
- Keep the phone **stable** — avoid swinging arms.

### 3.2 Sweep Pattern
Follow this sequence for each room:

1. **Perimeter sweep** — Walk clockwise along all four walls, staying ~0.5–1 m from the wall. Keep the wall in the right half of frame.
2. **Corner coverage** — At each corner, make a slow **180° arc** facing the corner, capturing it from multiple angles.
3. **Diagonal sweeps** — Walk diagonally across the room (corner to corner) twice.
4. **Centre spin** — Stand in the centre and slowly rotate 360° once.
5. **Ceiling pass** — Tilt the phone upward to capture the ceiling texture and light fixtures (important for orientation lock).

---

## 4. Frame Overlap

COLMAP requires sufficient feature correspondence between consecutive frames.

- **Target overlap: ≥ 60%** between any two adjacent extracted frames.
- At **2 fps extraction** and **0.5 m/s walk speed**, each step covers ~0.25 m — typically sufficient.
- **If the room is large (> 50 m²):** reduce walking speed to 0.3 m/s or increase extraction FPS to 3.

---

## 5. Corner Shots

Corners are the hardest regions for SfM because of depth ambiguity. Apply the **corner protocol**:

1. Stop 0.5 m from the corner.
2. Point camera directly at the corner.
3. **Slowly pan left → right** by ~45° while keeping the corner in frame.
4. Then pan **up → down** to cover floor-to-ceiling.
5. Step closer to 0.3 m and repeat the arc.

This gives COLMAP enough angular diversity to triangulate the corner geometry.

---

## 6. Dealing with Reflective Surfaces

Reflective surfaces (mirrors, glass walls, glossy floors) cause "ghost" geometry in NeRF/3DGS.

| Surface Type | Mitigation |
|---|---|
| **Mirror** | Cover with a plain matte cloth or poster during capture. Unmask after. |
| **Glass wall/door** | Capture from an oblique angle (≥ 45°) so the reflection shifts. Avoid head-on. |
| **Glossy floor** | Add cross-polarised lighting if available. Alternatively, place matte paper squares as visual markers. |
| **Window (bright outside)** | Close blinds/curtains to prevent overexposure of the window region. |

> [!WARNING]
> Leaving large mirrors uncovered will produce "mirrored room" artifacts. The reconstruction will appear as if the room doubles in size.

---

## 7. Lighting Guidelines

Good lighting is the single biggest factor in reconstruction quality.

- **Prefer diffuse, even lighting** — multiple soft light sources are better than a single harsh overhead.
- **Avoid mixed colour temperatures** — don't mix daylight from windows with warm incandescent bulbs. Close windows or use white-balance lock.
- **Minimum lux:** ~200 lux at floor level. Supplement with portable LED panels if needed.
- **Dark alcoves:** illuminate individually. The extraction script rejects blurry/underexposed frames.
- **Avoid direct sunlight patches** on floor — moving cloud shadows change between frames and confuse matching.

---

## 8. Multi-Room Stitching

When capturing a space with multiple connected rooms:

1. Capture each room individually using the procedure above.
2. **Transition corridor:** at every doorway, record a **slow 10-second walk-through** from one room to the other and back. This gives COLMAP overlapping frames to stitch the two point clouds.
3. Repeat for every room pair that shares a doorway.
4. Process all frames together in a single COLMAP run (put all frames in the same `output/frames/` folder).

> [!TIP]
> For large venues (> 10 rooms), split into wing-level COLMAP runs and merge sparse models with COLMAP model_merger, then re-run `ns-train nerfacto` on the merged output.

---

## 9. Verification Checklist (Post-Capture)

Before handing off to the reconstruction pipeline:

- [ ] Total video duration ≥ 5 minutes for a medium room.
- [ ] Frame count after extraction ≥ 300 (run `ls output/frames/ | wc -l`).
- [ ] Spot-check 10 random frames — none should be motion-blurred or extremely dark.
- [ ] COLMAP feature extraction report: ≥ 1000 features per image on average.
- [ ] COLMAP mapper registers ≥ 90% of images.
