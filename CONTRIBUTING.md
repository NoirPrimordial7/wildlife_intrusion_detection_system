# Contributing to VanRakshak / Wildlife Watch

Start with [QUICKSTART.md](QUICKSTART.md), the [setup and demo guide](docs/SETUP_AND_DEMO_GUIDE.md), [technical architecture](docs/TECHNICAL_ARCHITECTURE.md) and [model limitations](docs/MODEL_LIMITATIONS.md).

## Set up and reproduce

Use 64-bit Python 3.10–3.12 and follow the setup guide for your operating system. On Windows, `START.bat` prepares the environment and launches the app. After setup, run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\verify_ui.py
```

On macOS/Linux, use `./.venv/bin/python` for the same Python commands. The unit suite uses temporary data and mocked providers; do not replace those mocks with live messaging services.

Start UI checks with the built-in guided simulation, which is labelled and does not create real alerts or notifications. Keep SMS and voice calls disabled while reproducing ordinary UI bugs. Provider test scripts can send real messages or calls when configured and are not part of the default contribution checks.

## Choose useful work

Good starting points include reproducible launcher failures, clearer setup instructions, keyboard-access problems, video-control behavior and notification-status wording. Open an issue using the bug or feature template. Include the operating system, Python version, relevant action, expected result and a minimal reproducible example. Discussions are available for setup questions and explanations.

Keep one coherent improvement per pull request and link its issue. For behavior changes, include the relevant regression checks. For UI changes, include screenshots and describe the steps exercised. Credit real collaborators using their agreed GitHub-associated email in a `Co-authored-by` trailer.

## Keep detection claims accurate

This is a desktop prototype using broad YOLO animal classes and an existing species classifier. A UI improvement does not establish improved detection accuracy. Changes to confidence thresholds, repeated-detection confirmation, cooldowns, evidence recording or provider behavior need explicit regression coverage and an explanation of their effect.

An API-accepted voice request is queued; it does not establish that somebody answered. Keep simulation, current detections, confirmed alerts and notification outcomes clearly distinguishable.

## Protect people and credentials

Use synthetic phone numbers and non-sensitive test media in public issues. Redact logs and screenshots before uploading them. Never commit `data/sms_config.json`, `data/firebase_config.json`, provider tokens, real recipient lists or identifiable camera footage. Check [.gitignore](.gitignore), but also inspect the actual diff: ignored configuration files do not protect other files automatically.

No open-source license has been selected for this repository. Ask the maintainer about permission before redistributing its code or model assets.
