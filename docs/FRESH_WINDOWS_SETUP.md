# Fresh Windows PC setup

Download the project ZIP from GitHub and extract the **entire folder** to a permanent location. Double-click **SETUP.bat**. Keep the internet connected until it says **Setup complete**.

Or open PowerShell in the extracted project folder and paste:

```powershell
.\SETUP.bat
```

Setup checks the project files, finds a compatible 64-bit Python 3.10–3.12, installs Python 3.12 if missing, checks/installs Microsoft's Visual C++ runtime, creates the local virtual environment, installs the pinned app packages, obtains YOLO weights if missing, verifies the environment and classifier, and creates a desktop shortcut. Git is not required when using a ZIP.

For Python installation it tries [WinGet](https://learn.microsoft.com/en-us/windows/package-manager/winget/install) first. If WinGet is unavailable or cannot supply Python, it downloads the official [Python 3.12.10 Windows installer](https://www.python.org/downloads/release/python-31210/), the tested binary release for this project. Microsoft runtime downloads use [Microsoft's official redistribution link](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist). Downloaded installers must pass publisher-signature verification before running. Windows may request administrator approval to install the shared runtime.

After setup, double-click **START.bat** or **VanRakshak Wildlife Watch** on the desktop. Click **Guided demo** for the illustrated walkthrough. SMS/calls need your own provider credentials and recipients; setup does not enable them or replace existing configuration.

Requirements: 64-bit Windows 10/11, internet during installation, enough free space for Python/TensorFlow/PyTorch (allow approximately 8 GB), and a PC capable of running those models. No webcam is needed for Guided demo or uploaded media.

If setup fails, read `.setup/setup.log`, correct the reported error, and rerun the same setup file. Failed installation steps stop setup; it does not report success until the environment/model checks pass. If Windows requires a restart, restart and rerun. Keep the project folder in place so the shortcut continues to work.

Check prerequisites without installing anything:

```powershell
.\SETUP.bat -CheckOnly
```

For macOS use the existing `install_macos.sh` instructions. This new installer is for Windows.
