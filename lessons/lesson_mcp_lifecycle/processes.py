"""Two process-level operations the host needs and the MCP SDK does not offer: stop a server for real, and check it is gone.

Both take the pid a server reported about itself (the ``service_info`` tool), so they work the same whether the
server was started by this run or by an earlier connection.
"""
import os
import signal
import time


def stop_process(pid: int):
    """Kill a server without warning, the way a crash would: no stdin close, no grace period."""
    # Windows has no SIGKILL; os.kill with SIGTERM calls TerminateProcess there, which is just as abrupt.
    os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))


def pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x00100000 | 0x1000, False, pid)  # SYNCHRONIZE | QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT: still running
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # signal 0 checks existence without touching the process
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_gone(pids: list[int], timeout: float = 3.0) -> list[int]:
    """Pids still running after ``timeout`` seconds; an empty list means every server process exited."""
    deadline = time.monotonic() + timeout
    alive = [pid for pid in pids if pid_alive(pid)]
    while alive and time.monotonic() < deadline:
        time.sleep(0.05)
        alive = [pid for pid in alive if pid_alive(pid)]
    return alive
