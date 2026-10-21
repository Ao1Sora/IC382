# Server Integration

Manual navigation integration now uses the existing HPC allocation, course601 namespace,
and Ubuntu Humble root. See [Navigation MVP](NAVIGATION_MVP.md) for launch commands and evidence.
No automatic GPU runner is enabled.

Keep the existing Isaac Sim scenes and installation separate.
Clone this robot branch into another directory using the shallow, single-branch command in the README
to avoid downloading large historical simulation assets.

## Manual integration

1. Allocate a GPU and start the course scene using the simulation environment's launch procedure.
   Confirm that the bridge is enabled and the simulation is playing.
2. Enter the **same ROS2 network and user namespace** as Isaac Sim.
   The current course601 environment uses an isolated namespace; setting ROS_DOMAIN_ID alone is insufficient.
   The independent robot checkout also needs to be mounted into the container.
3. Source ROS2 Humble, build the robot workspace, and source install/setup.bash inside that environment.
4. Run `bash scripts/check-simulation.sh`. Check the commit SHA, message counts, and result in its report.
5. Use `scripts/hpc-patrol.sh start` for the dedicated navigation MVP; start the mission with its
   service only after localization and Nav2 lifecycle readiness. `team.launch.py` is a separate
   entry point for nodes selected in the team manifest.

The existing HPC Ubuntu root container only mounts the simulation project.
`scripts/hpc-ros.sh` enters the verified running desktop namespace and existing container wrapper.
Do not source the container's /opt/ros/humble directly on the host.
Revalidate namespace and mounts if the simulation environment's layout changes.

## Future automated integration

GitHub ROS2 CI is separate from GPU testing.
Once GPU allocation, namespaces, and mounts have been verified, register a dedicated runner.
Check out an exact commit, run CPU checks, then build and run bridge and mission tests serially.
Upload results tagged with the commit SHA.

Only trusted merged commits should enter the shared GPU queue.
Avoid allowing two jobs to control the same scene.
There is currently no GPU workflow waiting for the server, and a push does not modify the existing simulation runtime.
