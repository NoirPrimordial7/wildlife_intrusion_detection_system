# Fresh Windows PC Setup

Use this on a brand-new Windows 10/11 64-bit PC.

## What It Installs Or Checks

- Git
- Python 3.10
- Python virtual environment
- TensorFlow, OpenCV, CustomTkinter, Ultralytics YOLO, Twilio, Requests
- YOLOv8n weights for offline demo after setup
- Desktop shortcut for launching the app

The installer does not create or commit SMS secrets. `data/sms_config.json` is ignored by Git and SMS stays disabled by default.

## Steps

1. Download or clone the project.
2. Open the project folder.
3. Double-click:

```text
install_windows_full.bat
```

4. Wait for verification to complete.
5. Launch from the desktop shortcut:

```text
VanRakshak AI Wildlife Monitoring System
```

Or run:

```powershell
.\Run_VanRakshak.bat
```

## Requirements

- Windows 10/11 64-bit
- Internet connection during setup
- About 8 GB free disk space
- 8 GB RAM minimum, 16 GB recommended

## If Winget Is Missing

Install Git and Python 3.10 manually:

- Git: https://git-scm.com/download/win
- Python 3.10: https://www.python.org/downloads/release/python-31011/

Then run `install_windows_full.bat` again.

## SMS Safety

Real SMS is disabled by default. Configure SMS only if you have provider credentials and are ready to use trial/paid SMS credits.
