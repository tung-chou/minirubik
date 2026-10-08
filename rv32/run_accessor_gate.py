"""Run the complete target abstract-coordinate accessor gate on pinned Ripes."""
import argparse
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile
import time

from check_asm import ROOT, sha
from inspect_elf import rv32i
from measure_rv32 import elf_sections
import struct

FLAGS = ["-O2", "-std=c99", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
         "-march=rv32i", "-mabi=ilp32", "-mno-relax", "-msmall-data-limit=0",
         "-ffreestanding", "-fno-builtin", "-fno-pie", "-fno-stack-protector",
         "-ffunction-sections", "-fdata-sections", "-nostdlib", "-Wl,--gc-sections",
         "-Wl,--no-relax"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ripes", required=True)
    parser.add_argument("--cc", default="riscv64-unknown-elf-gcc")
    parser.add_argument("--xvfb")
    parser.add_argument("--xvfb-library-dir")
    parser.add_argument("--elf", type=Path, default=ROOT / "rv32/build/accessor_gate.elf")
    parser.add_argument("--output", type=Path, default=ROOT / "rv32/results/accessor_gate.json")
    args = parser.parse_args()
    pin = json.loads((ROOT / "tests/ripes_pin.json").read_text())
    if sha(args.ripes) != pin["binary_sha256"]:
        raise RuntimeError("Ripes executable differs from pinned version")
    args.output.unlink(missing_ok=True)
    subprocess.run(["make", "-C", str(ROOT / "rv32"), "build/tables.S"], check=True)
    args.elf.parent.mkdir(parents=True, exist_ok=True)
    command = [args.cc, *FLAGS, "-Wl,-T," + str(ROOT / "tests/rv32.ld"),
               str(ROOT / "rv32/accessor_gate.c"), str(ROOT / "rv32/accessor_start.S"),
               str(ROOT / "rv32/solver.S"), str(ROOT / "rv32/build/tables.S"), "-o", str(args.elf)]
    subprocess.run(command, check=True)
    data = args.elf.read_bytes()
    sections = elf_sections(data)
    text = sections[".text"]
    for offset in range(0, text[5], 4):
        if not rv32i(struct.unpack_from("<I", data, text[4] + offset)[0]):
            raise AssertionError("accessor gate contains a non-RV32I instruction")
    static = {n: s[5] for n, s in sections.items() if s[2] & 2 and not s[2] & 4}
    if sum(static.values()) > 131072:
        raise AssertionError("accessor gate exceeds static-data limit")
    env = dict(os.environ, QT_QPA_PLATFORM="xcb")
    server = None
    with tempfile.TemporaryDirectory(prefix="minirubik-accessors-") as directory:
        env["XDG_CONFIG_HOME"] = str(Path(directory) / "config")
        try:
            if args.xvfb:
                xenv = dict(os.environ)
                if args.xvfb_library_dir:
                    xenv["LD_LIBRARY_PATH"] = args.xvfb_library_dir
                display = next(str(n) for n in random.sample(range(100, 10000), 100)
                               if not Path(f"/tmp/.X{n}-lock").exists())
                server = subprocess.Popen([args.xvfb, ":" + display, "-screen", "0", "640x480x24",
                                           "-nolisten", "tcp", "-ac"], env=xenv,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                time.sleep(0.5)
                if server.poll() is not None:
                    raise RuntimeError(server.stderr.read())
                env["DISPLAY"] = ":" + display
            result = subprocess.run([args.ripes, "--mode", "cli", "--src", str(args.elf), "-t", "elf",
                                     "--proc", "RV32_ISS", "--iret", "--regs", "--json", "--runinfo",
                                     "--timeout", "60000", "--output", str(Path(directory) / "report.json")],
                                    env=env, capture_output=True, text=True, timeout=75)
            if result.returncode or result.stdout.strip() != "Program exited with code: 0":
                raise RuntimeError((result.returncode, result.stdout, result.stderr))
            report = json.loads((Path(directory) / "report.json").read_text())
        finally:
            if server is not None:
                server.terminate()
                server.wait(timeout=10)
    regs = report["registers"]
    passed = regs["x10"] == 0 and regs["x11"] == 136080 and regs["x12"] == 204120
    if report["runinfo"]["processor"] != "RV32_ISS" or report["runinfo"]["ISA extensions"]:
        raise AssertionError(report["runinfo"])
    report["gate"] = dict(status="PASS" if passed else "FAIL", distance_checks=regs["x11"],
                          transition_checks=regs["x12"], return_status=regs["x10"],
                          failed_coordinate=regs["x13"], failed_selector=regs["x14"],
                          actual=regs["x15"], expected=regs["x16"],
                          elf_sha256=sha(args.elf), ripes_sha256=sha(args.ripes),
                          assembly_sha256=sha(ROOT / "rv32/solver.S"),
                          gate_source_sha256=sha(ROOT / "rv32/accessor_gate.c"),
                          compile_command=command, text_bytes=text[5], static_sections=static,
                          static_bytes=sum(static.values()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["gate"], indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
