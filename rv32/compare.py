"""Measure equivalent GCC -O2 and handwritten RV32I cores on pinned Ripes.

Every result is replayed independently, checked against the certified BFS
distance, and checked for ABI preservation. All variants use compare_start.S.
Counts include the common harness; exclude text parsing, printing and rendering.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import json
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
import time

from check_asm import MOVES, SOLVED, ROOT, encode, move, sha
from inspect_elf import rv32i
from measure_rv32 import decode_state, elf_sections

VARIANTS = ("gcc_O2", "asm_baseline", "asm_leaf", "asm_cached")
LIMIT = 50_000_000


def inspect(path, objdump, host_tables):
    data = path.read_bytes()
    sections = elf_sections(data)
    code = sections[".text"]
    if code[5] % 4:
        raise AssertionError("instruction section is not word aligned")
    for i in range(0, code[5], 4):
        word = struct.unpack_from("<I", data, code[4] + i)[0]
        if not rv32i(word):
            raise AssertionError(f"{path}: non-RV32I word at {code[3]+i:#x}")
    symbols = {}
    for line in subprocess.check_output([objdump, "-t", str(path)], text=True).splitlines():
        fields = line.split()
        if len(fields) >= 5:
            try:
                symbols[fields[-1]] = int(fields[0], 16)
            except ValueError:
                pass
    rodata = sections[".rodata"]

    def table_at(symbol, size):
        offset = rodata[4] + symbols[symbol] - rodata[3]
        return data[offset:offset + size]

    if "pdb_tables" in symbols:
        actual = (table_at("pdb_tables", 68040) + table_at("coordinate_turn", 10080)
                  + table_at("orientation_add", 6561))
    else:
        actual = (table_at("asm_pdb_a", 34020) + table_at("asm_pdb_b", 34020)
                  + table_at("asm_coordinate_turn", 10080) + table_at("asm_orientation_add", 6561))
    if actual != host_tables:
        raise AssertionError(f"{path}: benchmark tables differ from the C reference")
    static = {n: s[5] for n, s in sections.items() if s[2] & 2 and not s[2] & 4}
    if sum(static.values()) > 131072:
        raise AssertionError(f"{path}: static data exceeds 128 KiB")
    if sections[".data"][5] != 14 or sections[".bss"][5] != 11:
        raise AssertionError("expected normalized 14-byte input and 11-byte path")
    return data, sections[".data"][4], dict(text_bytes=code[5], static_sections=static,
                                          static_bytes=sum(static.values()), elf_sha256=sha(path),
                                          isa="RV32I", table_bytes_checked=len(actual))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ripes", required=True)
    parser.add_argument("--cc", default="riscv64-unknown-elf-gcc")
    parser.add_argument("--objdump", default="riscv64-unknown-elf-objdump")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, help="partial hard-case smoke run; never reports FULL PASS")
    parser.add_argument("--proc", choices=("RV32_ISS", "RV32_5S"), default="RV32_ISS")
    parser.add_argument("--xvfb")
    parser.add_argument("--xvfb-library-dir")
    parser.add_argument("--output", type=Path, default=ROOT / "rv32/results/comparison")
    args = parser.parse_args()
    if args.workers <= 0 or (args.limit is not None and args.limit <= 0):
        parser.error("workers and limit must be positive")
    pin = json.loads((ROOT / "tests/ripes_pin.json").read_text())
    if sha(args.ripes) != pin["binary_sha256"]:
        raise RuntimeError("Ripes executable does not match the pinned version")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").unlink(missing_ok=True)
    subprocess.run(["make", "-C", str(ROOT / "rv32"), "compare-build",
                    "RV32_CC=" + args.cc], check=True)
    host_tables = subprocess.check_output([str(ROOT / "rv32/build/export_tables"), "--binary"])
    templates, meta = {}, {}
    for name in VARIANTS:
        path = ROOT / f"rv32/build/{name}.elf"
        template, offset, metadata = inspect(path, args.objdump, host_tables)
        templates[name] = (template, offset)
        meta[name] = metadata
        (output / f"{name}.dis").write_text(subprocess.check_output(
            [args.objdump, "-d", "-M", "no-aliases", str(path)], text=True))
    sources = [ROOT / "ida_solver.c", ROOT / "pdb_data.h", ROOT / "rv32/solver.S",
               ROOT / "rv32/c_core.c", ROOT / "rv32/compare_start.S", ROOT / "rv32/Makefile",
               Path(__file__).resolve(), ROOT / "tests/exact_distances.bin"]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    distances = (ROOT / "tests/exact_distances.bin").read_bytes()
    hard = [i for i, d in enumerate(distances) if d == 11]
    if len(distances) != 3674160 or len(hard) != 2644:
        raise RuntimeError("expected complete BFS oracle with 2644 distance-11 states")
    selected = hard if args.limit is None else hard[:args.limit]
    cases = {}
    for line in (ROOT / "tests/solutions.txt").read_text().splitlines():
        if line and not line.startswith("#"):
            code, solution = line.split("|")
            state = bytes(int(c) - 1 for c in code)
            cases[code] = (state, len(solution.split()), None)
    for index in range(9):
        state = move(SOLVED, index)
        cases[encode(state)] = (bytes(state[0] + state[1]), 1, None)
    for rank in selected:
        state = decode_state(rank)
        code = "".join(str(v + 1) for v in state)
        cases[code] = (state, 11, rank)
    env = dict(os.environ, QT_QPA_PLATFORM="xcb")
    rows, server = [], None
    with tempfile.TemporaryDirectory(prefix="minirubik-compare-") as directory:
        temp = Path(directory)
        env["XDG_CONFIG_HOME"] = str(temp / "config")
        try:
            if args.xvfb:
                xenv = dict(os.environ)
                if args.xvfb_library_dir:
                    xenv["LD_LIBRARY_PATH"] = args.xvfb_library_dir
                display = next(str(n) for n in random.sample(range(100, 10000), 100)
                               if not Path(f"/tmp/.X{n}-lock").exists())
                server = subprocess.Popen(
                    [args.xvfb, ":" + display, "-screen", "0", "640x480x24", "-nolisten", "tcp", "-ac"],
                    env=xenv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                time.sleep(0.5)
                if server.poll() is not None:
                    raise RuntimeError(server.stderr.read())
                env["DISPLAY"] = ":" + display

            def measure(number, code, case):
                state, expected, rank = case
                row = dict(state=code, rank=rank, expected=expected, status="PASS")
                paths = []
                for name in VARIANTS:
                    template, offset = templates[name]
                    patched = bytearray(template)
                    patched[offset:offset + 14] = state
                    image = temp / f"{number}_{name}.elf"
                    report_file = temp / f"{number}_{name}.json"
                    image.write_bytes(patched)
                    command = [args.ripes, "--mode", "cli", "--src", str(image), "-t", "elf",
                               "--proc", args.proc, "--iret", "--regs", "--json", "--runinfo",
                               "--exectime", "--timeout", "60000", "--output", str(report_file)]
                    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=75)
                    if result.returncode or result.stdout.strip() != "Program exited with code: 0":
                        raise RuntimeError((code, name, result.returncode, result.stdout, result.stderr))
                    report = json.loads(report_file.read_text())
                    regs, info = report["registers"], report["runinfo"]
                    length = regs["x10"]
                    if info["processor"] != args.proc or info["ISA extensions"]:
                        raise AssertionError(info)
                    if length != expected or regs["x15"] or regs["x2"] != 0x100000:
                        raise AssertionError((code, name, "length/ABI mismatch", regs))
                    packed = b"".join(int(regs[f"x{i}"]).to_bytes(4, "little") for i in (11, 12, 13))
                    path = tuple(packed[:length])
                    if any(m >= 9 for m in path):
                        raise AssertionError((code, name, "invalid move IDs", path))
                    replay = (tuple(state[:7]), tuple(state[7:]))
                    for index in path:
                        replay = move(replay, index)
                    if replay != SOLVED:
                        raise AssertionError((code, name, "replay failed", path, replay))
                    count = report["# instructions retired"]
                    if count > LIMIT:
                        raise AssertionError((code, name, "instruction budget exceeded", count))
                    row[name] = count
                    row[name + "_ms"] = report["execution time (ms)"]
                    row[name + "_actual"] = length
                    paths.append(path)
                    image.unlink()
                    report_file.unlink()
                if len(set(paths)) != 1:
                    raise AssertionError((code, "search order mismatch", paths))
                row["solution"] = " ".join(MOVES[i] for i in paths[0])
                row["saved_vs_GCC"] = row["gcc_O2"] - row["asm_cached"]
                row["improvement_percent"] = 100 * row["saved_vs_GCC"] / row["gcc_O2"]
                return row

            with (output / "comparison.csv").open("w", newline="") as file:
                fields = ["state", "rank", "expected", "status", "solution"]
                for name in VARIANTS:
                    fields.extend([name, name + "_actual", name + "_ms"])
                fields.extend(["saved_vs_GCC", "improvement_percent"])
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                with ThreadPoolExecutor(max_workers=args.workers) as pool:
                    futures = {pool.submit(measure, i, code, case): (code, case[1])
                               for i, (code, case) in enumerate(cases.items())}
                    for future in as_completed(futures):
                        try:
                            row = future.result()
                        except Exception as error:
                            code, expected = futures[future]
                            writer.writerow(dict(state=code, expected=expected, status="FAIL", solution=str(error)))
                            file.flush()
                            raise
                        rows.append(row)
                        writer.writerow(row)
                        file.flush()
                        if len(rows) % 100 == 0 or len(rows) == len(cases):
                            print(f"PASS {len(rows)}/{len(cases)} across {len(VARIANTS)} cores", flush=True)
        finally:
            if server is not None:
                server.terminate()
                server.wait(timeout=10)
    if hashes != {str(p.relative_to(ROOT)): sha(p) for p in sources}:
        raise RuntimeError("benchmark source/oracle changed during execution; rerun required")
    hard_rows = [r for r in rows if r["rank"] is not None]
    full = args.limit is None and len(hard_rows) == 2644
    totals, worst = {}, {}
    for name in VARIANTS:
        totals[name] = sum(r[name] for r in hard_rows)
        r = max(hard_rows, key=lambda r: r[name])
        worst[name] = dict(rank=r["rank"], state=r["state"], instructions=r[name])
    compiler = subprocess.check_output([args.cc, "--version"], text=True).splitlines()[0]
    makefile = (ROOT / "rv32/Makefile").read_text()
    flags = {line.split(":=", 1)[0].strip(): line.split(":=", 1)[1].strip()
             for line in makefile.splitlines() if line.startswith(("FLAGS :=", "CFLAGS_CORE :=", "ASM_OPTFLAGS :="))}
    summary = dict(status="FULL PASS" if full else "PARTIAL PASS", cases=len(rows),
                   measured_runs=len(rows) * len(VARIANTS), distance11_count=len(hard_rows),
                   processor=args.proc, isa="RV32I", ripes_version=pin["version"],
                   ripes_sha256=sha(args.ripes), compiler=compiler, build_flags=flags,
                   link_extra_flags="-Wl,--gc-sections", definitions=dict(gcc_O2="BENCH_C",
                   asm_baseline="none", asm_leaf="ASM_REMOVE_LEAF_RA",
                   asm_cached="ASM_REMOVE_LEAF_RA + ASM_CACHE_FACE_ROW"),
                   variants=meta, source_hashes=hashes, command=sys.argv,
                   measurement_boundary="normalized state; includes identical startup, ABI probes, result packing and exit; no parsing/output/renderer",
                   retired_instruction_limit=LIMIT, worst=worst, distance11_total=totals,
                   aggregate_improvement_percent=100 * (totals["gcc_O2"] - totals["asm_cached"]) / totals["gcc_O2"],
                   optimizations=dict(leaf_saved_instructions=totals["asm_baseline"] - totals["asm_leaf"],
                                      cache_saved_instructions=totals["asm_leaf"] - totals["asm_cached"]))
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
