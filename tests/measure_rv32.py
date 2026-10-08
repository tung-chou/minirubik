"""Measure every distance-11 input on a pinned Ripes RV32_ISS build.

Only the initial state's .data bytes differ between runs. No source recompilation,
input-specific search hints, profiling counters, or renderer is used.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import json
import os
from pathlib import Path
import select
import struct
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LIMIT = 50_000_000
FLAGS = [
    "-O3", "-std=c99", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
    "-march=rv32i", "-mabi=ilp32", "-mno-relax", "-msmall-data-limit=0",
    "-ffreestanding", "-fno-builtin", "-fno-pie", "-fno-stack-protector",
    "-ffunction-sections", "-fdata-sections", "-fno-unwind-tables",
    "-fno-asynchronous-unwind-tables", "-nostdlib", "-Wl,--gc-sections",
]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def elf_sections(binary):
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", binary)
    if header[0][:6] != b"\x7fELF\x01\x01" or header[2] != 243:
        raise ValueError("benchmark must be a little-endian RV32 ELF")
    entries = [struct.unpack_from("<IIIIIIIIII", binary, header[6] + i * header[11])
               for i in range(header[12])]
    strings = entries[header[13]]
    names = binary[strings[4]:strings[4] + strings[5]]
    return {names[s[0]:].split(b"\0", 1)[0].decode(): s for s in entries}


def decode_state(rank):
    p, o = divmod(rank, 729)
    available = list(range(7))
    cubies = []
    for factorial in (720, 120, 24, 6, 2, 1, 1):
        digit, p = divmod(p, factorial)
        cubies.append(available.pop(digit))
    orientation = [0] * 7
    for i in range(5, -1, -1):
        o, orientation[i] = divmod(o, 3)
    orientation[6] = -sum(orientation) % 3
    return bytes(cubies + orientation)


def build_benchmark(cc, elf):
    subprocess.run([cc, *FLAGS, "-Wl,-T," + str(HERE / "rv32.ld"),
                    str(HERE / "rv32_bench.c"), str(HERE / "rv32_start.S"),
                    "-o", str(elf)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ripes", required=True, help="Ripes binary (or extracted AppRun)")
    parser.add_argument("--ripes-version", default="v2.2.6-106-g5b8a616")
    parser.add_argument("--cc", default="riscv64-unknown-elf-gcc")
    parser.add_argument("--distances", type=Path, default=HERE / "exact_distances.bin")
    parser.add_argument("--output", type=Path, default=HERE / "rv32_report")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, help="smoke run only; never labels this FULL PASS")
    parser.add_argument("--xvfb", help="optional Xvfb binary for headless hosts")
    parser.add_argument("--xvfb-library-dir", help="library directory for a portable Xvfb")
    args = parser.parse_args()
    pin = json.loads((HERE / "ripes_pin.json").read_text())
    if args.ripes_version != pin["version"] or sha256(args.ripes) != pin["binary_sha256"]:
        raise RuntimeError("Ripes executable does not match tests/ripes_pin.json")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    elf = output / "ida_rv32.elf"
    build_benchmark(args.cc, elf)
    template = elf.read_bytes()
    sections = elf_sections(template)
    # Count every allocated non-code section, including small-data sections.
    static_sections = {name: s[5] for name, s in sections.items()
                       if s[2] & 2 and not s[2] & 4}
    static_bytes = sum(static_sections.values())
    if static_bytes > 128 * 1024:
        raise RuntimeError(f"static data exceeds 128 KiB: {static_bytes}")
    input_section = sections[".data"]
    if input_section[5] != 14:
        raise RuntimeError("expected only the 14-byte bench_input in .data")
    distances = args.distances.read_bytes()
    ranks = [rank for rank, d in enumerate(distances) if d == 11]
    if len(distances) != 3674160 or len(ranks) != 2644:
        raise RuntimeError("expected complete oracle with 2644 distance-11 states")
    if args.limit is not None:
        if args.limit <= 0:
            parser.error("--limit must be positive")
        ranks = ranks[:args.limit]
    env = dict(os.environ, QT_QPA_PLATFORM="xcb")
    server = None
    rows = []
    with tempfile.TemporaryDirectory(prefix="minirubik-rv32-") as temporary:
        temporary = Path(temporary)
        env["XDG_CONFIG_HOME"] = str(temporary / "config")
        try:
            if args.xvfb:
                server_env = dict(os.environ)
                if args.xvfb_library_dir:
                    server_env["LD_LIBRARY_PATH"] = args.xvfb_library_dir
                server = subprocess.Popen(
                    [args.xvfb, "-displayfd", "1", "-screen", "0", "640x480x24",
                     "-nolisten", "tcp", "-ac"], env=server_env,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                ready, _, _ = select.select([server.stdout], [], [], 10)
                if not ready:
                    raise RuntimeError("Xvfb did not initialize within ten seconds")
                display = server.stdout.readline().strip()
                if not display:
                    raise RuntimeError(server.stderr.read())
                env["DISPLAY"] = ":" + display

            def measure(rank):
                state = decode_state(rank)
                patched = bytearray(template)
                offset = input_section[4]
                patched[offset:offset + 14] = state
                image = temporary / f"rank_{rank}.elf"
                image.write_bytes(patched)
                command = [args.ripes, "--mode", "cli", "--src", str(image),
                           "-t", "elf", "--proc", "RV32_ISS", "--iret", "--regs",
                           "--json", "--runinfo", "--exectime", "--timeout", "30000"]
                result = subprocess.run(command, env=env, capture_output=True,
                                        text=True, timeout=45)
                if result.returncode or "Program exited with code: 0" not in result.stdout:
                    raise RuntimeError(f"rank {rank}: Ripes failed\n{result.stdout}\n{result.stderr}")
                report = json.loads(result.stdout[result.stdout.index("{"):])
                instructions = report["# instructions retired"]
                length = report["registers"]["x10"]
                runinfo = report["runinfo"]
                if length != 11 or runinfo["processor"] != "RV32_ISS" or runinfo["ISA extensions"]:
                    raise RuntimeError(f"rank {rank}: wrong result or processor configuration: {report}")
                row = {"rank": rank, "state": "".join(str(v + 1) for v in state),
                       "retired_instructions": instructions, "solution_length": length,
                       "execution_ms": report["execution time (ms)"]}
                image.unlink()
                return row

            with (output / "distance11.csv").open("w", newline="") as file:
                fields = ["rank", "state", "retired_instructions", "solution_length", "execution_ms"]
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                with ThreadPoolExecutor(max_workers=args.workers) as pool:
                    futures = [pool.submit(measure, rank) for rank in ranks]
                    for future in as_completed(futures):
                        row = future.result()
                        rows.append(row)
                        writer.writerow(row)
                        file.flush()
                        if len(rows) % 100 == 0 or len(rows) == len(ranks):
                            maximum = max(r["retired_instructions"] for r in rows)
                            print(f"measured {len(rows)}/{len(ranks)}; max instructions={maximum}", flush=True)
        finally:
            if server is not None:
                server.terminate()
                server.wait()

    worst = max(rows, key=lambda r: r["retired_instructions"])
    full = args.limit is None and len(rows) == 2644
    passed = full and worst["retired_instructions"] <= LIMIT
    summary = {
        "status": "FULL PASS" if passed else ("PARTIAL" if not full else "FAIL"),
        "ripes_version": args.ripes_version, "ripes_sha256": sha256(args.ripes),
        "compiler": subprocess.check_output([args.cc, "--version"], text=True).splitlines()[0],
        "flags": FLAGS, "renderer": "compiled out (MINIRUBIK_CORE_ONLY)",
        "processor": "RV32_ISS", "isa": "RV32I", "static_sections": static_sections,
        "static_bytes": static_bytes, "static_limit": 131072,
        "distance11_count": len(rows), "instruction_limit": LIMIT, "worst": worst,
        "elf_sha256": sha256(elf), "oracle_sha256": sha256(args.distances),
        "source_sha256": sha256(ROOT / "ida_solver.c"),
        "pdb_header_sha256": sha256(ROOT / "pdb_data.h"),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if passed or not full else 1


if __name__ == "__main__":
    raise SystemExit(main())
