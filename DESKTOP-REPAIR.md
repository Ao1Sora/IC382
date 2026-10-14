# Isaac Sim desktop repair — 2026-10-01

## Confirmed issues

The original VNC display uses Mesa llvmpipe, without hardware acceleration.
Native Isaac Sim GUI initialization crashes in NVIDIA EGL 550.54.14.
Full Isaac Sim started with `DISPLAY` unset and `--no-window` reached `app ready`.
The first streaming attempt also reached `app ready`, but its native streaming
plugin could not load because the system C++ runtime lacks `GLIBCXX_3.4.26`.
An app-ready message alone does not prove that streaming works.

## User-level repair

`scripts/isaac-desktop.sh` starts the official full streaming application with
the VNC display removed from the renderer environment. The NVIDIA WebRTC
client 1.0.6 then displays the interface inside the existing VNC desktop.
Both processes share a private network namespace containing loopback and an
unconnected dummy interface at `10.238.38.1`. WebRTC does not gather candidates
from loopback alone. The client disables mDNS address hiding within this
private network so that its local media address is usable by the server.
No streaming port is reachable outside that namespace. Chromium uses its
user-namespace sandbox; the unavailable setuid helper is disabled.

The launcher adds project-local C++ runtime libraries from verified
conda-forge packages:

- `libstdcxx-ng-12.2.0-h46fd767_19.tar.bz2`, MD5 `1030b1f38c129f2634eae026f704fe60`
- `libgcc-ng-12.2.0-h65d4601_19.tar.bz2`, MD5 `e4c94f80aef025c17ab0828cd85ef535`

They are installed under `tools/cpp-runtime`; system libraries are unchanged.
The runtime resolves the streaming plugin's missing C++ dependency and links
against the existing Rocky Linux glibc. Package metadata is saved in `logs/`.

Use the launcher inside the GPU allocation's VNC desktop. In the client, use
`10.238.38.1` and click **Connect**. This address is reachable only within the
private desktop session. The launcher waits for both application
readiness and TCP port 49100. Closing the client stops its render process.
Only one session can run per project, guarded by an advisory lock.

## Current verification

The new C++ runtime was verified: the streaming server starts and listens on
TCP 49100. The client runs with `--enable-sandbox` in its renderer process.
Native GUI startup still crashes in NVIDIA EGL after adding the C++ runtime.
The first isolated stream with only loopback failed ICE/media connectivity;
the dummy-interface fix was verified: the user confirmed on 2026-10-01 that
connecting to `10.238.38.1` displays an interactive Isaac Sim interface. This is
direct user confirmation; the agent verified process state, logs and port readiness.
The Desktop shortcut now uses this launcher. The original shortcut is backed
up under `logs/IC382-IsaacSim.desktop.before-repair`.

## Limitations

The private network has no Internet or external ROS 2 connectivity. Local
files remain accessible, but online assets must be downloaded separately
before opening them. The bundled ROS 2 bridge also still fails initialization
on this host and has not been repaired by this desktop change.
The system NVIDIA driver and X server remain unchanged.
This is an alternate desktop display path, not a driver repair.

Logs: `logs/desktop-launch.log`, `logs/desktop-server.log`,
`logs/desktop-client.log`, `logs/repair-native-gdb.log`.
