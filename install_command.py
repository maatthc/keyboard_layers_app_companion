#!/usr/bin/env python3

import os
import sys
import getpass
from pathlib import Path


def get_start_cmd() -> str:
    print("Package Managers:")
    print("1): UV")
    print("2): PipEnv")
    while True:
        try:
            choice = int(input("\nWhich package manager are you using? "))
            if 1 <= choice <= 2:
                break
            print("Invalid selection. Please choose a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            sys.exit(0)
    if choice == 1:
        return "uv run main.py"
    return "pipenv run python main.py"


def get_dir_priority(p: Path, home: Path) -> int:
    local_dir = home / ".local"
    is_under_local = p.is_relative_to(local_dir)
    ends_in_bin = p.name.endswith("bin")

    if is_under_local and ends_in_bin:
        return 1
    elif is_under_local:
        return 2
    elif ends_in_bin:
        return 3
    else:
        return 4


def main():

    script_name = "companion"
    cwd = Path.cwd()
    user = getpass.getuser()
    home = Path.home().resolve()

    print(f"Current User: {user}")
    print(f"Current Directory: {cwd}\n")

    start_cmd = get_start_cmd()
    path_env = os.environ.get("PATH", "")
    raw_paths = path_env.split(os.pathsep)

    user_path_dirs = []
    seen = set()

    for p_str in raw_paths:
        if not p_str:
            continue

        p = Path(p_str).resolve()

        if p.is_dir() and p.is_relative_to(home) and p not in seen:
            user_path_dirs.append(p)
            seen.add(p)

    if not user_path_dirs:
        print("No directories in your PATH are located under your home directory.")
        sys.exit(1)

    user_path_dirs.sort(key=lambda d: get_dir_priority(d, home))

    print("Available PATH directories under your home folder (prioritized):")
    for i, d in enumerate(user_path_dirs, start=1):
        print(f"  {i}) {d}")

    while True:
        try:
            choice = int(input("\nSelect a directory number to install the script: "))
            if 1 <= choice <= len(user_path_dirs):
                selected_dir = user_path_dirs[choice - 1]
                break
            print("Invalid selection. Please choose a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            sys.exit(0)

    script_path = selected_dir / script_name

    script_content = f"""#!/usr/bin/env bash

set -euo pipefail
cd {cwd}
{start_cmd} "$@"

"""
    try:
        script_path.write_text(script_content)

        # Make the script executable (chmod +x)
        current_mode = script_path.stat().st_mode
        script_path.chmod(current_mode | 0o111)

        print(f"\nSuccess! Executable script created at: {script_path}")
    except Exception as e:
        print(f"\nError writing script: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
