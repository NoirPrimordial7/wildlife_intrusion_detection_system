# Run VanRakshak

1. Extract the entire project ZIP.
2. On a new Windows PC, double-click **SETUP.bat**. It checks/installs Python, the Windows runtime, app packages and models, verifies them, and creates a desktop shortcut. Keep the internet connected.
3. Double-click **START.bat** to open the app. If compatible Python is already installed, START.bat can also set up the app packages directly.

For first setup on a new Windows PC, open PowerShell **inside the extracted project folder** and copy this:

```powershell
.\SETUP.bat
```

After setup, launch with:

```powershell
.\START.bat
```

First start installs packages. The ZIP includes YOLO weights; source-only copies download them once if missing. Keep the internet connected and wait for the desktop window. Later starts reuse the installation. No Git, virtual-environment activation, credentials, or administrator access is needed.

**To get the same walkthrough:** click **Guided demo** in the sidebar. The illustrated elephant approaches the boundary, the threat changes from LOW to WARNING to DANGER, then the perimeter clears. This is a scripted simulation, clearly labelled on screen; it never sends SMS, sounds the alarm, or writes real alert history. Pause, resume, seek, speed, restart, and detection bookmarks work in the demo.

**For real detection:** choose **Upload video**, select a wildlife video, then click **Start** under the preview. Or choose **Use webcam** / **Analyze image**. The first real inference may take longer while the models load. Supported video decoding depends on the codec installed with OpenCV.

**For phone texts:** open **Settings → Configure provider credentials**, enter your SMS provider credentials, add recipients with `+countrycode` phone numbers, save users, and enable SMS. Use Test SMS to check the provider. Real texts require a working provider account; no credentials are included. SMS and calls start disabled. Actual phone delivery depends on account credits, recipient permissions, and provider availability. For calls, configure Twilio with a voice-capable sender number, enable **Voice alerts (Twilio)**, and use **Test Call**. Calls use Twilio credentials even if your SMS provider is Fast2SMS. A queued call means accepted by Twilio, not answered; check the phone/provider dashboard. Both channels obey the confirmed-alert cooldown. [Twilio voice API reference](https://www.twilio.com/docs/voice/api/call-resource).

**Check installation:**

```powershell
.\START.bat --setup-only --verify
```

**macOS / Linux:** with Python 3.10–3.12 and Tk installed, open a terminal in this folder:

```bash
python3 launch.py
```

If setup fails, read the last error in the terminal and run the same command again. If no webcam is available, use Upload video or Guided demo. If the window is too small at high display scaling, lower the system display scaling or use a larger display.
