import time
import subprocess

from utilities import log_details

def get_chrome_processes_for_profile(profile_path: str):
    """
    Return PIDs of Chrome processes whose --user-data-dir points
    to the specified profile.
    """

    profile_path = profile_path.rstrip("\\").lower()

    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            """
            Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'" |
            Select-Object ProcessId, CommandLine |
            ConvertTo-Json -Compress
            """,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if not result.stdout.strip():
        return []

    import json

    try:
        processes = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    # Convert single-object JSON into a list.
    if isinstance(processes, dict):
        processes = [processes]

    matching_pids = []

    for process in processes:
        command_line = process.get("CommandLine") or ""
        command_line = command_line.lower()

        # Normalize quotes and slashes.
        normalized = command_line.replace('"', "").replace("/", "\\")

        expected = f"--user-data-dir={profile_path}"

        if expected in normalized:
            matching_pids.append(int(process["ProcessId"]))

    return matching_pids


def close_chrome_for_profile(profile_path: str):
    """
    Kill ONLY Chrome processes belonging to this profile.

    Does not touch Chrome processes belonging to other profiles.
    """

    log_details(f"Closing Chrome processes for profile:")
    log_details(f"  {profile_path}")

    # Find processes first.
    pids = get_chrome_processes_for_profile(profile_path)

    if not pids:
        log_details("No Chrome processes found for this profile.")
        return

    log_details(f"Found Chrome PIDs: {pids}")

    # Force kill each individual process.
    for pid in pids:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    # Wait until ALL matching processes have actually disappeared.
    deadline = time.time() + 10

    while time.time() < deadline:
        remaining = get_chrome_processes_for_profile(profile_path)

        if not remaining:
            log_details("All Chrome processes for profile have exited.")
            return

        log_details(f"Waiting for Chrome processes to exit: {remaining}")
        time.sleep(0.25)

    # If we get here, something is still holding the profile.
    remaining = get_chrome_processes_for_profile(profile_path)

    if remaining:
        raise RuntimeError(
            f"Chrome processes are still running for profile: {remaining}"
        )


