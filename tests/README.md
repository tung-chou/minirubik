# Correctness tests

All test programs, Python checks, vectors, generated distance data, and gate
reports live in this directory. Build the C gates and generate the BFS oracle
from the repository root:

```sh
make -C tests all distances
```

The parent Makefile automatically generates the two packed PDBs needed by the
IDA* implementation. The gates compile the actual `ida_solver.c` with its CLI
entry point renamed. The exact-distance oracle is never passed to the search.

| Gate | Program | Checks |
| --- | --- | --- |
| H1 | `verify_h1.c` | The actual `heuristic()` satisfies `h(s) <= d(s)` for all 3,674,160 full states. |
| H2 | `verify_h2.c` | Both PDBs have the reference maximum and unique solved zero. Every entry and maximum of both transition tables, including their solved rows, matches an independent reference. The oracle's size, population, maximum, and solved entry are also checked. |
| H3 | `verify_h3.c` | IDA* returns a solving path whose length equals the exact BFS distance for every full state. |
| H4 | `verify_h4.c` | The actual packed accessor equals an independent unpacked BFS reference at every even and odd index of both PDBs. |

Run each gate separately:

```sh
make -C tests verify-h1
make -C tests verify-h2
make -C tests verify-h3
make -C tests verify-h4
```

Run all four gates, including the complete H3 search comparison:

```sh
make -C tests verify
```

The programs print counts and PASS/FAIL summaries. H1 reports heuristic
violations and the maximum heuristic. H2 reports population, actual and
expected maxima, solved rank/value, and zero-entry count for each PDB. H4
reports even and odd counts separately: 34,020 indices per parity per PDB,
136,080 comparisons in total. H2 and H4 build fresh unpacked reference PDBs
using independent corner cycles. They never unpack the production table to
create their reference and never call the offline generator's abstract moves.
For the current patterns, both reference maxima are 8; solved ranks are 0 for
A and 35,235 for B. Maximum expectations are derived from the reference BFS.

`generate_distances.c` calls `solver.c`'s actual `build_table()` and follows its
shortest-path moves, memoizing lengths. `exact_distances.bin` is exactly
3,674,160 bytes with no header: byte `rank` is the minimum number of HTM moves
to solve `unrank_state(rank)`. Values range from 0 to 11 and rank 0 is the unique
solved state. This file contains distances, not move sequences.

H1 and H3 certify the entire oracle before trusting it. For every unsolved
state, independent reference moves must satisfy
`d(s) = 1 + min(d(neighbor))`. Together with a unique zero at the solved state,
this proves the distances are exact: a decreasing path realizes the distance,
and an edge can decrease it by at most one. H3 also certifies every abstract
PDB entry against its goal and reference neighbors. H1 is specifically an
admissibility gate; it does not require consistency.

When invoked directly, H1, H2, H3, and the generator default to
`exact_distances.bin` in the current working directory. Supply a path when
running from the repository root:

```sh
./tests/generate_distances tests/exact_distances.bin
./tests/verify_h1 tests/exact_distances.bin
./tests/verify_h2 tests/exact_distances.bin
./tests/verify_h4
```

H3 supports contiguous rank ranges; the last argument is a count, not an end
rank:

```sh
./tests/verify_h3 tests/exact_distances.bin 0 100
./tests/verify_h3 tests/exact_distances.bin 100 100
```

Only coverage of `[0, 3674160)` prints `FULL PASS/FAIL`; smaller ranges print
`PARTIAL PASS/FAIL`. H3 reports progress to stderr every five seconds between
searches, a final per-distance count, and the first 20 failing states. Full
search comparison takes longer than the other gates. When aggregating ranges,
check that all exit successfully and that there are no gaps or overlaps.

To certify the oracle and abstract PDB entries without running IDA* searches:

```sh
make -C tests check-table
```

This runs H3's `--check-table` mode. `TABLE PASS` means that search paths and
heuristic admissibility have not been tested; use H1 for admissibility.

For routine tests:

```sh
make check              # Existing BFS/mini tests, CLI/PDB checks, gate checks
make check-ida          # Independent Python PDB BFS and IDA* CLI checks
make check-gates        # Full H1/H2/H4, H3 sample, invalid/corrupt file checks
```

`make check-gates` delegates to `make -C tests check`. It covers all H1 states,
all H2 entries, all H4 indices, and 17 H3 states including a depth-11 case.
It does not claim exhaustive H3 coverage. `check_pdb.py` compares every packed
PDB entry with a separate Python abstract BFS and checks deterministic offline
regeneration. `check_ida.py` checks all 385 concrete states through depth 3,
eight known optimal vectors in `solutions.txt`, invalid input, CLI formatting,
and output errors. Python checks require Python 3.

Exit status is 0 on success, 1 for a gate/I/O failure, and 2 for invalid
arguments. `gate_common.h` shares the actual solver, independent reference
moves, oracle loading/certification, and unpacked reference BFS. Gate binaries,
`exact_distances.bin`, and `ida_verification.txt` are ignored by Git.
`make -C tests clean` removes gate binaries and keeps generated distance data.

## RV32I efficiency and Ripes

`rv32_bench.c` compiles the actual solver with `MINIRUBIK_CORE_ONLY`, which
excludes the CLI, output formatting, and host self-tests. It copies a volatile
14-byte input and calls `solve`; the input is not a compile-time constant.
`rv32_start.S` initializes the stack, calls the benchmark, and exits through
Ripes' exit ecall. Register `a0` retains the solution length and `bench_path`
contains the moves. `rv32.ld` places code at `0x1000`; the stack starts at
`0x100000`. No renderer, libc, libgcc, heap, or host profiling counters is linked.

