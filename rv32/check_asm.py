"""Run the actual handwritten RV32I ELF on pinned Ripes; replay every path.

Default coverage: optimal vectors and invalid inputs. --shallow adds all 385
states through depth 3; --distance11 adds all 2,644 oracle distance-11 states.
--distance11-only measures the final CLI over exactly the complete hard set.
Its counts include parsing, validation, search, solution printing and exit;
they must be kept separate from the normalized-input compiler comparison.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
import time
from collections import deque

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from measure_rv32 import elf_sections, decode_state
from inspect_elf import rv32i

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
    parser.add_argument("--distance11-only", action="store_true",
                        help="only the 2644 hard states; report the full-program instruction budget")
    parser.add_argument("--representative", action="store_true",
                        help="only solved, a one-move scramble, and the required distance-11 vector")
    parser.add_argument("--require-verification", action="store_true",
                        help="require the CLI's in-program replay status in a4")
    parser.add_argument("--verifier-gate", type=Path,
                        help="also run the test-only 13-case positive/negative replay gate")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--xvfb")
    parser.add_argument("--xvfb-library-dir")
    parser.add_argument("--output", type=Path, default=ROOT / "rv32/results")
    args = parser.parse_args()
    if args.workers <= 0:
        parser.error("--workers must be positive")
    if args.representative and (args.shallow or args.smoke or args.distance11 or args.distance11_only):
        parser.error("--representative cannot be combined with other case selectors")
    if args.distance11_only:
        if args.shallow or args.smoke or args.proc != "RV32_ISS":
            parser.error("--distance11-only requires RV32_ISS without --shallow or --smoke")
        args.distance11 = True
    if args.smoke and (args.shallow or args.distance11):
        parser.error("--smoke cannot be combined with --shallow or --distance11")
    pin = json.loads((ROOT / "tests/ripes_pin.json").read_text())
    if sha(args.ripes) != pin["binary_sha256"]:
        raise RuntimeError("Ripes binary does not match the repository pin")
    template = args.elf.read_bytes()
    sections = elf_sections(template)
    text = sections[".text"]
    if text[5] % 4 or any(not rv32i(struct.unpack_from("<I", template, text[4] + i)[0])
                          for i in range(0, text[5], 4)):
        raise RuntimeError("linked program contains a non-RV32I instruction")
    slot = sections[".data"]
    if slot[5] != 32:
        raise RuntimeError("expected exactly 32 input bytes in .data")
    static = {n: s[5] for n, s in sections.items() if s[2] & 2 and not s[2] & 4}
    if sum(static.values()) > 131072:
        raise RuntimeError("static data exceeds 128 KiB")
    source_paths = [ROOT / name for name in (
        "rv32/solver.S", "rv32/solver.h", "rv32/start.S", "rv32/Makefile", "rv32/check_asm.py",
        "rv32/inspect_elf.py", "rv32/export_tables.c", "generate_pdb.c", "pdb.h",
        "cube_moves.h", "pdb_data.h", "ida_solver.c", "tests/rv32.ld",
        "tests/measure_rv32.py", "tests/ripes_pin.json", "tests/solutions.txt")]
    if args.verifier_gate:
        source_paths.append(ROOT / "rv32/verification_gate.S")
    source_hashes = {str(path.relative_to(ROOT)): sha(path) for path in source_paths}
    elf_sha = sha(args.elf)
    cases, ranks = {}, {}
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
        if args.distance11_only:
            certified = json.loads((ROOT / "rv32/validation/comparison_full/summary.json").read_text())
            if oracle_sha != certified["source_hashes"]["tests/exact_distances.bin"]:
                raise RuntimeError("BFS oracle differs from the certified full comparison")
        for rank, distance in enumerate(data):
            if distance == 11:
                code = "".join(str(v + 1) for v in decode_state(rank))
                cases[code] = 11
                ranks[code] = rank
    for code in ("", "1234567111111", "123456711111111", "02345671111111",
                 "82345671111111", "12345671111110", "12345671111114",
                 "1234567111111a", "11345671111111", "12345671111112",
                 "12345671111113", "76543213333333"):
        cases[code] = -2
    if args.distance11_only:
        cases = {code: expected for code, expected in cases.items() if expected == 11}
        if len(cases) != 2644 or set(cases) != set(ranks):
            raise RuntimeError("hard cases do not exactly match the complete BFS oracle")
    if args.representative:
        cases = {encode(SOLVED): 0, "25314672313211": 1, "21345671111111": 11}
    args.output.mkdir(parents=True, exist_ok=True)
    # A failed rerun must not leave an earlier success summary in place.
    (args.output / f"correctness_{args.proc}.json").unlink(missing_ok=True)
    env = dict(os.environ, QT_QPA_PLATFORM="xcb")
    rows, server, gate_result = [], None, None
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

            if args.verifier_gate:
                gate_report = temp / "verifier_gate.json"
                command = [args.ripes, "--mode", "cli", "--src", str(args.verifier_gate),
                           "-t", "elf", "--proc", args.proc, "--iret", "--regs", "--json",
                           "--runinfo", "--timeout", "60000", "--output", str(gate_report)]
                result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=75)
                report = json.loads(gate_report.read_text())
                regs, info = report["registers"], report["runinfo"]
                if (result.returncode or result.stdout.strip() != "Program exited with code: 0"
                        or regs["x10"] != 0 or regs["x11"] != 13 or regs["x2"] != 0x100000
                        or info["processor"] != args.proc or info["ISA extensions"]):
                    raise AssertionError(("verifier gate failed", result.stdout, result.stderr, report))
                gate_result = dict(status="PASS", cases=13, elf_sha256=sha(args.verifier_gate),
                                   command=command, report=report)
                print(f"Verifier positive/negative gate: PASS 13/13 ({args.proc})", flush=True)

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
                if args.require_verification and report["registers"]["x14"] != int(expected >= 0):
                    raise AssertionError((code, "in-program replay status mismatch", report["registers"]))
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
                if args.distance11_only:
                    row["rank"] = ranks[code]
                if args.require_verification:
                    row["in_program_verification"] = "PASS" if expected >= 0 else "SKIPPED"
                image.unlink()
                report_path.unlink()
                return row

            with (args.output / f"correctness_{args.proc}.csv").open("w", newline="") as file:
                fields = ("state", "expected", "actual", "output", "status",
                          "retired_instructions_with_output")
                if args.distance11_only:
                    fields = ("rank",) + fields
                if args.require_verification:
                    fields += ("in_program_verification",)
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
    if sha(args.elf) != elf_sha or any(sha(ROOT / name) != digest
                                     for name, digest in source_hashes.items()):
        raise RuntimeError("program or source changed during the run")
    if args.distance11 and sha(ROOT / "tests/exact_distances.bin") != oracle_sha:
        raise RuntimeError("BFS oracle changed during the run")
    if sha(args.ripes) != pin["binary_sha256"]:
        raise RuntimeError("Ripes executable changed during the run")
    summary = dict(status="PASS", processor=args.proc, isa="RV32I", count=len(rows),
                   shallow=args.shallow, smoke=args.smoke, all_distance11=args.distance11,
                   sections=static, static_bytes=sum(static.values()),
                   text_bytes=sections[".text"][5], ripes_version=pin["version"],
                   elf_sha256=elf_sha, assembly_sha256=sha(ROOT / "rv32/solver.S"),
                   ripes_sha256=sha(args.ripes), oracle_sha256=oracle_sha,
                   source_hashes=source_hashes, command=sys.argv,
                   instruction_counts="full text-entry CLI: startup, parsing, validation, search, path generation, solution printing and normal exit; no renderer")
    if args.require_verification:
        summary.update(in_program_verification_required=True,
                       in_program_verified_cases=sum(row["expected"] >= 0 for row in rows),
                       instruction_counts="full text-entry CLI: startup, parsing, validation, search, path generation, in-program concrete replay, solution printing and normal exit; no renderer")
    if args.representative:
        summary["representative_cases"] = True
    if gate_result is not None:
        summary["verifier_gate"] = gate_result
    if args.distance11_only:
        counts = "retired_instructions_with_output"
        worst = max(rows, key=lambda row: row[counts])
        vector = next(row for row in rows if row["state"] == "21345671111111")
        exceeded = sum(row[counts] > 50_000_000 for row in rows)
        summary.update(benchmark="final optimized full-program CLI", distance11_count=len(rows),
                       all_optimal_and_independent_replay_passed=True,
                       retired_instruction_limit=50_000_000, states_exceeding_limit=exceeded,
                       grading_pass=exceeded == 0,
                       maximum=dict(state=worst["state"], rank=worst["rank"], instructions=worst[counts]),
                       minimum_instructions=min(row[counts] for row in rows),
                       vector_21345671111111=dict(instructions=vector[counts], length=vector["actual"],
                                               solution=vector["output"]))
        if exceeded:
            summary["status"] = "BUDGET FAIL"
    (args.output / f"correctness_{args.proc}.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if args.distance11_only and not summary["grading_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
