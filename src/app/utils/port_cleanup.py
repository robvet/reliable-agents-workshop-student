"""
Port Cleanup Utility for FastAPI Applications

This utility class kills processes holding a specific port on Windows.
Modern languages (C#, Go, Java) handle port cleanup automatically. Python doesn't.

This solves the "port already in use" errors from previous runs and Windows TIME_WAIT issues.

Usage in FastAPI lifespan:
    from app.utils.port_cleanup import PortCleanup
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Cleanup on startup
        PortCleanup.kill_process_on_port(8000)
        
        yield
        
        # Cleanup on shutdown
        PortCleanup.kill_process_on_port(8000)
    
    app = FastAPI(lifespan=lifespan)

Search for "PORT CLEANUP" in your codebase to find this utility for reuse.
"""

import subprocess
import platform
import os


class PortCleanup:
    """
    Utility class for killing processes holding a specific port.
    
    Windows-only implementation using netstat and taskkill.
    For Linux/Mac, would need to use lsof and kill commands.
    """
    
    @staticmethod
    def kill_process_on_port(port: int) -> bool:
        """
        Kill any process holding the specified port.
        
        Args:
            port: The port number to free up (e.g., 8000)
            
        Returns:
            True if a process was found and killed, False otherwise.
            
        Note:
            Silently fails on errors - this is best-effort cleanup.
            Won't raise exceptions, making it safe to call in startup/shutdown.
        """
        try:
            if platform.system() == "Windows":
                return PortCleanup._kill_on_windows(port)
            else:
                return PortCleanup._kill_on_unix(port)
        except Exception:
            # Silently fail - this is best-effort cleanup
            return False

    @staticmethod
    def _kill_on_unix(port: int) -> bool:
        """Kill process on port using lsof (macOS/Linux)."""
        current_pid = os.getpid()
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            check=False
        )
        if not result.stdout.strip():
            return False

        killed = False
        for pid_str in result.stdout.strip().splitlines():
            pid = int(pid_str.strip())
            if pid == current_pid:
                continue
            os.kill(pid, 9)
            killed = True
        return killed

    @staticmethod
    def _kill_on_windows(port: int) -> bool:
        """Kill process on port using netstat/taskkill (Windows)."""
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            check=False
        )

        killed = False
        current_pid = str(os.getpid())

        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if len(parts) > 4:
                    pid = parts[-1]

                    # Skip if it's the current process
                    if pid == current_pid:
                        continue

                    # Kill the process forcefully
                    subprocess.run(
                        ["taskkill", "/F", "/PID", pid],
                        capture_output=True,
                        check=False
                    )
                    killed = True

        return killed
    
    @staticmethod
    def is_port_in_use(port: int) -> bool:
        """
        Check if a port is currently in use.
        
        Args:
            port: The port number to check
            
        Returns:
            True if port is in use, False otherwise
        """
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                for line in result.stdout.splitlines():
                    if f":{port}" in line and "LISTENING" in line:
                        return True
                return False
            else:
                result = subprocess.run(
                    ["lsof", "-ti", f":{port}"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                return bool(result.stdout.strip())
        except Exception:
            return False

