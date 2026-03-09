#!/usr/bin/env python3
"""
SPESION 3.0 — Cross-Platform Launcher
======================================
Detects your OS and launches the correct setup/management script.

Usage:
    python setup.py           → Interactive setup wizard
    python setup.py start     → Start services
    python setup.py stop      → Stop services
    python setup.py <command> → Forward any management command
"""

import os
import sys
import platform
import subprocess
import shutil

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")

def detect_os():
    """Returns 'windows', 'macos', or 'linux'."""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "macos"
    else:
        return "linux"

def run_setup(os_type: str):
    """Launch the interactive setup wizard for the detected OS."""
    if os_type == "windows":
        script = os.path.join(SCRIPTS_DIR, "spesion_setup.ps1")
        if not os.path.exists(script):
            print(f"❌ Setup script not found: {script}")
            sys.exit(1)
        print("🧠 Launching SPESION 3.0 Setup (Windows PowerShell)...")
        subprocess.run([
            "powershell", "-ExecutionPolicy", "RemoteSigned",
            "-File", script
        ])
    else:
        script = os.path.join(SCRIPTS_DIR, "spesion_setup.sh")
        if not os.path.exists(script):
            print(f"❌ Setup script not found: {script}")
            sys.exit(1)
        # Ensure executable
        os.chmod(script, 0o755)
        print("🧠 Launching SPESION 3.0 Setup (Bash)...")
        subprocess.run(["bash", script])

def run_command(os_type: str, command: str, extra_args: list):
    """Forward a management command to the appropriate script."""
    if os_type == "windows":
        script = os.path.join(SCRIPTS_DIR, "spesion.ps1")
        if not os.path.exists(script):
            print(f"❌ Management script not found: {script}")
            sys.exit(1)
        cmd = [
            "powershell", "-ExecutionPolicy", "RemoteSigned",
            "-File", script, command
        ] + extra_args
    else:
        script = os.path.join(SCRIPTS_DIR, "spesion.sh")
        if not os.path.exists(script):
            print(f"❌ Management script not found: {script}")
            sys.exit(1)
        os.chmod(script, 0o755)
        cmd = ["bash", script, command] + extra_args

    subprocess.run(cmd)

def check_prerequisites(os_type: str):
    """Quick check for Docker and Ollama."""
    ok = True
    for tool in ["docker", "git"]:
        if shutil.which(tool):
            print(f"  ✅ {tool}")
        else:
            print(f"  ❌ {tool} — not found")
            ok = False
    return ok

def main():
    os_type = detect_os()
    os_name = {"windows": "Windows", "macos": "macOS", "linux": "Linux"}[os_type]

    if len(sys.argv) < 2:
        # No command → run setup wizard
        print()
        print("  ╔═══════════════════════════════════════════════════════╗")
        print("  ║     🧠  SPESION 3.0 — Cross-Platform Launcher       ║")
        print("  ╚═══════════════════════════════════════════════════════╝")
        print()
        print(f"  Detected OS: {os_name} ({platform.machine()})")
        print(f"  Python:      {platform.python_version()}")
        print()

        choice = input("  What would you like to do?\n"
                       "    1. Run full setup wizard\n"
                       "    2. Quick start (docker compose up)\n"
                       "    3. Check prerequisites\n"
                       "     → ")

        if choice == "1":
            run_setup(os_type)
        elif choice == "2":
            run_command(os_type, "start", [])
        elif choice == "3":
            check_prerequisites(os_type)
        else:
            print("  Invalid choice.")
            sys.exit(1)
    else:
        command = sys.argv[1]
        extra = sys.argv[2:]

        if command in ("setup", "install", "init"):
            run_setup(os_type)
        elif command == "help":
            run_command(os_type, "help", [])
        else:
            run_command(os_type, command, extra)

if __name__ == "__main__":
    main()
