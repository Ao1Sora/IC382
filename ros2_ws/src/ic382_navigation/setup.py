from glob import glob
from setuptools import setup

setup(
    name='ic382_navigation', version='0.1.0', packages=['ic382_navigation'],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/ic382_navigation']),
        ('share/ic382_navigation', ['package.xml']),
        ('share/ic382_navigation/launch', glob('launch/*.launch.py')),
        ('share/ic382_navigation/config', glob('config/*.yaml')),
        ('share/ic382_navigation/behavior_trees', glob('behavior_trees/*.xml')),
    ],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='IC382 team', maintainer_email='maintainers@example.com',
    description='Teacher Wheeltec navigation with automatic three-point desk inspection',
    license='Apache-2.0', tests_require=['pytest'],
    entry_points={'console_scripts': [
        'journal = ic382_navigation.journal_node:main',
        'velocity_gate = ic382_navigation.velocity_gate:main',
        'local_alignment = ic382_navigation.local_alignment:main',
        'record_waypoint = ic382_navigation.record_waypoint:main',
        'desk_navigation = ic382_navigation.desk_navigation:main',
        'simulation_encoder = ic382_navigation.simulation_encoder:main',
        'simulation_scan = ic382_navigation.simulation_scan:main',
    ]},
)
