# IC382

Remote development and Isaac Sim workspace on the PolyU HPC.

GitHub repository: https://github.com/Ao1Sora/IC382 (private).
Initial development branch: `codex/setup`.

Project path: `~/Desktop/IC382` (shared home storage, persistent across GPU jobs).

## Environment

- Host: Rocky Linux 8.10, glibc 2.28.
- Allocated GPU verified on 2026-10-01: RTX 3080 Ti, 12 GB VRAM, driver 550.54.14.
- Simulator: NVIDIA Isaac Sim 4.5.0 standalone Linux x86_64.
- Runtime: native Rocky Linux; bundled Python 3.10.15. The isolated Ubuntu fallback was prepared but is not used by the launchers.
- Downloads and runtime are stored in `tools/`, `downloads/`, and `cache/`, excluded from Git.
- No host OS or GPU driver changes were required.

## Start GUI

Use the existing `hpc/Connect-Gui.cmd` on the local Windows computer to open the allocated GPU desktop. In the desktop terminal:

```bash
cd ~/Desktop/IC382
./scripts/isaac-desktop.sh
```

The launcher requires an existing Slurm GPU allocation. Do not run on the login node.

Or double-click `IC382 Isaac Sim 4.5` on the server Desktop. When the streaming
client opens, enter `10.238.38.1` and click **Connect**. The user confirmed that
the interface is visible and interactive on 2026-10-01. Startup takes about two
minutes with the existing cache. Closing the client stops its render process.

This uses a private network and project-local C++ libraries to avoid the
native VNC/NVIDIA EGL crash. Online assets and external ROS 2 networking are
unavailable in this mode; use local project files. See [DESKTOP-REPAIR.md](DESKTOP-REPAIR.md).

## Run Python or the smoke test

Use `hpc/Connect-Hpc.cmd` locally to open a shell inside the GPU allocation:

```bash
cd ~/Desktop/IC382
./scripts/isaac-python.sh scripts/smoke-test.py
```

Pass absolute paths for scripts outside the simulator directory:

```bash
./scripts/isaac-python.sh "$PWD/scripts/smoke-test.py"
```

A successful test prints `IC382_SMOKE_TEST_PASSED` after rendering and simulating a falling cube for 60 steps.

## Layout

- `scripts/`: project launchers, installation helpers, smoke test.
- `scenes/`: simulation scenes.
- `robots/`: robot descriptions and models.
- `ros2_ws/`: ROS 2 workspace (reserved; ROS 2 has not been installed).
- `logs/`: installation, native compatibility, and smoke-test results.

## Installation sources

The server directly downloaded the official 7,208,817,125-byte archive:
https://download.isaacsim.omniverse.nvidia.com/isaac-sim-standalone-4.5.0-linux-x86_64.zip

Archive integrity is checked using `unzip -tq`; its local SHA-256 is recorded in `logs/isaacsim-archive.sha256` (a local fingerprint, not an independently published vendor checksum).

Current NVIDIA installation documentation:
https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html

Current releases require newer drivers and larger GPU memory than this allocation. Version 4.5 is chosen for this older workstation and validated separately.

Project sources and collaboration context were checked live on 2026-10-01:
https://chatgpt.com/g/g-p-6a97d97945a48191821db914294c8a89-ic382/project
https://chatgpt.com/g/g-p-6a97d97945a48191821db914294c8a89/c/6abcd66a-97e8-83ee-8775-73cdde44180b

The live Sources list displayed `IC382 2026 -2027 Rulebook V2.4.pdf`; the local Windows `chatgpt-sync` mirror dated 2026-09-23 is an older snapshot.

## Verified result

See [INSTALLATION.md](INSTALLATION.md) for the passed native GPU/render/physics test and first-start timing.
