# Namma Space — Quick Start for macOS & Submission Guide

Welcome! This package contains the **complete, runnable Namma Space indoor digital twin system** along with all official submission materials for **Techfest IIT Bombay 2026–27 (Round 1: 3D Reconstruction & Roaming)**.

---

## 🚀 How to Run the Whole System on Your Mac (1-Click)

### Prerequisites (Standard Mac Dev Tools)
You only need standard Python 3 and Node.js:
1. **Python 3.10+**: Run `python3 --version` in Terminal. (If missing, install from [python.org](https://www.python.org/) or `brew install python`).
2. **Node.js (LTS)**: Run `node -v` in Terminal. (If missing, install from [nodejs.org](https://nodejs.org/) or `brew install node`).

---

### Step-by-Step Launch
1. Double-click **`run_mac.command`** in Finder.
   *(Or in Terminal, navigate to this folder and run: `bash run_mac.command`)*
2. The launcher will automatically:
   - Install backend Python packages (`fastapi`, `uvicorn`, `sqlite3`).
   - Install frontend npm packages (takes ~15 seconds on the first run).
   - Start the FastAPI backend on port 8000.
   - Start the Vite 3D web viewer on port 5173.
   - **Automatically open Safari/Chrome to `http://localhost:5173/`!**

---

## 🕹️ How to Free-Roam in the 3D Space

Once `http://localhost:5173/` opens:
* **Mouse Look:** Click anywhere on the 3D canvas to lock your pointer for full 360° first-person look.
* **Walking:** Use <kbd>W</kbd>, <kbd>A</kbd>, <kbd>S</kbd>, <kbd>D</kbd> to walk smoothly around the room.
* **Sprint:** Hold <kbd>Shift</kbd> for 2.5× walking speed.
* **Fly / Elevate:** Press <kbd>Space</kbd> to fly up, <kbd>C</kbd> to fly down.
* **Switch Views:** Click the `🕹️ WASD Roam` / `🔄 Orbit View` button at top-left to toggle between first-person exploration and a 3D dollhouse overview.
* **Switch Rooms:** Use the top bar dropdown to switch between all 10 pre-loaded rooms (`Ex4 Scene`, `Ex3 Scene`, `Ex2 Scene`, `Ex1 Scene`, `Roomvid Scene`, etc.)!
* **Search POIs:** Use the search bar at the top to search for points of interest (e.g. "Workstation", "Entrance", "Balcony") with instant camera fly-to interpolation.

---

## 📁 How to Do the Techfest Round 1 Submission

Inside this folder, you will find the **`Submission_Deliverables/`** folder containing the 4 required deliverables:

```
Submission_Deliverables/
├── 1_Technical_Abstract/
│   └── Technical_Abstract.pdf              <-- 5-page IEEE-format technical paper
├── 2_Proof_of_Concept_and_Web_Viewer/
│   └── Proof_of_Concept_and_Web_Viewer_Link.pdf  <-- Working URLs & Evaluator Guide
├── 3_Demonstration_Video/
│   ├── Demonstration_Video_Script_and_Guide.pdf  <-- 4m 15s Storyboard & Narration
│   └── (Place your recorded .mp4 demo video here)
├── 4_Code_Repository_and_Setup/
│   └── SETUP_AND_REPRODUCTION_GUIDE.pdf     <-- 1-command reproduction guide
└── SUBMISSION_CHECKLIST_AND_GOOGLE_DRIVE_INSTRUCTIONS.md
```

### Steps to Submit to Google Drive:
1. Open Google Drive in your browser.
2. Create a new folder named: **`Namma_Space_Round1_Submission`**
3. Upload the 4 deliverable folders from `Submission_Deliverables/` into it.
4. Upload your recorded 3–5 minute demonstration video into `3_Demonstration_Video/`.
5. Upload this complete project zip (or link your public GitHub repo) into `4_Code_Repository_and_Setup/`.
6. Right-click the folder $\to$ **Share** $\to$ set General Access to **"Anyone with the link can view"**.
7. Copy the link and submit it on the Techfest submission portal.
