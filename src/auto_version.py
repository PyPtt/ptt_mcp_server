import time
from typing import Optional

import requests

import _version


def get_version() -> tuple[Optional[str], Optional[str]]:
    main_version_url = "https://raw.githubusercontent.com/PyPtt/ptt_mcp_server/refs/heads/main/src/_version.py"

    max_retries = 3
    retry_delay_seconds = 2

    for attempt in range(max_retries):
        try:
            response = requests.get(main_version_url)
            response.raise_for_status()  # Raise an exception for HTTP errors

            versions = response.text.split('=')[1].strip().strip('"')

            return versions, _version.__version__

        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1} failed: Error fetching: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay_seconds)
            else:
                print("Max retries reached. Could not fetch version.")
                return None, None
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: An unexpected error occurred: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay_seconds)
            else:
                print("Max retries reached. Could not fetch version.")
                return None, None
    return None, None  # Should not be reached


def main():
    remote_version, current_version = get_version()

    if remote_version is None or current_version is None:
        print("Failed to retrieve version information.")
        return

    if int(remote_version.replace('.', '')) <= int(current_version.replace('.', '')):
        print(current_version)
    else:
        print(remote_version)


if __name__ == "__main__":
    main()
