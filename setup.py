import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="ptt-mcp-server",
    version="0.1.0",
    author="CodingMan",  # 請替換成您的名字
    author_email="pttcodingman@gmail.com",  # 請替換成您的電子郵件
    description="A MCP server for PTT.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/PyPtt/ptt_mcp_server",  # 請替換成您的專案 URL
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    install_requires=[
        "pyptt",
        "fastmcp",
        "python-dotenv",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",  # 您可以選擇適合的授權條款
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)
