from typing import Dict, Any

import setuptools
import os

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

version: Dict[str, Any] = {}
with open(os.path.join(os.path.dirname(__file__), "src", "_version.py")) as f:
    exec(f.read(), version)

setuptools.setup(
    name="ptt-mcp-server",
    version=version["__version__"],
    author="CodingMan",  # 請替換成您的名字
    author_email="pttcodingman@gmail.com",  # 請替換成您的電子郵件
    description="The best MCP server for PTT.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/PyPtt/ptt_mcp_server",  # 請替換成您的專案 URL
    package_dir={"": "src"},
    py_modules=[os.path.splitext(f)[0] for f in os.listdir("src") if f.endswith(".py") and f != "auto_version.py"],
    install_requires=[
        "pyptt",
        "fastmcp",
        "python-dotenv",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",

        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",

        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "ptt-mcp-server=mcp_server:main",
        ],
    },
)
