from glob import glob
from setuptools import setup

setup(
    name="ic382_bringup", version="0.1.0",
    packages=["ic382_bringup"],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/ic382_bringup"]),
        ("share/ic382_bringup", ["package.xml"]),
        ("share/ic382_bringup/launch", glob("launch/*.launch.py")),
        ("share/ic382_bringup/config", glob("config/*.json")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="IC382 team", maintainer_email="maintainers@example.com",
    description="Team launch and simulation bridge checks",
    license="LicenseRef-Proprietary",
    tests_require=["pytest"],
    entry_points={"console_scripts": [
        "bridge_probe = ic382_bringup.bridge_probe:main",
    ]},
)