Compiler used for the checked artifact: GCC 13.2.0, Ubuntu package
`13.2.0-11ubuntu1+12`, targeting `-march=rv32i -mabi=ilp32 -O3`.
The complete flags are in `measure_rv32.py` and `rv32_report/bound.json`.
This deliberately uses no M extension. The linked code contains no
multiply/divide/remainder instructions or software arithmetic helpers.

```sh
make rv32-bound RV32_CC=riscv64-unknown-elf-gcc \
  RV32_OBJDUMP=riscv64-unknown-elf-objdump
```

This builds the RV32 ELF, counts every allocated non-code section, checks the
machine-code control flow, and collects search counts for all distance-11
states. Results are stored in `rv32_report/bound.json`, `search_counts.csv`,
and `ida_rv32.dis`; the generated ELF is ignored by Git.

| Static data | Bytes |
| --- | ---: |
| Two packed PDBs | 68,040 |
| Shared permutation / twist-delta transitions | 10,080 |
| Shared orientation addition | 6,561 |
| `.rodata` alignment | 3 |
| Input (`.data`) | 14 |
| Solution path (`.bss`) | 11 |
| Total | **84,709 / 131,072** |

Relative to the original concrete-state search, each candidate avoids seven
corner permutation writes, seven corner orientation writes and modulo-three
calculations, a seven-entry inverse-position map, two four-corner projections,
and two partial-rank calculations. The new candidate uses six table loads:
two 32-bit permutation/delta loads, two byte orientation loads, and two packed
distance byte loads. Permutation/orientation extraction and `p * 81` use
shifts, masks, and additions. Search arguments carry two coordinates in RV32
scalar variables. A fixed local array stores ten 16-byte ancestor records;
it uses no heap and no recursion. Each accepted non-goal child saves four
words; rejected candidates do not update the ancestor stack. On success, the
saved face/turn cursors reconstruct the path with eleven output writes.
The checked compiler inlines search into `bench_run`, which has one fixed
240-byte machine stack frame including the array, locals, and saved registers.

The exhaustive distance-11 profile counts **37,133,776 visits** and
**6,194,842 expanded nodes**. Counts match the preceding recursive implementation
for every one of the 2,644 inputs. The iterative implementation replaces
recursive calls with explicit descent/backtracking. Search order, PDB distances,
and the number of logical candidates stay the same.

The instruction bound uses the linked machine code, not host timing. Let
`V` be logical visits and `E` expanded nodes. `check_rv32.py` cuts the eight
cyclic backward edges in `bench_run` and checks that the remaining graph is
acyclic. It computes longest acyclic paths rather than charging the entire
function's static size for each iteration. The initial path, including
`_start`, costs at most 398 instructions. Each segment entered through a cut
edge costs at most 194 instructions, including eventual path output and exit.

Let `C` be child candidates and `R` root iterations, so `V = C + R`.
Candidate processing takes at most `C` cut edges (a rejected candidate or an
accepted non-goal descent). Face completion takes at most `3E`, face skipping
at most `E`, backtracking at most `E`, and threshold advancement at most `R`.
The total cut-edge count is therefore at most `V + 5E`, giving the bound
`398 + 194 * (V + 5E)`. The script rejects search calls, unexpected functions,
changed loop counts, or residual cycles; a changed compiler layout requires
reviewing this accounting. Only `_start` calls `bench_run`, so the checked
RV32 program contains neither recursive calls nor heap allocation calls.

The maximum bound over all 2,644 inputs is **28,942,094 instructions**:
rank `1137240`, `V = 81374`, `E = 13562`. This is below the 50,000,000 limit.
The bound report includes hashes of the source, PDB header, oracle, and ELF.
`BOUND PASS` is an analytical result, not a Ripes retired-instruction report.

The pinned Ripes build is **v2.2.6-106-g5b8a616**, commit `5b8a616`, from
`/home/unijoy/ripes/Ripes-v2.2.6-106-g5b8a616-linux-x86_64.AppImage`.
`ripes_pin.json` records SHA-256 hashes of that AppImage and its extracted
executable. Extract it with `--appimage-extract` in a temporary directory and
pass `squashfs-root/AppRun` (or the identical `usr/bin/Ripes`) to the runner.
The runner verifies the executable hash before executing it.

```sh
make measure-rv32 RV32_CC=riscv64-unknown-elf-gcc \
  RIPES=/path/to/squashfs-root/AppRun
```

Each run uses `--mode cli --proc RV32_ISS --iret --regs --json --runinfo`,
with an RV32I ELF and no ISA extensions. The runner patches only the input
bytes in the same ELF for each oracle-certified distance-11 state, checks
termination and solution length, and records retired instructions in
`rv32_report/distance11.csv`. `summary.json` reports `FULL PASS` only after
all 2,644 measurements finish and their maximum is within the limit.
For a partial smoke run, add `RIPES_ARGS='--limit 1'`; this reports `PARTIAL`.

Ripes initializes Qt even in CLI mode. On a headless host, the runner accepts
`--xvfb /path/to/Xvfb` and optionally `--xvfb-library-dir /path/to/libraries`
through `RIPES_ARGS`. Full Ripes execution was not authorized in this session,
so no complete measured `summary.json` is supplied. The static-data check,
full H1/H2/H3/H4 gates, and exhaustive analytical bound have been completed.
