from setuptools import setup, find_packages

setup(
    name="netmon",
    version="2.0.0",
    description="Application-based network traffic monitor",
    author="Murat",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "typer>=0.9.0",
        "rich>=13.0.0",
        "httpx>=0.25.0",
        "pydantic>=2.0.0",
        "pyyaml>=6.0.0",
    ],
    entry_points={
        "console_scripts": [
            "netmon=netmon.cli:app",
        ],
    },
)
