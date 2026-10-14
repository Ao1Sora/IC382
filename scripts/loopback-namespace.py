#!/usr/bin/env python3
"""Run a desktop streaming session in a private, loopback-only network."""
import ctypes
import fcntl
import os
import socket
import struct
import subprocess
import sys

uid, gid = os.getuid(), os.getgid()
libc = ctypes.CDLL(None, use_errno=True)
if libc.unshare(0x10000000 | 0x40000000):
    raise OSError(ctypes.get_errno(), "Cannot create private user/network namespaces")
with open('/proc/self/setgroups', 'w') as file:
    file.write('deny')
with open('/proc/self/uid_map', 'w') as file:
    file.write(f'{uid} {uid} 1\n')
with open('/proc/self/gid_map', 'w') as file:
    file.write(f'{gid} {gid} 1\n')
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as control:
    request = struct.pack('16sH14s', b'lo', 0, b'')
    flags = struct.unpack('16sH14s', fcntl.ioctl(control, 0x8913, request))[1]
    fcntl.ioctl(control, 0x8914, struct.pack('16sH14s', b'lo', flags | 1, b''))
# WebRTC omits loopback addresses when gathering ICE candidates. Add a dummy
# interface within this namespace; it has no link to the host or Internet.
class CapHeader(ctypes.Structure):
    _fields_ = [('version', ctypes.c_uint32), ('pid', ctypes.c_int)]
class CapData(ctypes.Structure):
    _fields_ = [('effective', ctypes.c_uint32), ('permitted', ctypes.c_uint32),
                ('inheritable', ctypes.c_uint32)]
header = CapHeader(0x20080522, 0)
caps = (CapData * 2)()
if libc.capget(ctypes.byref(header), caps):
    raise OSError(ctypes.get_errno(), 'capget')
caps[0].inheritable |= 1 << 12  # CAP_NET_ADMIN, within the private namespace
if libc.capset(ctypes.byref(header), caps) or libc.prctl(47, 2, 12, 0, 0):
    raise OSError(ctypes.get_errno(), 'Private interface configuration capability')
try:
    subprocess.run(['ip', 'link', 'add', 'ic382-local', 'type', 'dummy'], check=True)
    subprocess.run(['ip', 'addr', 'add', '10.238.38.1/24', 'dev', 'ic382-local'], check=True)
    subprocess.run(['ip', 'link', 'set', 'ic382-local', 'up'], check=True)
finally:
    libc.prctl(47, 4, 0, 0, 0)  # Drop all ambient capabilities before app startup.
os.environ['IC382_LOOPBACK_ONLY'] = '1'
os.execvp(sys.argv[1], sys.argv[1:])
