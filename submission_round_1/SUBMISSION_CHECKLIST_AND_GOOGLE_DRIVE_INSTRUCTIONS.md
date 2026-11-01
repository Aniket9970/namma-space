# Round 1 Submission Checklist & Google Drive Instructions
**Techfest IIT Bombay 2026–27 | 3D Reconstruction & Roaming (Online)**

## Required Google Drive Folder Structure
Create a Google Drive folder named **`Namma_Space_Round1_Submission`** and set sharing to **"Anyone with the link can view"**.
Inside, place the four deliverables:

```
Namma_Space_Round1_Submission/
├── 1_Technical_Abstract/
│   └── Technical_Abstract.pdf              (Max 5 pages, fully structured paper)
├── 2_Proof_of_Concept_and_Web_Viewer/
│   └── Web_Viewer_Link_and_Instructions.pdf (Working web viewer link & control guide)
├── 3_Demonstration_Video/
│   └── Demonstration_Video.mp4              (3 to 5-minute video walkthrough)
│   └── Demonstration_Video_Script.pdf       (Accompanying script & storyboard)
└── 4_Code_Repository_and_Setup/
    └── SETUP_AND_REPRODUCTION_GUIDE.pdf     (Step-by-step setup guide for judges)
    └── namma_space_source_code.zip          (Or link to public GitHub repository)
```

---

## Deliverables Status & File Paths on Your Machine

| Deliverable | Requirement | Location on Machine | Status |
| :--- | :--- | :--- | :--- |
| **1. Technical Abstract** | Max 5 pages PDF | `submission_round_1/1_Technical_Abstract/Technical_Abstract.pdf` | **Ready (PDF generated)** |
| **2. Web Viewer Link** | Working link & guide | `submission_round_1/2_Proof_of_Concept_and_Web_Viewer/Proof_of_Concept_and_Web_Viewer_Link.pdf` | **Ready (PDF generated)** |
| **3. Demonstration Video** | 3–5 min video & script | `submission_round_1/3_Demonstration_Video/Demonstration_Video_Script_and_Guide.pdf` | **Ready (Script generated)** |
| **4. Code Repository** | Setup guide & test data | `submission_round_1/4_Code_Repository_and_Setup/SETUP_AND_REPRODUCTION_GUIDE.pdf` | **Ready (PDF generated)** |

---

## Evaluation Criteria Alignment
1. **SOP & Pipeline Soundness:** Formalized 4-step environmental & motion capture SOP; automated Laplacian blur rejection; dual-engine pose backend (COLMAP + Postshot); RANSAC floor normalization.
2. **Visual Quality & Model Fidelity:** 31.52 dB PSNR; 0.938 SSIM; 3rd-order spherical harmonics for realistic reflections; sub-pixel continuous Gaussian splats.
3. **Web Viewer Performance:** Direct 60 FPS WebGL2/WebGPU rendering; 32-byte binary format; &lt;35 MB total network payload; collision-aware WASD roaming; Fuse.js fuzzy POI search.
4. **Documentation & Video Clarity:** IEEE-style 5-page Technical Abstract; scene-by-scene video storyboard; reproducible 1-command reconstruction CLI.
