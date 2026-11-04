"""Physical startup/shutdown smoke check. Sends no movement keys."""
import os
from pathlib import Path
import pty
import select
import subprocess
import time

master, slave = pty.openpty()
root = Path(__file__).resolve().parents[1]
process = subprocess.Popen(['bash', str(root/'run.sh'), 'manual'],
    stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
output = b''
try:
    deadline = time.monotonic()+40
    while time.monotonic()<deadline and process.poll() is None:
        if select.select([master], [], [], .2)[0]:
            output += os.read(master, 65536)
        if b'IC382 ROBOT CONSOLE' in output:
            # Keyboard is in raw terminal mode; Ctrl+C is processed by the teacher loop.
            os.write(master, b'\x03')
            process.wait(timeout=15)
            assert process.returncode == 0, output.decode(errors='replace')
            print('PASS: real main entry started chassis and keyboard; Ctrl+C exited. No movement keys sent.')
            break
    else:
        raise RuntimeError(output.decode(errors='replace'))
finally:
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=20)
    os.close(master); os.close(slave)
