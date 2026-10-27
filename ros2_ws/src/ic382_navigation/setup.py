from glob import glob
from setuptools import setup

setup(
    name='ic382_navigation', version='0.1.0', packages=['ic382_navigation'],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/ic382_navigation']),
        ('share/ic382_navigation', ['package.xml']),
        ('share/ic382_navigation/launch', glob('launch/*.launch.py')),
        ('share/ic382_navigation/config', glob('config/*.yaml')),
        ('share/ic382_navigation/maps/course', glob('maps/course/*')),
        ('share/ic382_navigation/maps/inspection', glob('maps/inspection/*')),
    ],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='IC382 team', maintainer_email='maintainers@example.com',
    description='Nav2 patrol with explicitly simulated inspection and tagging',
    license='Apache-2.0', tests_require=['pytest'],
    entry_points={'console_scripts': [
        'mission = ic382_navigation.mission_node:main',
        'journal = ic382_navigation.journal_node:main',
        'velocity_gate = ic382_navigation.velocity_gate:main',
        'scan_filter = ic382_navigation.scan_filter:main',
        'record_waypoint = ic382_navigation.record_waypoint:main',
        'desk_navigation = ic382_navigation.desk_navigation:main',
        'wheel_odometry = ic382_navigation.wheel_odometry:main',
    ]},
)
