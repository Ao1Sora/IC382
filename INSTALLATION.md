# Installation result - 2026-10-01

Project: `/puhome/24110598d/Desktop/IC382` (physical shared-storage path `/hpc/puhome/24110598d/Desktop/IC382`).

Installed and verified: NVIDIA Isaac Sim 4.5.0 standalone, running natively on Rocky Linux 8.10.

The original Windows files `hpc/Connect-Hpc.cmd`, `hpc/Connect-Gui.cmd`, and `hpc/Stop-Hpc.cmd` were inspected and retained unchanged. The existing GPU job was reused; no second GPU allocation was submitted.

## Validation

- Official archive downloaded directly on the server: 7,208,817,125 bytes. No local PC transfer required.
- `unzip -tq`: no compressed data errors.
- Archive SHA-256: `c33a452a39bccd2a8a7917b06b5812c6a9d08352e0f03ee42b59d4fdc81b7fb9` (local fingerprint).
- Bundled Python: 3.10.15.
- Native Vulkan renderer selected the allocated RTX 3080 Ti (12 GB); NVIDIA driver 550.54.14.
- Actual render/physics test passed for 60 steps. A 0.25 m cube settled at z=0.1249996200 m.
- Test marker: `IC382_SMOKE_TEST_PASSED`.
- Logs: `logs/smoke-test.log`.
- First full startup took approximately 651 seconds, predominantly initial NVIDIA GPU shader compilation. Later startup speed has not been measured.
- Native VNC GUI startup crashes in NVIDIA EGL. The repaired desktop uses isolated local WebRTC streaming and project-local C++ runtime libraries. The user confirmed the streamed interface is visible and interactive on 2026-10-01. See DESKTOP-REPAIR.md for evidence and limitations.

## Runtime decisions

Version 4.5 was chosen for the installed older GPU/driver, instead of attempting the latest 6.1 release on this allocation. The current NVIDIA requirements were consulted live.

An Ubuntu 22.04 Singularity fallback was downloaded into the project during compatibility checks. Its Vulkan test did not pass and it is not used by the final launchers. Native execution passed the full test.

CPU worker counts are capped at the Slurm CPU allocation for GUI startup, and at six in the supplied smoke test. Python launcher exports matching OMP/MKL/OpenBLAS thread limits; custom Python SimulationApp programs should set the corresponding `extra_args` as in the supplied smoke test.

No server OS or NVIDIA driver changes were made. ROS 2 has not been installed. The project Git repository is published privately at https://github.com/Ao1Sora/IC382 on branch `codex/setup`. The server remote is `origin` (HTTPS). Initial publication uses the local Windows GitHub CLI login; GitHub credentials are not copied to the HPC.

## Use

Connect using the original Windows `hpc/Connect-Gui.cmd`, then in the GPU desktop terminal:

```bash
cd ~/Desktop/IC382
./scripts/isaac-desktop.sh
```

Or use the `IC382 Isaac Sim 4.5` shortcut on the server Desktop.
In the streaming client, enter `10.238.38.1` and click **Connect**.

For Python, connect with the original `hpc/Connect-Hpc.cmd`:

```bash
cd ~/Desktop/IC382
./scripts/isaac-python.sh scripts/smoke-test.py
```

## Sources checked

Local Windows scripts: `D:\ChatGPT\IC382\hpc\Connect-Hpc.cmd`, `Connect-Gui.cmd`, `Stop-Hpc.cmd`.
Local chat mirror: `D:\ChatGPT\IC382\chatgpt-sync\README.md`, `stage-1-tasks.md`, `ros2-introduction.md`. The mirror is dated 2026-09-23 and is an older snapshot.

Online project Sources checked live on 2026-10-01:
https://chatgpt.com/g/g-p-6a97d97945a48191821db914294c8a89-ic382/project
The Sources list displayed `IC382 2026 -2027 Rulebook V2.4.pdf`.

Relevant online collaboration chat read live:
https://chatgpt.com/g/g-p-6a97d97945a48191821db914294c8a89-ic382/c/6abcd66a-97e8-83ee-8775-73cdde44180b

Official direct archive:
https://download.isaacsim.omniverse.nvidia.com/isaac-sim-standalone-4.5.0-linux-x86_64.zip

Current NVIDIA requirements and CPU tuning documentation consulted live:
https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html
https://docs.isaacsim.omniverse.nvidia.com/latest/reference_material/sim_performance_optimization_handbook.html
