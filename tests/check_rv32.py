"""Check RV32I static data and a conservative instruction bound, without Ripes.

The bound is separate from retired-instruction measurements. See README.md
for the loop accounting and the compiler control-flow assumptions checked here.
"""

import argparse
import csv
import json
from pathlib import Path
import re
import subprocess

from measure_rv32 import FLAGS, HERE, ROOT, build_benchmark, elf_sections, sha256


def functions(disassembly):
    result = {}
    current = None
    for line in disassembly.splitlines():
        symbol = re.match(r"^([0-9a-f]+) <([^>]+)>:", line)
        if symbol:
            current = result.setdefault(symbol[2], [])
        insn = re.match(r"\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+(\S+)\s*(.*)", line)
        if insn and current is not None:
            current.append((int(insn[1], 16), insn[3], insn[4]))
    return result


def check_flow(instructions, expected_loops, callee=None):
    """Cut cyclic backward edges and bound the remaining acyclic segments."""
    conditional = {"beq", "bne", "blt", "bge", "bltu", "bgeu",
                   "beqz", "bnez", "bltz", "bgez", "blez", "bgtz",
                   "bgt", "ble", "bgtu", "bleu"}
    graph = {}
    for i, (address, op, args) in enumerate(instructions):
        targets = []
        if op in conditional or op == "j":
            target = int(re.search(r"([0-9a-f]+) <", args)[1], 16)
            targets.append(target)
        if op not in {"j", "ret", "ecall"} and i + 1 < len(instructions):
            targets.append(instructions[i + 1][0])
        if op in {"jal", "jalr"}:
            if callee is None or f"<{callee}>" not in args:
                raise RuntimeError(f"unexpected call at {address:x}: {args}")
        graph[address] = targets

    def reaches(start, end):
        pending, seen = [start], set()
        while pending:
            node = pending.pop()
            if node == end:
                return True
            if node not in seen:
                seen.add(node)
                pending.extend(graph[node])
        return False

    cuts = [(node, target) for node, targets in graph.items() for target in targets
            if target <= node and reaches(target, node)]
    for node, target in cuts:
        graph[node].remove(target)
    if len(cuts) != expected_loops:
        raise RuntimeError("compiler changed loop layout; review the bound accounting")
    active, done = set(), set()

    def visit(node):
        if node in active:
            raise RuntimeError("unaccounted cycle in generated machine code")
        if node in done:
            return
        active.add(node)
        for target in graph[node]:
            visit(target)
        active.remove(node)
        done.add(node)

    for node in graph:
        visit(node)
    longest = {}

    def length(node):
        if node not in longest:
            longest[node] = 1 + max((length(target) for target in graph[node]), default=0)
        return longest[node]

    return {
        "cuts": [[hex(a), hex(b)] for a, b in cuts],
        "initial_segment": length(instructions[0][0]),
        "repeated_segment": max((length(target) for _, target in cuts), default=0),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="riscv64-unknown-elf-gcc")
    parser.add_argument("--objdump", default="riscv64-unknown-elf-objdump")
    parser.add_argument("--output", type=Path, default=HERE / "rv32_report")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    elf = output / "ida_rv32.elf"
    build_benchmark(args.cc, elf)
    sections = elf_sections(elf.read_bytes())
    static_sections = {name: s[5] for name, s in sections.items()
                       if s[2] & 2 and not s[2] & 4}
    disassembly = subprocess.check_output([args.objdump, "-d", str(elf)], text=True)
    (output / "ida_rv32.dis").write_text(disassembly)
    code = functions(disassembly)
    if set(code) != {"_start", "bench_run"}:
        raise RuntimeError("unexpected functions; review the instruction bound")
    if any(re.match(r"^(mul|div|rem)", op)
           for instructions in code.values() for _, op, _ in instructions):
        raise RuntimeError("expensive arithmetic in RV32 search")
    # The checked compiler inlines iterative ida_search into bench_run.
    # Eight cyclic backward edges cover threshold changes, candidates,
    # face completion/skipping, and backtracking; there are no search calls.
    traversal = check_flow(code["bench_run"], 8)
    startup = check_flow(code["_start"], 0, "bench_run")
    counts = output / "search_counts.csv"
    subprocess.run([str(HERE / "profile_search"), str(HERE / "exact_distances.bin"),
                    str(counts)], check=True)
    with counts.open() as file:
        rows = [{key: int(value) for key, value in row.items()}
                for row in csv.DictReader(file)]
    if len(rows) != 2644:
        raise RuntimeError("incomplete distance-11 coverage")
    initial = traversal["initial_segment"] + startup["initial_segment"]
    repeated = traversal["repeated_segment"]
    for row in rows:
        row["instruction_upper_bound"] = (
            initial + repeated * (row["visits"] + 5 * row["expansions"]))
    worst = max(rows, key=lambda row: row["instruction_upper_bound"])
    passed = sum(static_sections.values()) <= 131072 and worst["instruction_upper_bound"] <= 50_000_000
    report = {
        "status": "BOUND PASS" if passed else "FAIL",
        "ripes_measurement": False,
        "compiler": subprocess.check_output([args.cc, "--version"], text=True).splitlines()[0],
        "flags": FLAGS, "static_sections": static_sections,
        "static_bytes": sum(static_sections.values()),
        "static_limit": 131072, "instruction_limit": 50_000_000,
        "distance11_count": len(rows),
        "visits": sum(row["visits"] for row in rows),
        "expansions": sum(row["expansions"] for row in rows),
        "recursion": False, "heap": False,
        "initial_segment_instructions": initial,
        "repeated_segment_instructions": repeated,
        "traversal_loop_cuts": traversal["cuts"],
        "formula": "initial_segment_instructions + repeated_segment_instructions * (visits + 5 * expansions)",
        "worst": worst, "elf_sha256": sha256(elf),
        "oracle_sha256": sha256(HERE / "exact_distances.bin"),
        "source_sha256": sha256(ROOT / "ida_solver.c"),
        "pdb_header_sha256": sha256(ROOT / "pdb_data.h"),
    }
    (output / "bound.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
