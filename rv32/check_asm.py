"""Run the actual handwritten RV32I ELF on pinned Ripes; replay every path.

Default coverage: optimal vectors and invalid inputs. --shallow adds all 385
states through depth 3; --distance11 adds all 2,644 oracle distance-11 states.
The printed ELF is for correctness only; its instruction counts include output.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time
from collections import deque

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from measure_rv32 import elf_sections, decode_state

MOVES = ("R", "R2", "R'", "B", "B2", "B'", "D", "D2", "D'")
SOLVED = (tuple(range(7)), (0,) * 7)
CYCLES = ((0, 3, 4, 1), (3, 6, 5, 4), (1, 4, 5, 2))
TWISTS = ({0: 1, 1: 2, 3: 2, 4: 1}, {3: 1, 4: 2, 5: 1, 6: 2}, {})


def move(state, index):
    p, o = state
    face, turn = divmod(index, 3)
    cycle = CYCLES[face]
    for _ in range(turn + 1):
        np, no = list(p), list(o)
        for source, dest in zip(cycle, cycle[1:] + cycle[:1]):
            np[dest] = p[source]
            no[dest] = (o[source] + TWISTS[face].get(dest, 0)) % 3
        p, o = tuple(np), tuple(no)
    return p, o


def encode(state):
    return "".join(str(v + 1) for part in state for v in part)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ripes", required=True)
    parser.add_argument("--elf", type=Path, default=ROOT / "rv32/build/solver.elf")
    parser.add_argument("--proc", choices=("RV32_ISS", "RV32_5S"), default="RV32_ISS")
    parser.add_argument("--shallow", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="solved, nine one-move states, and invalid inputs")
    parser.add_argument("--distance11", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--xvfb")
    parser.add_argument("--xvfb-library-dir")
    parser.add_argument("--output", type=Path, default=ROOT / "rv32/results")
    args = parser.parse_args()
    if args.smoke and (args.shallow or args.distance11):
        parser.error("--smoke cannot be combined with --shallow or --distance11")
    pin = json.loads((ROOT / "tests/ripes_pin.json").read_text())
    if sha(args.ripes) != pin["binary_sha256"]:
        raise RuntimeError("Ripes binary does not match the repository pin")
    template = args.elf.read_bytes()
    sections = elf_sections(template)
    slot = sections[".data"]
    if slot[5] != 32:
        raise RuntimeError("expected exactly 32 input bytes in .data")
    static = {n: s[5] for n, s in sections.items() if s[2] & 2 and not s[2] & 4}
    if sum(static.values()) > 131072:
        raise RuntimeError("static data exceeds 128 KiB")
    cases = {}
    for line in (ROOT / "tests/solutions.txt").read_text().splitlines():
        if line and not line.startswith("#"):
            code, path = line.split("|")
            cases[code] = len(path.split())
    cases[encode(SOLVED)] = 0
    if args.smoke:
        cases = {encode(SOLVED): 0}
    for index in range(9):
        cases[encode(move(SOLVED, index))] = 1
    if args.shallow:
        distances = {SOLVED: 0}
        queue = deque([SOLVED])
        while queue:
            state = queue.popleft()
            depth = distances[state]
            cases[encode(state)] = depth
            if depth == 3:
                continue
            for index in range(9):
                child = move(state, index)
                if child not in distances:
                    distances[child] = depth + 1
                    queue.append(child)
    oracle_sha = None
    if args.distance11:
        oracle = ROOT / "tests/exact_distances.bin"
        data = oracle.read_bytes()
        if len(data) != 3674160 or data.count(11) != 2644:
            raise RuntimeError("expected complete BFS oracle with 2644 distance-11 states")
        oracle_sha = sha(oracle)
        for rank, distance in enumerate(data):
            if distance == 11:
                cases["".join(str(v + 1) for v in decode_state(rank))] = 11
    for code in ("", "1234567111111", "123456711111111", "02345671111111",
                 "82345671111111", "12345671111110", "12345671111114",
                 "1234567111111a", "11345671111111", "12345671111112",
                 "12345671111113", "76543213333333"):
        cases[code] = -2
    args.output.mkdir(parents=True, exist_ok=True)
    # A failed rerun must not leave an earlier success summary in place.
    (args.output / f"correctness_{args.proc}.json").unlink(missing_ok=True)
    env = dict(os.environ, QT_QPA_PLATFORM="xcb")
    rows, server = [], None
    with tempfile.TemporaryDirectory(prefix="minirubik-asm-") as temp:
        temp = Path(temp)
        env["XDG_CONFIG_HOME"] = str(temp / "config")
        try:
            if args.xvfb:
                xenv = dict(os.environ)
                if args.xvfb_library_dir:
                    xenv["LD_LIBRARY_PATH"] = args.xvfb_library_dir
                display = next(str(n) for n in random.sample(range(100, 10000), 100)
                               if not Path(f"/tmp/.X{n}-lock").exists())
                server = subprocess.Popen(
                    [args.xvfb, ":" + display, "-screen", "0", "640x480x24",
                     "-nolisten", "tcp", "-ac"], env=xenv, text=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                # Some managed hosts expose X11's abstract socket but hide its
                # filesystem socket. Do not use a /tmp/.X11-unix existence gate.
                time.sleep(0.5)
                if server.poll() is not None:
                    raise RuntimeError(server.stderr.read())
                env["DISPLAY"] = ":" + display

            def check(number, code, expected):
                patched = bytearray(template)
                encoded = code.encode("ascii") + b"\0"
                if len(encoded) > 32:
                    raise ValueError("input exceeds patch slot")
                patched[slot[4]:slot[4] + 32] = encoded.ljust(32, b"\0")
                image = temp / f"case_{number}.elf"
                report_path = temp / f"case_{number}.json"
                image.write_bytes(patched)
                command = [args.ripes, "--mode", "cli", "--src", str(image),
                           "-t", "elf", "--proc", args.proc, "--iret", "--regs",
                           "--json", "--runinfo", "--timeout", "60000",
                           "--output", str(report_path)]
                result = subprocess.run(command, env=env, capture_output=True,
                                        text=True, timeout=75)
                if result.returncode or "Program exited with code: 0" not in result.stdout:
                    raise RuntimeError(f"{code}: Ripes failed: {result.stdout}\n{result.stderr}")
                report = json.loads(report_path.read_text())
                length = report["registers"]["x10"]
                if length >= 2**31:
                    length -= 2**32
                # Ripes forwards program ecalls to stdout before its exit message.
                # The CLI prepends one newline to its own exit-status message.
                output = result.stdout.split("Program exited with code: 0")[0].removesuffix("\n")
                if length != expected:
                    raise AssertionError((code, expected, length, output))
                info = report["runinfo"]
                if info["processor"] != args.proc or info["ISA extensions"]:
                    raise AssertionError(info)
                if expected >= 0:
                    tokens = output.split()
                    if len(tokens) != expected or output != " ".join(tokens) + "\n":
                        raise AssertionError((code, expected, output))
                    state = (tuple(int(c) - 1 for c in code[:7]),
                             tuple(int(c) - 1 for c in code[7:]))
                    for token in tokens:
                        state = move(state, MOVES.index(token))
                    if state != SOLVED:
                        raise AssertionError((code, output, state))
                    reference = subprocess.run([str(ROOT / "ida_solver"), code],
                                               capture_output=True, text=True, check=True)
                    if output != reference.stdout:
                        raise AssertionError((code, "C search order mismatch", output, reference.stdout))
                elif output != "invalid input or search failure\n":
                    raise AssertionError((code, output))
                row = dict(state=code, expected=expected, actual=length,
                           output=output.rstrip("\n"), status="PASS",
                           retired_instructions_with_output=report["# instructions retired"])
                image.unlink()
                report_path.unlink()
                return row

            with (args.output / f"correctness_{args.proc}.csv").open("w", newline="") as file:
                fields = ("state", "expected", "actual", "output", "status",
                          "retired_instructions_with_output")
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                with ThreadPoolExecutor(max_workers=args.workers) as pool:
                    futures = {pool.submit(check, i, code, d): (code, d)
                               for i, (code, d) in enumerate(cases.items())}
                    for future in as_completed(futures):
                        try:
                            row = future.result()
                        except Exception as error:
                            code, d = futures[future]
                            writer.writerow(dict(state=code, expected=d, status="FAIL", output=str(error)))
                            file.flush()
                            raise
                        rows.append(row)
                        writer.writerow(row)
                        file.flush()
                        if len(rows) % 100 == 0 or len(rows) == len(cases):
                            print(f"PASS {len(rows)}/{len(cases)} ({args.proc})", flush=True)
        finally:
            if server is not None:
                server.terminate()
                server.wait(timeout=10)
    summary = dict(status="PASS", processor=args.proc, isa="RV32I", count=len(rows),
                   shallow=args.shallow, smoke=args.smoke, all_distance11=args.distance11,
                   sections=static, static_bytes=sum(static.values()),
                   text_bytes=sections[".text"][5], ripes_version=pin["version"],
                   elf_sha256=sha(args.elf), assembly_sha256=sha(ROOT / "rv32/solver.S"),
                   ripes_sha256=sha(args.ripes), oracle_sha256=oracle_sha,
                   command=sys.argv, instruction_counts="include parsing and solution printing")
    (args.output / f"correctness_{args.proc}.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
