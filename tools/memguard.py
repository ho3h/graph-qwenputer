#!/usr/bin/env python3
"""Run a command under a hard memory limit, and kill its whole process group if it goes over.

    memguard.py --limit-gib 12 --log out.mem -- python test.py --workers 2

macOS does not enforce RLIMIT_AS, so this polls every second. It sums phys_footprint over the group, which counts
compressed pages and GPU allocations (plain RSS does not). It also kills the group if the system's own free-memory
level (kern.memorystatus_level) falls below --min-free-pct, whichever process is responsible, so that one job cannot
take the Mac down. Exit code: the command's own, or 137 after a kill. The reason and the peak go to --log and stderr.
"""
import argparse
import ctypes
import os
import signal
import subprocess
import sys
import time

GIB = 2 ** 30
libproc = ctypes.CDLL("/usr/lib/libproc.dylib")
RUSAGE_INFO_V0 = 0
FOOTPRINT_OFFSET = 72                                     # rusage_info_v0.ri_phys_footprint


def footprint(pid):
    buf = (ctypes.c_uint64 * 16)()
    if libproc.proc_pid_rusage(pid, RUSAGE_INFO_V0, buf) != 0:
        return 0
    return buf[FOOTPRINT_OFFSET // 8]


def group_bytes(pgid):
    out = subprocess.run(["/bin/ps", "-axo", "pid=,pgid="], capture_output=True, text=True).stdout
    pids = [int(a) for a, b in (ln.split() for ln in out.splitlines()) if int(b) == pgid]
    return sum(footprint(p) for p in pids), len(pids)


def free_pct():
    out = subprocess.run(["/usr/sbin/sysctl", "-n", "kern.memorystatus_level"], capture_output=True, text=True).stdout
    return int(out.strip() or 100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-gib", type=float, required=True)
    ap.add_argument("--min-free-pct", type=int, default=15)
    ap.add_argument("--log", default="")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    log = open(a.log, "a", buffering=1) if a.log else None

    def say(msg):
        line = f"{time.strftime('%H:%M:%S')} memguard: {msg}"
        print(line, file=sys.stderr, flush=True)
        if log:
            log.write(line + "\n")

    p = subprocess.Popen(cmd, start_new_session=True)

    def forward(signum, _):                                # a timeout or kill of the guard takes the whole group with it
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        sys.exit(128 + signum)

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    pgid, peak, t0, last, why = p.pid, 0, time.time(), 0, None
    say(f"start pid {p.pid} limit {a.limit_gib} GiB, min free {a.min_free_pct}%: {' '.join(cmd)[:200]}")
    while p.poll() is None:
        used, n = group_bytes(pgid)
        peak = max(peak, used)
        level = free_pct()
        if used > a.limit_gib * GIB:
            why = f"group at {used / GIB:.1f} GiB > limit {a.limit_gib} GiB"
        elif level < a.min_free_pct:
            why = f"system free {level}% < {a.min_free_pct}% (group at {used / GIB:.1f} GiB)"
        if why:
            break
        if time.time() - last > 60:
            say(f"{time.time() - t0:.0f} s, {n} procs, {used / GIB:.2f} GiB, peak {peak / GIB:.2f}, system free {level}%")
            last = time.time()
        time.sleep(1)
    if why:
        say(f"KILL: {why}")
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(pgid, sig)
            except (ProcessLookupError, PermissionError):      # macOS: EPERM once only zombies remain
                break
            time.sleep(3)
        p.wait()
        code = 137
    else:
        code = p.returncode
    say(f"end code {code}, {time.time() - t0:.0f} s, peak {peak / GIB:.2f} GiB")
    sys.exit(code)


if __name__ == "__main__":
    main()
