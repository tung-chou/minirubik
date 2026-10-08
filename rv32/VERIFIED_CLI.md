# Verified text-entry CLI — mandatory correctness and grading

**PASS:** the final handwritten RV32I text-entry solver now verifies its own
solution, passes the three T7 cases on both pinned processor models, and stays
within the retired-instruction limit for all 2,644 distance-11 states. No new
search optimization or GCC comparison change was made.

## In-program verification

`asm_solve_text` retains the original parsed cube. After `asm_solve` returns,
`asm_verify_solution` copies that cube into a fixed 32-byte frame, applies every
returned move, then checks permutation bytes `0..6` and seven zero twists.
Replay uses a separate 42-byte concrete source/twist table; it does not use
PDBs, abstract transitions or the search heuristic. Length must be `0..11`,
and every move ID must be `0..8`. The original cube and path remain unchanged.

Only a verified solution returns a nonnegative length. Failed replay returns
`-3` and the CLI prints `solution verification failed`, rather than a solution.
Invalid input remains `-2`, search failure `-1`. Register `a4` is `1` after
verified success and `0` on rejection. Host tests check this status and retain
their independent corner-cycle replay, optimal-length assertion and C path check.

Replay runs after search returns, so its frame does not increase the existing
304-byte maximum call stack. There is no heap, recursion, floating point or
non-RV32I instruction. All 84,681 shared table bytes pass ELF inspection.

## Actual T7 results

The **same final fourteen-character CLI ELF** was used on both models, with
no ISA extensions and Ripes `v2.2.6-106-g5b8a616`:

| Input | Length | Actual solution | ISS retired | RV32_5S retired | Target / host replay |
| --- | ---: | --- | ---: | ---: | --- |
| `12345671111111` | 0 | Empty | 631 | 630 | PASS / PASS |
| `25314672313211` | 1 | `R'` | 1,503 | 1,502 | PASS / PASS |
| `21345671111111` | 11 | `R B' D2 R' B R' B' R D2 R B` | 3,791,721 | 3,791,720 | PASS / PASS |

Each model also passed a test-only thirteen-case verifier gate: correct paths,
incorrect paths, invalid move IDs, invalid lengths and original-state
preservation. The existing ISS shallow/vector/invalid-input suite passed
**404/404**, including 392 verified solutions and twelve rejected inputs.
CLI execution on RV32_5S establishes T7 model execution; GUI pipeline signal
observations and screenshots remain separate pending work.

## Complete CLI grading measurements

| Metric | Result |
| --- | ---: |
| Distance-11 coverage | **2,644 / 2,644** |
| Optimal eleven-move solution, target and independent host replay | All PASS |
| Maximum retired instructions | **6,733,921** |
| Maximum input / rank | `12347651111111` / 3,645 |
| States above 50,000,000 | **0** |
| Required vector `21345671111111` | **3,791,721** |
| Minimum over the hard set | 527,676 |
| `.rodata + .data + .bss` | **84,868 / 131,072 bytes** |
| Linked output CLI `.text` | 2,176 bytes |

Counts are actual pinned `RV32_ISS --iret` results and include startup, string
parsing, validation, search, path generation, **in-program concrete replay**,
printing and normal exit. No LED renderer is linked. The maximum is 13.47%
of the 50,000,000 budget. The complete rank/state set matches the certified BFS
oracle and the prior core comparison, not a sampled hard-state subset.

Static sections are `.rodata = 84,825`, `.data = 32`, `.bss = 11` bytes.
The silent text-entry ELF has 84,768 static bytes and 2,012 text bytes.
The final output ELF SHA-256 is
`c05bf167c2b0006a501e085ca39e246256b68b23ed11815f467538c8bc1913ad`.

The original normalized-input GCC comparison is preserved in
[BENCHMARK.md](BENCHMARK.md). A rebuilt optimized normalized assembly ELF is
byte-identical to its archived `asm_cached` binary: replay code/data are removed
by section collection. Its `.text` remains 1,664 versus GCC's 1,612 bytes,
52 bytes larger, while aggregate hard-state retired instructions are 13.25%
lower. This code-size trade-off remains deliberately unoptimized. Those core
counts exclude the text wrapper and verification, and are not the complete CLI
grading counts above. The earlier pre-verification CLI campaign is retained in
[CLI_BENCHMARK.md](CLI_BENCHMARK.md) with its original evidence unchanged.

## Evidence and reproduction

- [Full CLI counts](validation/verified_cli_distance11/counts.csv) and
  [summary](validation/verified_cli_distance11/summary.json): all 2,644 paths,
  lengths, target status, actual counts, coverage, source/ELF/oracle/Ripes hashes.
- [Build metadata](validation/verified_cli_distance11/build.json): exact flags,
  compiler, linked inputs, inspection and unchanged-core proof.
- [T7 ISS records](validation/verified_t7/correctness_RV32_ISS.csv) and
  [RV32_5S records](validation/verified_t7/correctness_RV32_5S.csv); companion
  JSON includes commands and actual thirteen-case verifier-gate reports.
- [Regression summary](validation/verified_cli_shallow/correctness_RV32_ISS.json).

From the repository root (replace tool paths on another machine):

```sh
make pdb ida_solver
make -C tests distances
make -C rv32 all \
  RV32_CC=/tmp/minirubik-toolchain/usr/bin/riscv64-unknown-elf-gcc
/tmp/minirubik-toolchain/usr/bin/riscv64-unknown-elf-gcc \
  -march=rv32i -mabi=ilp32 -mno-relax -msmall-data-limit=0 -nostdlib \
  -Wl,--no-relax -Wl,--gc-sections -Wl,-T,tests/rv32.ld \
  rv32/verification_gate.S rv32/solver.S rv32/build/tables.S \
  -o rv32/build/verification_gate.elf
python3 rv32/check_asm.py --representative --require-verification \
  --verifier-gate rv32/build/verification_gate.elf --proc RV32_ISS \
  --ripes /tmp/minirubik-ripes/squashfs-root/AppRun \
  --xvfb /tmp/minirubik-ripes/Xvfb \
  --xvfb-library-dir /tmp/minirubik-toolchain/usr/lib/x86_64-linux-gnu \
  --output rv32/results/verified_t7
python3 rv32/check_asm.py --representative --require-verification \
  --verifier-gate rv32/build/verification_gate.elf --proc RV32_5S \
  --ripes /tmp/minirubik-ripes/squashfs-root/AppRun \
  --xvfb /tmp/minirubik-ripes/Xvfb \
  --xvfb-library-dir /tmp/minirubik-toolchain/usr/lib/x86_64-linux-gnu \
  --output rv32/results/verified_t7
python3 rv32/check_asm.py --distance11-only --require-verification \
  --elf rv32/build/solver.elf --proc RV32_ISS --workers 4 \
  --ripes /tmp/minirubik-ripes/squashfs-root/AppRun \
  --xvfb /tmp/minirubik-ripes/Xvfb \
  --xvfb-library-dir /tmp/minirubik-toolchain/usr/lib/x86_64-linux-gnu \
  --output rv32/results/verified_cli_distance11
```

Omit Xvfb arguments with an available display. For the existing regression
suite, replace `--distance11-only` with `--shallow` and use a separate output
directory. Original case selectors, build/benchmark flags, comparison scripts
and all previous evidence are preserved; the new test selectors are optional.
The verifier gate is test-only and is not linked into the grading executable.
