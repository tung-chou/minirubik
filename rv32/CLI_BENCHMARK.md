# Historical full-program CLI benchmark before target replay — 2026-10-08

This records the executable before in-program verification was added. Its
archived counts and hashes are retained unchanged. Current verified CLI and
T7 results are documented in [VERIFIED_CLI.md](VERIFIED_CLI.md). Reproducing
these historical counts requires the original sources identified in the
archived summary; running the commands below on current sources measures
the new executable instead.

**PASS:** the final optimized handwritten RV32I text-entry executable was
run on all **2,644 distance-11 states**. Every execution terminated normally,
returned an optimal eleven-move path, and passed independent concrete replay.
**Zero states exceed 50,000,000 retired instructions.** No further solver
optimization was made, and the existing GCC -O2 comparison was left unchanged.

| Metric | Final full-program CLI |
| --- | ---: |
| Tested distance-11 states | 2,644 / 2,644 |
| Optimal length / independent replay | All PASS |
| Maximum retired instructions | **6,729,751** |
| Maximum input | `12347651111111`, rank 3,645 |
| States exceeding 50,000,000 | **0** |
| Minimum over the hard set | 524,048 |
| Required vector `21345671111111` | **3,787,559** |
| Required vector solution length | 11 |
| Static `.rodata + .data + .bss` | **84,792 / 131,072 bytes** |
| Linked `.text` | 1,836 bytes |

The required vector returns `R B' D2 R' B R' B' R D2 R B`.
The worst-case count is 13.46% of the instruction budget. The static sections
are `.rodata = 84,749`, `.data = 32`, and `.bss = 11` bytes.

## Measurement boundary

The measured ELF is `rv32/build/solver.elf`, built from `solver.S`, `start.S`,
and generated `tables.S` with both existing optimization flags
`ASM_REMOVE_LEAF_RA` and `ASM_CACHE_FACE_ROW`, plus `ASM_PRINT`. There is no
LED renderer in these link inputs. This is the final optimized implementation,
not the original Phase 1 baseline.

Counts include startup, parsing the inlined fourteen-character string, state
validation, coordinate projection, all IDA* searches, path generation, solution
printing, and normal exit. Host replay and the host C reference check happen
after target execution and contribute no target instructions.

Every run uses pinned Ripes **`v2.2.6-106-g5b8a616`**, **`RV32_ISS`**, **no ISA
extensions**, and `--iret --regs --json --runinfo --timeout 60000`. The runner
patches only the input slot in one ELF template; executable code and tables
remain identical for every state. The complete rank/state set was audited
against the certified BFS oracle and the previous full core comparison.

The prior normalized-input core numbers remain **6,729,300** for its maximum
and **3,787,108** for the required vector. That harness excludes parsing and
printing and includes ABI probes/result packing. Those are a separate compiler
comparison in [BENCHMARK.md](BENCHMARK.md), not this full-program grading result.

## Evidence and reproduction

- [counts.csv](validation/final_cli_distance11/counts.csv): every rank, input,
  expected/actual length, printed path, PASS status, and actual retired count.
- [summary.json](validation/final_cli_distance11/summary.json): coverage,
  maximum, required-vector count, over-budget count, measurement boundary,
  source/ELF/oracle/Ripes hashes, and the actual run command.
- [build.json](validation/final_cli_distance11/build.json): compiler version,
  build command, optimization/ISA flags, link inputs, and ELF inspection.

The final ELF SHA-256 is
`8cea7dce2b3104814181235a1492faee9543783f1e872b7591d7128186c9ed28`;
it matches the previously archived optimized CLI. Every linked instruction was
inspected as RV32I and all 84,681 exported table bytes were checked against
the host arrays and binary PDBs. Existing solver sources, compiler-comparison
scripts, `BENCHMARK.md`, and both core comparison archives remained unchanged.

From the repository root, with native `cc`, Python 3, and the recorded tools:

```sh
make pdb ida_solver
make -C tests distances
make -C rv32 -B build/solver.elf \
  RV32_CC=/tmp/minirubik-toolchain/usr/bin/riscv64-unknown-elf-gcc
python3 rv32/check_asm.py --distance11-only \
  --elf rv32/build/solver.elf --proc RV32_ISS --workers 4 \
  --ripes /tmp/minirubik-ripes/squashfs-root/AppRun \
  --xvfb /tmp/minirubik-ripes/Xvfb \
  --xvfb-library-dir /tmp/minirubik-toolchain/usr/lib/x86_64-linux-gnu \
  --output rv32/results/final_cli_distance11
```

Replace temporary tool paths on another machine; the measured compiler is
GCC 13.2.0. Omit Xvfb arguments if a display is available. Fresh output is
ignored under `results/`, named `correctness_RV32_ISS.csv` and
`correctness_RV32_ISS.json`; the curated copies above are named `counts.csv`
and `summary.json`. `--distance11-only` selects exactly the full hard set and
reports failure if any count exceeds the budget. It does not run or rebuild
the GCC comparison.
