"""
Cross-platform port cleanup script.

Kills stale Python processes on backend ports (8010) before
the server starts. Used by the VS Code debugger preLaunchTask.

Usage:
    python cleanup.py
"""

import sys
import os

# Add src directory to path so we can import the app package.
# This file lives at scripts/cleanup/, so src is two levels up.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from app.utils.port_cleanup import PortCleanup


if __name__ == "__main__":
    ports = [8010]
    for port in ports:
        if PortCleanup.kill_process_on_port(port):
            print(f"Killed stale process on port {port}")
        else:
            print(f"Port {port} is clear")
