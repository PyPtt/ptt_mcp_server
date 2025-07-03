import argparse
import subprocess
import sys

from _version import __version__

def get_pypi_version(package_name: str, is_test: bool = True) -> str | None:
    url = 'https://test.pypi.org/simple/' if is_test else 'https://pypi.org/simple/'

    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'index', 'versions', '--index-url', url, package_name],
            capture_output=True,
            text=True,
            check=True
        )
        latest_version = result.stdout.split(' ')[-1].strip()
        return latest_version
    except subprocess.CalledProcessError as e:
        print(f"Error checking TestPyPI: {e.stderr}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', help="Test Pypi or not", action="store_true")
    args = parser.parse_args()

    latest_pypi_version = get_pypi_version('ptt-mcp-server', is_test=args.test)

    if latest_pypi_version.split('.')[:2] != __version__.split('.')[:2]:
        latest_pypi_version = __version__

    # print(latest_version)

    if args.test:

        if 'dev' not in latest_pypi_version:
            cur_version = f'{latest_pypi_version}.dev0'
        else:

            next_num = latest_pypi_version.split('dev')[-1]
            next_num = int(next_num) + 1

            cur_version = latest_pypi_version[:latest_pypi_version.find('dev') + 3] + str(next_num)
    else:
        next_num = latest_pypi_version.split('.')[-1]
        next_num = int(next_num) + 1

        cur_version = '.'.join(latest_pypi_version.split('.')[:2] + [str(next_num)])

    print(cur_version)


if __name__ == "__main__":
    main()
