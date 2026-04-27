# Fresh macOS Setup

Use this on a brand-new macOS computer.

## What It Installs Or Checks

- Xcode Command Line Tools
- Homebrew
- Git
- Python 3.10
- Python virtual environment
- TensorFlow, OpenCV, CustomTkinter, Ultralytics YOLO, Twilio, Requests
- YOLOv8n weights for offline demo after setup
- Double-click launcher script

The installer does not create or commit SMS secrets. `data/sms_config.json` is ignored by Git and SMS stays disabled by default.

## Requirements

- macOS 12 or newer recommended
- Intel or Apple Silicon Mac
- Internet connection during setup
- About 8 GB free disk space
- 8 GB RAM minimum, 16 GB recommended

## Setup Steps

1. Download or clone the project.
2. Open Terminal in the project folder.
3. Run:

```bash
chmod +x install_macos.sh
./install_macos.sh
```

4. If macOS opens the Apple Command Line Tools installer, finish that installer, then run `./install_macos.sh` again.
5. Launch with:

```bash
./Run_VanRakshak.command
```

The installer also tries to place this launcher on the Desktop:

```text
VanRakshak AI Wildlife Monitoring System.command
```

## Manual Requirements If Homebrew Is Not Wanted

Install these manually:

- Git
- Python 3.10

Then run:

```bash
python3.10 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip setuptools wheel
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python scripts/check_environment.py
./.venv/bin/python scripts/test_model.py
./.venv/bin/python app/main.py
```

## SMS Safety

Real SMS is disabled by default. Configure SMS only if you have provider credentials and are ready to use trial/paid SMS credits.

Do not commit:

```text
data/sms_config.json
.env
```
