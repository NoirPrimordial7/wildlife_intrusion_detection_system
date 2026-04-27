#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

APP_NAME="VanRakshak AI Wildlife Monitoring System"
PYTHON_BIN=""

step() {
  printf "\n==> %s\n" "$1"
}

need_macos() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "This installer is for macOS only." >&2
    exit 1
  fi
}

ensure_xcode_tools() {
  if xcode-select -p >/dev/null 2>&1; then
    echo "Xcode command line tools found."
    return
  fi

  step "Installing Xcode command line tools"
  xcode-select --install || true
  echo "Finish the Apple installer popup, then run install_macos.sh again."
  exit 1
}

ensure_homebrew() {
  if command -v brew >/dev/null 2>&1; then
    echo "Homebrew found."
    return
  fi

  step "Installing Homebrew"
  echo "Homebrew is required to install Git and Python 3.10 on a fresh Mac."
  read -r -p "Install Homebrew now? [y/N] " answer
  case "$answer" in
    y|Y|yes|YES)
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      ;;
    *)
      echo "Install Homebrew from https://brew.sh, then run this script again."
      exit 1
      ;;
  esac

  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
}

ensure_git() {
  if command -v git >/dev/null 2>&1; then
    echo "Git found."
    return
  fi

  step "Installing Git"
  brew install git
}

ensure_python310() {
  if command -v python3.10 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.10)"
    echo "Python 3.10 found: $PYTHON_BIN"
    return
  fi

  step "Installing Python 3.10"
  brew install python@3.10

  if command -v python3.10 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.10)"
    return
  fi

  if [[ -x /opt/homebrew/opt/python@3.10/bin/python3.10 ]]; then
    PYTHON_BIN="/opt/homebrew/opt/python@3.10/bin/python3.10"
  elif [[ -x /usr/local/opt/python@3.10/bin/python3.10 ]]; then
    PYTHON_BIN="/usr/local/opt/python@3.10/bin/python3.10"
  else
    echo "Python 3.10 was installed but python3.10 was not found. Restart Terminal and run this script again." >&2
    exit 1
  fi
}

ensure_local_sms_safe() {
  if [[ -f data/sms_config.json ]]; then
    echo "Leaving existing local data/sms_config.json in place. It is ignored by Git."
  else
    echo "SMS config not present. App will create disabled config on first run."
  fi
}

install_dependencies() {
  step "Creating Python virtual environment"
  if [[ ! -d .venv ]]; then
    "$PYTHON_BIN" -m venv .venv
  fi

  local python="./.venv/bin/python"
  if [[ ! -x "$python" ]]; then
    echo "Virtual environment was not created correctly." >&2
    exit 1
  fi

  step "Installing Python packages"
  "$python" -m pip install --upgrade pip setuptools wheel
  "$python" -m pip install -r requirements.txt
}

prepare_yolo() {
  step "Preparing YOLO model weights"
  ./.venv/bin/python -c "from ultralytics import YOLO; YOLO('yolov8n.pt'); print('YOLO weights ready')"
}

run_verification() {
  step "Running environment check"
  ./.venv/bin/python scripts/check_environment.py

  step "Running model smoke test"
  ./.venv/bin/python scripts/test_model.py

  step "Checking hybrid evaluator help"
  ./.venv/bin/python scripts/evaluate_hybrid_on_video.py --help >/dev/null
}

create_launcher() {
  step "Creating launcher"
  cat > Run_VanRakshak.command <<'EOF'
#!/usr/bin/env bash
cd "$(dirname "$0")"
./.venv/bin/python app/main.py
EOF
  chmod +x Run_VanRakshak.command

  local desktop="${HOME}/Desktop"
  if [[ -d "$desktop" ]]; then
    cp Run_VanRakshak.command "${desktop}/${APP_NAME}.command"
    chmod +x "${desktop}/${APP_NAME}.command"
    echo "Desktop launcher created: ${desktop}/${APP_NAME}.command"
  fi
}

print_done() {
  printf "\nSetup complete.\n\n"
  echo "Run the app:"
  echo "  Double-click Run_VanRakshak.command"
  echo "  OR run: ./.venv/bin/python app/main.py"
  echo ""
  echo "SMS is disabled by default. Configure SMS only when you are ready to test trial/paid SMS."
}

need_macos
step "Checking system requirements"
ensure_xcode_tools
ensure_homebrew
ensure_git
ensure_python310
ensure_local_sms_safe
install_dependencies
prepare_yolo
run_verification
create_launcher
print_done
