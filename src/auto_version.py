import argparse

import requests


def get_pypi_version(package_name: str, is_test: bool = True) -> str | None:
    base_url = "https://test.pypi.org/pypi/" if is_test else "https://pypi.org/pypi/"
    url = f"{base_url}{package_name}/json"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()

        versions = list(data["releases"].keys())
        # Sort versions to ensure we get the latest, including pre-releases
        # This requires a proper version parsing library for robust sorting
        # For simplicity, we'll assume lexicographical sort works for common cases
        # A more robust solution would use packaging.version.parse
        versions.sort(
            key=lambda s: [int(u) if u.isdigit() else u for u in s.split(".")],
            reverse=True,
        )

        if versions:
            return versions[0]
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from PyPI API: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", help="Test Pypi or not", action="store_true")
    args = parser.parse_args()

    latest_pypi_version = get_pypi_version("ptt-mcp-server", is_test=args.test)

    if latest_pypi_version is None:
        print("Error: Could not retrieve latest PyPI version.")
        return

    # print(latest_version)

    if args.test:
        if "dev" not in latest_pypi_version:
            cur_version = f"{latest_pypi_version}.dev0"
        else:
            next_num = latest_pypi_version.split("dev")[-1]
            next_num = int(next_num) + 1

            cur_version = latest_pypi_version[
                : latest_pypi_version.find("dev") + 3
            ] + str(next_num)
    else:
        next_num = latest_pypi_version.split(".")[-1]
        next_num = int(next_num) + 1

        cur_version = ".".join(latest_pypi_version.split(".")[:2] + [str(next_num)])

    print(cur_version)


if __name__ == "__main__":
    main()
