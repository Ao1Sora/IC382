# Teacher baseline and upstream dependencies

`../ros2_ws/src/teacher/` contains seven source packages exported from Jetson 10.11.31.13 without editing their file contents. `PROVENANCE.json` records source paths and SHA-256 hashes.

`upstream/navigation2-humble/` is the Nav2 source tree present on the same Jetson. `upstream/slam_toolbox-2.6.10/` is the official upstream tag corresponding to its installed ros-humble-slam-toolbox version 2.6.10. These are third-party algorithms, not teacher-authored or team-authored algorithms. Original licenses are retained.

Large individual assets/data files over 2 MB were excluded from this code bundle; every exclusion is recorded in PROVENANCE.json. The course Jetson environment supplies existing resources, sensor drivers and compiled Nav2/SLAM algorithm libraries. This is not an offline operating-system image or a fully self-contained asset bundle.

The seven Wheeltec packages and two team packages can be built with `bash run.sh build`. Heavy upstream algorithm sources are reference/dependency source snapshots, not implicitly rebuilt on every application build. Do not modify teacher originals to implement the team's patrol logic; that code is in ic382_navigation.
