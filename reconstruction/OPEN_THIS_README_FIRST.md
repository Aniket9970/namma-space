# 👋 Hey! Read this first.

You don't need to understand any of this technical stuff.

You just need to do **2 things**:

1. **Record a video** of a room (walk slowly around your room/home, 2-3 minutes)
2. **Open Antigravity and paste the message below**

That's it. Antigravity will do everything else for you automatically.

---

## Step 1 — Record a Video

- Use your phone camera
- Walk slowly around the room (1 room is enough for testing)
- Move smoothly, don't shake the phone
- Record for at least **2-3 minutes**
- Transfer the video to your PC (WhatsApp, USB cable, Google Photos, anything)
- Note down the full path to the video file  
  *(example: `C:\Users\YourName\Desktop\room_video.mp4`)*

---

## Step 2 — Open Antigravity

Open the Antigravity app on your PC.

Copy everything inside the box below and paste it into Antigravity chat.  
**Change the two things marked with ✏️ before sending.**

---

```
I need you to run the Namma Space 3D reconstruction pipeline on my Windows PC (I have an RTX 4060 GPU).

The project folder is at: ✏️ C:\Users\YourName\Desktop\namma_space\reconstruction
My video file is at: ✏️ C:\Users\YourName\Desktop\room_video.mp4

Please run this single command for me:
    python run_pipeline.py --video "✏️ C:\Users\YourName\Desktop\room_video.mp4"

Run it from inside the reconstruction folder. This one command will automatically do all 7 steps:
install packages → extract frames → COLMAP → Nerfstudio → Gaussian Splatting → export files → build nav grid.

If COLMAP is not installed, install it for me.
If gaussian-splatting repo is missing, clone it for me.
If any step fails, read the error, fix it, and re-run from that step using --start-from N.
Do not ask me what to do — just handle everything yourself.

When done, tell me which folder to zip and send to my friend.
```

---

## Step 3 — Wait

Antigravity will now run everything on its own. This takes about **1-2 hours total**.

You'll see it typing commands and showing progress. Just leave it running.

---

## Step 4 — Send Files to Your Friend

When Antigravity says it's done, it will tell you where the output files are.

Zip the `backend\static\` folder and send it to your friend on WhatsApp or Google Drive.

**You're done! 🎉**

---

> **If Antigravity gets stuck or asks you something**, just reply:
> *"I don't understand, please handle it yourself and continue."*
