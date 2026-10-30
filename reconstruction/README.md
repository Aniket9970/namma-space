# 🏠 Reconstruction — Setup Guide for Your PC

> **Hey!** This guide is written for someone who has never coded before.
> You don't need to understand how any of this works — just follow the steps in order.
> If anything goes wrong or looks confusing, **open Antigravity and paste the error** — it will fix it for you.

---

## 🤖 How to Use Antigravity (Your AI Helper)

Antigravity is an AI coding assistant — think of it like ChatGPT but it can actually run code on your computer for you.

1. Download & install Antigravity from the link your friend sent you
2. Open it — it looks like a chat window
3. Whenever a step below doesn't work, just copy the error message and tell Antigravity:

> *"I'm setting up the Namma Space reconstruction pipeline. I ran step X and got this error: [paste error here]. Please fix it."*

Antigravity will tell you exactly what to type. You just copy-paste.

---

## 💻 What You Need (One-Time Setup)

You only do this section **once ever**.

### Step 1 — Install Python

1. Go to 👉 https://www.python.org/downloads/
2. Click the big yellow **"Download Python"** button
3. Run the installer
4. ⚠️ **IMPORTANT:** On the first screen of the installer, tick the box that says **"Add Python to PATH"** before clicking Install

To check it worked, open **Command Prompt** (press `Windows key`, type `cmd`, press Enter) and type:
```
python --version
```
You should see something like `Python 3.12.x`. If you see an error, ask Antigravity.

---

### Step 2 — Install Git

1. Go to 👉 https://git-scm.com/download/win
2. Download and run the installer (click Next on everything, defaults are fine)

---

### Step 3 — Install COLMAP

COLMAP figures out camera positions from your photos.

1. Go to 👉 https://github.com/colmap/colmap/releases
2. Download the latest file ending in `-win64.zip`
3. Extract the zip to `C:\colmap\`
4. Add it to PATH:
   - Press `Windows key`, search **"Edit the system environment variables"**, open it
   - Click **"Environment Variables"**
   - Under "System variables", find **Path**, click Edit
   - Click **New** and type: `C:\colmap\`
   - Click OK on everything

To check it worked, open a new Command Prompt and type:
```
colmap --version
```
You should see a version number. If not, ask Antigravity.

---

### Step 4 — Install CUDA (for your RTX 4060)

CUDA lets Python use your GPU.

1. Go to 👉 https://developer.nvidia.com/cuda-downloads
2. Select: Windows → x86_64 → 11 → exe (local)
3. Download and install it (takes a while, defaults are fine)

---

### Step 5 — Install Python Packages

Open Command Prompt and paste this exactly:
```
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install nerfstudio open3d opencv-python Pillow numpy tqdm trimesh scipy
```

This will take 5–10 minutes. Let it finish.

---

### Step 6 — Clone the Gaussian Splatting Repo

Open Command Prompt, navigate to where you want the projects (e.g., your Desktop):
```
cd C:\Users\YourName\Desktop
git clone https://github.com/graphdeco-inria/gaussian-splatting --recursive
```
Replace `YourName` with your actual Windows username.

---

## 📁 Open the Project Folder

Your friend shared the `namma_space` folder with you. Put it on your Desktop.

Your Desktop should now look like:
```
Desktop/
├── namma_space/          ← your friend's project
└── gaussian-splatting/   ← what you just cloned
```

---

## 🎬 Every Time You Get a New Video to Process

Follow these steps **in order** every time you get a new recording.

Open **Command Prompt** and go to the reconstruction folder:
```
cd C:\Users\YourName\Desktop\namma_space\reconstruction
```

---

### 🔵 Step A — Extract Frames from the Video

This takes your video and pulls out individual photos from it.

```
python extract_frames.py --input "C:\path\to\your\video.mp4" --fps 2 --blur 100
```

Replace `C:\path\to\your\video.mp4` with the actual path to the video file.
(Tip: you can drag the video file into Command Prompt to auto-fill the path!)

✅ When done, you'll see a folder called `output\frames\` appear with lots of `.jpg` photos in it.

---

### 🔵 Step B — Run COLMAP (Figure Out Camera Positions)

```
run_colmap.bat
```

> 💡 **Note:** If it says `run_colmap.bat is not recognized`, type this instead and tell Antigravity about it.

This will open a window and show progress. It takes **5–20 minutes** depending on how many photos there are. Let it run.

✅ When done, you'll see a folder called `output\colmap\`

---

### 🔵 Step C — Build the 3D Model (Two Parts)

**Part 1 — Nerfstudio (creates the mesh/shape):**
```
run_nerfstudio.bat
```
This takes **30–60 minutes**. You'll see a progress bar. Let it finish completely.

**Part 2 — Gaussian Splatting (creates the pretty visuals):**
```
run_3dgs.bat
```
This also takes **20–40 minutes**.

> ☕ Good time for a break!

---

### 🔵 Step D — Export to Web Format

This converts everything into files the web app can use.

```
python export_web.py
```

✅ When done, two files will appear in `..\backend\static\models\`:
- `scene.glb`
- `scene.splat`

---

### 🔵 Step E — Build the Navigation Map

This creates the "floor map" so the app knows where walls are.

```
python build_occupancy_grid.py
```

✅ When done, you'll see files appear in `..\backend\static\navigation\`

---

### 🔵 Step F — Tell Your Friend You're Done!

Zip up the `backend\static\` folder and send it to your friend, or push it to the shared repo.

Your friend's web app will automatically pick up the new files. 🎉

---

## ❓ Something Went Wrong?

**Don't panic.** Just:

1. Copy the red error text from Command Prompt
2. Open **Antigravity**
3. Paste the error and say:
   > *"I'm running the Namma Space reconstruction pipeline on Step [X] and got this error. Please fix it."*

Antigravity will guide you through the fix step by step.

---

## ⏱️ Time Estimate Per Video

| Step | Time |
|------|------|
| Extract frames | 1–2 min |
| COLMAP | 5–20 min |
| Nerfstudio | 30–60 min |
| Gaussian Splatting | 20–40 min |
| Export + Grid | 2–5 min |
| **Total** | **~1–2 hours** |

---

## 🆘 Common Problems

| What you see | What to do |
|---|---|
| `'python' is not recognized` | Python not in PATH — reinstall Python and tick the PATH box |
| `CUDA out of memory` | Open Antigravity and ask it to reduce the training size |
| `colmap is not recognized` | COLMAP not in PATH — ask Antigravity to help add it |
| `No module named X` | Run `pip install X` in Command Prompt |
| Black screen / empty output | Video might be too short — try a longer recording |
| Anything else | Paste the full error into Antigravity |
