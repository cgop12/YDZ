"""
Firewall Setup Tool (Python version, no encoding issues)
"""
import subprocess
import sys
import os


def log(msg):
    print(f"[+] {msg}")


def is_admin():
    try:
        return os.getuid() == 0
    except:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0


def main():
    print("=" * 60)
    print("  YDZ - Firewall Setup")
    print("=" * 60)
    print()

    if not is_admin():
        print("ERROR: Need Administrator Privileges!")
        print("Please run this script as Administrator!")
        print()
        if sys.platform == "win32":
            input("Press Enter to exit...")
        return

    log("Adding firewall rules...")

    rules = [
        ("YDZ TCP 8888", "TCP", 8888),
        ("YDZ UDP 23333", "UDP", 23333),
    ]

    for name, proto, port in rules:
        cmd = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={name}", "dir=in", "action=allow",
            f"protocol={proto}", f"localport={port}"
        ]
        try:
            subprocess.run(cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            log(f"OK: {name}")
        except Exception as e:
            log(f"ERROR: {name} - {e}")

    exe_paths = [
        os.path.join(os.path.dirname(__file__), "YDZServer.exe"),
        os.path.join(os.path.dirname(__file__), "dist", "YDZServer.exe"),
    ]

    for exe in exe_paths:
        if os.path.exists(exe):
            log(f"Adding rule for {exe}...")
            cmd = [
                "netsh", "advfirewall", "firewall", "add", "rule",
                "name=YDZServer App", "dir=in", "action=allow",
                f"program={exe}"
            ]
            try:
                subprocess.run(cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                log("OK: Program rule added")
            except:
                pass

    print()
    print("=" * 60)
    print("  Done! Firewall rules added!")
    print("=" * 60)
    print()
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()

