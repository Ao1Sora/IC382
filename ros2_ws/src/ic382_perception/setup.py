from glob import glob
from setuptools import setup

setup(
    name="ic382_perception",
    version="0.1.0",
    packages=["ic382_perception"],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/ic382_perception"]),
        ("share/ic382_perception", ["package.xml"]),
        ("share/ic382_perception/config", glob("config/*.yaml")),
        ("share/ic382_perception/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="IC382 team",
    maintainer_email="maintainers@example.com",
    description="Object classification perception node",
    license="LicenseRef-Proprietary",
    tests_require=["pytest"],
    entry_points={"console_scripts": [
        "object_classifier = ic382_perception.object_classifier:main",
    ]},
)
