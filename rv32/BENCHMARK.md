# Measured RV32I comparison — 2026-10-08

**FULL PASS:** all 2,644 distance-11 states and sixteen representative inputs,
2,660 cases across four variants, **10,640 measured Ripes executions**. Every
variant returns the expected optimal length and identical path, independently
replays to solved, preserves saved registers and restores the machine stack.
The rank set was audited against the complete certified BFS oracle.

Measurements use pinned Ripes `v2.2.6-106-g5b8a616`, `RV32_ISS`, no ISA
extensions, and GCC 13.2.0. Every linked instruction is checked as RV32I;
all 84,681 table bytes are verified identical to Stage 3. The benchmark calls
the actual Stage 3 C solver and handwritten assembly through one common
`compare_start.S`. Input is normalized, fourteen bytes. Counts include the
common startup, ABI checks, result packing and exit; they exclude text parsing,
program output and rendering. No libc, libgcc, heap or profiling counters are
linked. Host execution time is diagnostic and is not used for the improvement.

## GCC -O2 versus optimized assembly

| Metric | GCC -O2 | Assembly | C minus assembly | Improvement |
| --- | ---: | ---: | ---: | ---: |
| Solved state | 371 | 326 | 45 | 12.13% |
| One-move `25314672313211` | 641 | 602 | 39 | 6.08% |
| Required hard case `21345671111111` | 4,375,238 | 3,787,108 | 588,130 | 13.44% |
| Maximum over all hard states | 7,762,682 | 6,729,300 | 1,033,382 | 13.31% |
| Total over all hard states | 3,537,903,354 | 3,069,039,820 | 468,863,534 | **13.25%** |
| Linked `.text`, common harness included | 1,612 bytes | 1,664 bytes | -52 bytes | -3.23% |
| Static data | 84,717 bytes | 84,706 bytes | 11 bytes | 0.013% |
| Solver machine stack | 224 bytes | 272 bytes | -48 bytes | -21.43% |

The two maxima occur at different inputs. C's worst case is rank 1,137,240,
`32145671111111`; assembly's is rank 3,645, `12347651111111`. At the C worst
input, assembly executes 6,722,019 instructions. The maximum-row improvement
compares maxima, while the aggregate improvement uses the same full input set:
`100 * (sum(C) - sum(assembly)) / sum(C)`.

The assembly maximum is **6,729,300 / 50,000,000** (13.46% of the instruction
budget). Its static data is **84,706 / 131,072 bytes**. Both variants satisfy
the supplied limits. The official handout remains unavailable for confirmation.
Assembly uses more code and stack despite its instruction reduction.

Static section breakdown is:

| Section | GCC -O2 | Assembly |
| --- | ---: | ---: |
| `.rodata` | 84,692 | 84,681 |
| `.data` | 14 | 14 |
| `.bss` | 11 | 11 |

C's extra eleven read-only bytes are its eight cubie-identity constants and
three bytes of alignment. The common harness also touches a four-byte guard
2,048 bytes below the initial `sp`; provide that mapped stack region. Solver
frame sizes above exclude this test guard. The text/CLI wrapper instead uses
up to 304 stack bytes and has 84,792 bytes of static data with solution output.

## Incremental optimization results

| Variant | Hard-state instruction total | Saved vs prior assembly variant | `.text` | Replay / optimality / ABI |
| --- | ---: | ---: | ---: | --- |
| `asm_baseline` | 3,254,943,926 | — | 1,640 bytes | PASS |
| `asm_leaf` | 3,254,914,982 | 28,944 (0.000889%) | 1,632 bytes | PASS |
| `asm_cached` | 3,069,039,820 | 185,875,162 (5.71%) | 1,664 bytes | PASS |

The baseline already uses 8.00% fewer instructions than GCC -O2 in aggregate.
Removing leaf `ra` save/restore saves two instructions per threshold search,
with negligible aggregate benefit. Caching the face row removes eight address
instructions from candidates; pointer updates occur on face changes, descent,
and backtracking. It saves 5.71% relative to the leaf variant, at a cost of
32 additional code bytes. Both switches are enabled in the default solver;
all three versions remain separately buildable. The 240-byte search-frame
layout remains fixed for these experiments, including the unused `ra` slot.

A C copy wrapper that introduced `memcpy` was rejected in favor of exporting
the real aggregate-argument solver. The initial exit harness produced an ISS
stack-register anomaly matching the adjacent C prologue. A harmless self-loop
after exit fixes it; all four binaries use that same guard. These corrections
are not counted as optimization gains. No unsuccessful search optimization
is claimed. Full diagnostic details are in `WORK_LOG.md`.

## Evidence and reproduction

Complete actual paths/counts are in
[`validation/comparison_full/comparison.csv`](validation/comparison_full/comparison.csv).
[`summary.json`](validation/comparison_full/summary.json) records full flags,
source/ELF/oracle/Ripes hashes, commands, totals and worst cases. Disassemblies
are archived alongside it. Limited runs always label their result `PARTIAL PASS`.

```sh
python3 rv32/compare.py \
  --cc /tmp/minirubik-toolchain/usr/bin/riscv64-unknown-elf-gcc \
  --objdump /tmp/minirubik-toolchain/usr/bin/riscv64-unknown-elf-objdump \
  --ripes /tmp/minirubik-ripes/squashfs-root/AppRun \
  --xvfb /tmp/minirubik-ripes/Xvfb \
  --xvfb-library-dir /tmp/minirubik-toolchain/usr/lib/x86_64-linux-gnu
```

The extracted `/tmp` tools may need replacement on another machine. Omit Xvfb
arguments with an available display. Clean the build directory when changing
compiler or flags. `make compare-asm` is the make entry; see `README.md`.
The Ripes command for every ELF includes `--mode cli -t elf --proc RV32_ISS
--iret --regs --json --runinfo --exectime --timeout 60000`; no ISA extension
option is passed. Program output is empty except Ripes' exit-status message.

The RV32_5S representative comparison also passed eighteen inputs / 72 runs,
including the required hard input, with evidence in
[`validation/comparison_5S/summary.json`](validation/comparison_5S/summary.json).
Its retired counts are one below ISS's corresponding values at exit; processor
models are reported separately. GUI pipeline signals/screenshots and the LED
renderer remain `TBD`. Complete assembly H1/H3 over all 3,674,160 concrete
states is additional coverage beyond the exhaustive hard-case set.
