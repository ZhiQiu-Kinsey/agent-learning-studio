"""Release smoke check: it prints a long progress log, then waits for a release server that never answers.

The lesson uses it to show a command that does not finish: the platform has to stop it,
and stop the helper process it started too.
"""
import subprocess
import sys

for number in range(1, 601):
    print(f'checking item {number:04d} ... ok', flush=True)

helper = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'])
print(f'helper pid {helper.pid}: waiting for the release server', flush=True)
helper.wait()
