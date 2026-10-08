# Stage 4: handwritten RV32I

The Phase 0/1 baseline and full assembly distance-11 validation are complete.
The original `solver.c` (BFS), `mini.c`,
and final Stage 3 `ida_solver.c` are preserved. No target C, libc, libgcc,
heap, recursion, or M/C extensions are used by these two solver executables.

## Inspection and implementation decisions

The final reference is `ida_solver.c`, rather than `solver.c` or the old
`IDDFS_solver` executable. It projects the concrete cube once into two
four-corner coordinates, searches with `max(PDB_A, PDB_B)`, and carries
coordinates through shared table transitions. Its explicit ancestor records
replace recursion. The repository's existing `tests/ida_verification.txt`
records exhaustive C H1–H4 validation; those gates were also rerun for this
baseline. They certify the C reference, not the assembly search.

Patterns track cubie identities `{0,1,2,3}` and `{3,4,5,6}`. Each abstraction
has `P(7,4)*3^4 = 68,040` entries. A coordinate is
`permutation | (orientation << 10)`; the packed distance index is
`permutation*81 + orientation`. Even indices occupy the low nibble.
Both exact abstract distances are admissible, and their maximum is admissible.
Their goals together identify every movable cubie, so `h == 0` identifies
the concrete solved state. IDA* starts at the initial heuristic, advances to
the smallest exceeded threshold, suppresses consecutive same-face moves,
and considers R, B, D with one, two, and three quarter turns in that order.
Half turns still cost one HTM move. Thus the C optimality argument is retained.

No separate official assignment document was found in this checkout or the
surrounding architecture workspace. The 128 KiB static-data limit, 50,000,000
retired-instruction limit, RV32I target, and 35×25 display requirement are
currently taken from the supplied task and repository optimization notes.
There is no discovered discrepancy; checking the official handout remains open.

### Target and host boundaries

| Stage 3 function | Stage 4 treatment |
| --- | --- |
| `parse_state`, `valid` | Combined as handwritten `asm_parse_state`; sequential length/digit checks, duplicate bit mask, bounded twist-sum subtraction |
| `search_coordinates`, `pdb_rank_parts` | `asm_coordinates` and internal `asm_rank4`; one inverse map and unrolled ranking |
| `turn_coordinate`, `coordinate_distance` | Handwritten leaf accessors and inline RV32I macros in the hot search |
| `ida_search` | `asm_search`, fixed explicit ancestors, same traversal and threshold result |
| `solve` | `asm_solve`, normalized-state API; `asm_solve_text` adds input validation and concrete solution replay |
| CLI output | Ripes ecalls and a small handwritten character emitter in `start.S` |
| Concrete solution replay | Handwritten `asm_verify_solution`, independent of abstract transitions and PDBs |
| `self_test`, full ranking/unranking | Host correctness utilities; not linked into the target |
| PDB BFS and transition construction | Existing host `generate_pdb.c`; unchanged |
| Table serialization | New host-only `export_tables.c`, reading the existing generated C arrays |
| `output_failed`, hosted `argc/argv` handling | Hosted C utilities only; Ripes ecalls have different I/O/exit semantics |

The entry reads a NUL-terminated string from `asm_input`; its default is an
ordinary test input, not a special case in the search. Edit or patch this
32-byte slot to provide any valid 14-digit cube code. Malformed input returns
`a0 = -2`; search failure returns `-1`; failed solution replay returns `-3`.
Success returns a verified length `0..11` and writes move IDs `0..8` to
`asm_path`. `asm_solve_text(text, path)` exposes the
same behavior for another caller. Its input pointer must address a readable
NUL-terminated string and its output pointer must address eleven writable bytes.
`asm_solve(state, path)` instead accepts a previously validated 14-byte state
with zero-based cubies/twists, matching the existing C core benchmark boundary.

The text wrapper retains the original parsed cube and replays the returned
path on a copy. Every final permutation byte must equal its position, and
every twist must be zero. The verifier bounds length to 0..11 and move IDs to
0..8. It uses a separate 42-byte concrete move table, not the search PDBs or
abstract transitions. Invalid results are rejected before printing a solution.
The CLI leaves `a4 = 1` only after successful verification (`0` on rejection);
`check_asm.py --require-verification` checks this in addition to host replay.

`solver.elf` prints a solution line, or an input/failure diagnostic.
`bench.elf` omits output. Ripes exit ecall 10 returns process exit code zero
even for rejected input; callers/tests must inspect the signed value of `a0`.
There is no hosted `--self-test` argument or hosted stdout-error test on this target.

### Architecture and memory

`asm_search` keeps both current coordinates, bound, path, depth, face, turn,
previous face, next bound, and three table bases in `s0..s11`. The second
PDB base stays in `a6`; table macros use scratch `t0..t5`. Calls outside the
search follow ILP32; saved registers and `ra` are restored, and every machine
stack frame is aligned to 16 bytes. The search contains no calls. The default
build removes its unnecessary `ra` save/restore and caches the face-row pointer
in `a5`, advancing it on a face change and restoring it on backtracking.

Ten ancestor records occupy 160 bytes, each `{a,b,face,turn}` consisting of
four words. A saved non-goal child has `h >= 1` and
`depth + 1 + h <= bound <= 11`, so its depth is at most ten. This bounds the
ancestor array. The current state stays in registers. Rejected children do
not write ancestors. On success only the eleven-or-fewer final path bytes
are written. The fixed search frame is 240 bytes, the outer solver frame
is 32, and the text wrapper frame is 32: maximum simultaneous machine stack
is **304 bytes**. Projection temporarily uses another 32-byte frame, but
does not overlap the search. Stack top is `0x100000`, inherited from the
existing freestanding linker/startup arrangement.
Concrete replay uses a separate 32-byte leaf frame after search has returned,
so it does not increase the 304-byte maximum.

| Linked section | Solution-output ELF | Silent ELF |
| --- | ---: | ---: |
| `.text` | 2,176 | 2,012 |
| `.rodata` | 84,825 | 84,725 |
| `.data` | 32 | 32 |
| `.bss` | 11 | 11 |
| Static total | **84,868** | **84,768** |

The table payload is `2*34020 + 3*840*4 + 81*81 = 84,681` bytes.
The silent executable leaves 46,304 bytes below the 131,072-byte static limit.
Concrete replay data and alignment add 44 bytes; output strings and alignment
add another 100 bytes. No LED framebuffer is reserved yet. Stack is additional
working memory, not an allocated `.bss` section. `.riscv.attributes` is
non-allocated metadata and is excluded from the static total.

The original Phase 1 source is preserved as `validation/phase1_solver.S`.
Its output/silent `.text` sizes were 1,812/1,664 bytes. Per-function sections
now let the linker remove unused parser and accessor functions from the
normalized core benchmark. This affects linked size, not traversal.
Replay code and data are also removed from that benchmark. Rebuilding its
optimized assembly variant produces the same ELF hash as the archived core
comparison, so its measurements and 52-byte code-size trade-off still apply.

## Reproduce the build

### Git policy and generated inputs

Track handwritten assembly, headers, host generators, build/test/benchmark
scripts, documentation, and the complete curated `validation/` directory.
Its CSV/JSON records, disassemblies, compiler stack report, gate logs, and
Phase 1 source snapshot support the reported measurements and provenance.
Keep them even though some were generated. Fresh/debug runs belong in ignored
`results/`; ELF/object files, generated `tables.S`, the exporter executable,
and working disassembly belong in ignored `build/`.

Root PDB files and `tests/exact_distances.bin` can be regenerated entirely
from repository sources. A clean-copy build on 2026-10-08 reproduced their
hashes, the assembly tables, and all four benchmark ELF hashes exactly,
using the existing GCC 13.2.0 toolchain. From a fresh checkout:

```sh
make pdb ida_solver
make -C tests distances
make -C rv32 all compare-build RV32_CC=/path/to/riscv64-unknown-elf-gcc
```

If only the binary PDBs were removed while `pdb_data.h` remains, `make pdb`
may consider the header up to date. Restore all three outputs explicitly with
`make generate_pdb` followed by `./generate_pdb` from the repository root.
Python checks use the standard library; Ripes measurements additionally need
the external pinned executable and a display or Xvfb. Local tool installations
are not Git inputs. Preserve `tests/ripes_pin.json` and the archived flags/hashes;
temporary `/tmp` tool paths in commands must be replaced on another machine.

GNU RISC-V GCC/binutils can be installed normally or provided via `PATH`.
The inspected environment has an extracted GCC 13.2.0 toolchain under
`/tmp/minirubik-toolchain/usr/bin`; these temporary paths may disappear.
Native `cc` and Python 3 are also required. Ripes is pinned by
`tests/ripes_pin.json` to `v2.2.6-106-g5b8a616`.

From the repository root:

```sh
export PATH=/tmp/minirubik-toolchain/usr/bin:$PATH
make rv32-asm
make inspect-asm
```

Outputs live in ignored `rv32/build/`: host exporter, generated `tables.S`,
`solver.elf`, `bench.elf`, and disassembly. Tables are generated automatically
when absent; no external table files are needed while the target runs.
The assembler/linker flags are:

```text
-march=rv32i -mabi=ilp32 -mno-relax -msmall-data-limit=0 -nostdlib
-Wl,--no-relax -Wl,-T,../tests/rv32.ld
```

`inspect_elf.py` checks every linked instruction's encoding against RV32I,
every allocated non-code section against the memory budget, and all 84,681
exported table bytes against the host C arrays. Both packed PDB sections are
also compared with the existing binary PDBs.

## Reproduce correctness tests

```sh
make check-ida
make -C tests verify
python3 rv32/check_asm.py --shallow \
  --ripes /tmp/minirubik-ripes/squashfs-root/AppRun \
  --xvfb /tmp/minirubik-ripes/Xvfb \
  --xvfb-library-dir /tmp/minirubik-toolchain/usr/lib/x86_64-linux-gnu
python3 rv32/check_asm.py --smoke --proc RV32_5S \
  --ripes /tmp/minirubik-ripes/squashfs-root/AppRun \
  --xvfb /tmp/minirubik-ripes/Xvfb \
  --xvfb-library-dir /tmp/minirubik-toolchain/usr/lib/x86_64-linux-gnu
```

Omit the Xvfb arguments when an X display is available. In this managed
environment the X server requires permission to bind local sockets.
An abstract X11 socket may work even when its `/tmp/.X11-unix` path is hidden;
the runner therefore checks server liveness instead of waiting for that path.

Ripes runs with `--mode cli -t elf --proc RV32_ISS` (or `RV32_5S`),
`--iret --regs --json --runinfo`, no ISA extensions, and a 60-second simulation
timeout per input. It patches only `.data` in one ELF. It reads the length
from `x10`, independently replays printed moves using corner cycles, verifies
the optimal length, checks exact line formatting, and compares search output
with the validated C reference. Reports contain every input, PASS/FAIL,
actual length/output, and retired count in CSV, plus ELF/source/Ripes hashes
and the command in JSON. Solution-output counts include parsing and printing
and must not be used as a fair compiler comparison.

Measured baseline coverage (2026-10-08):

| Check | Coverage | Result |
| --- | --- | --- |
| Stage 3 independent PDB BFS and CLI tests | All PDB entries; 385 shallow states; eight optimal vectors | PASS |
| Stage 3 H1/H2/H3/H4 | Full existing gates, including all 3,674,160 C searches | PASS |
| Assembly ELF/table inspection | Both executables; all instructions and 84,681 table bytes | PASS |
| Assembly `RV32_ISS` | 385 depth-0–3 states, seven additional depth-8–11 vectors, twelve invalid inputs: 404 cases | PASS |
| Assembly `RV32_5S` | Solved, nine one-move states, twelve invalid inputs: 22 cases | PASS |
| Assembly all 2,644 distance-11 states | Original baseline; optimal lengths, independent replay, exact C path; 3,047 cases including shallow/invalid coverage | PASS |
| Target H2/H4 accessor coverage | All 136,080 packed distance entries and 204,120 abstract quarter turns, combined with host table certification | PASS |
| Assembly H1/H3 over every concrete state | All 3,674,160 concrete states | TBD |

Archived results are in `rv32/validation/`; fresh runs use ignored
`rv32/results/`. The hard-case output is:

```text
21345671111111 -> R B' D2 R' B R' B' R D2 R B
length=11; independent replay=solved; validated C path=identical
```

To reproduce the complete hard-case correctness suite:

```sh
python3 rv32/check_asm.py --shallow --distance11 \
  --ripes /path/to/extracted/AppRun --xvfb /path/to/Xvfb
```

The distance-11 cases come from the host BFS oracle; run the existing full
gates first to certify it. This target run will test optimality, replay, and
the exact C traversal output for each case. Its printed instruction counts
include output and do not constitute the renderer-free performance benchmark.

## Final full-program CLI grading

The final verified text-entry grading benchmark is separately documented in
[VERIFIED_CLI.md](VERIFIED_CLI.md). All 2,644 hard states passed optimality,
in-program replay and independent host replay on pinned RV32_ISS, with **6,733,921** maximum retired
instructions and **zero** states above 50,000,000. The required vector takes
**3,791,721** instructions. These counts include parsing, validation, search,
path generation, target replay, solution printing and exit; they exclude the LED renderer.
They must be distinguished from the normalized-input comparison below.
The same CLI ELF passed solved, short and distance-11 inputs on ISS and RV32_5S.
The earlier CLI campaign is retained in [CLI_BENCHMARK.md](CLI_BENCHMARK.md).

## GCC -O2 comparison and incremental optimizations

`compare_start.S` supplies the same 14-byte normalized input and eleven-byte
output path to four runtime variants. It initializes saved registers with
distinct sentinels, checks them and the restored stack pointer, checks a stack
guard, and packs the returned path into `a1/a2/a3`. Ripes `--regs` retrieves
the actual path without printing. `a0` contains length and `a5` is the ABI
failure flag. Every path is independently replayed and compared across the
four variants. Counts include the common harness and exclude parsing,
program output, and rendering.

`c_core.c` exposes the actual Stage 3 `solve` function with its algorithm and
data unchanged. ILP32 passes its 14-byte aggregate indirectly in `a0`, and
the output pointer in `a1`, matching the common assembly caller. A separate
C pointer-to-value wrapper was rejected after GCC lowered its aggregate copy
to an unavailable `memcpy`; the final bridge introduces no copy wrapper or
library dependency.

| Variant | Build definition | Purpose |
| --- | --- | --- |
| `gcc_O2` | `BENCH_C` | Actual Stage 3 C core, GCC 13.2.0 `-O2` |
| `asm_baseline` | None | Original search operations |
| `asm_leaf` | `ASM_REMOVE_LEAF_RA` | Remove two instructions per threshold search |
| `asm_cached` | Both assembly options | Also cache the current face-row pointer |

All four are checked for RV32I encodings, exact table-byte equivalence, and
static memory. The common exit is followed by a harmless self-loop: without
it, ISS final register reporting showed an additional 224-byte stack decrement
matching the adjacent C prologue despite a passing in-program ABI check.
The guard resolves this observation and is identical in all four binaries.

Reproduce the complete comparison from the repository root:

```sh
python3 rv32/compare.py \
  --cc /tmp/minirubik-toolchain/usr/bin/riscv64-unknown-elf-gcc \
  --objdump /tmp/minirubik-toolchain/usr/bin/riscv64-unknown-elf-objdump \
  --ripes /tmp/minirubik-ripes/squashfs-root/AppRun \
  --xvfb /tmp/minirubik-ripes/Xvfb \
  --xvfb-library-dir /tmp/minirubik-toolchain/usr/lib/x86_64-linux-gnu
```

The equivalent make target is `make compare-asm` with tool/Xvfb arguments
supplied using `RV32_CC`, `RV32_OBJDUMP`, `RIPES` and `RIPES_ARGS`.
Add `--limit 2` for a smoke run or `--limit 1 --proc RV32_5S` for representative
five-stage execution. Limited runs always report `PARTIAL PASS`, and never
certify all hard cases. Clean `rv32/build` when changing compiler or build flags.

Full comparison output goes to `results/comparison/`. CSV includes each actual
path, length and retired count for every variant. JSON records compiler flags,
source/ELF hashes, worst cases, totals and differences. See `BENCHMARK.md` for
the measured summary and archived evidence.

For the complete target accessor gate (test-only C driver, handwritten
accessors, no test driver in production binaries):

```sh
python3 rv32/run_accessor_gate.py \
  --cc /tmp/minirubik-toolchain/usr/bin/riscv64-unknown-elf-gcc \
  --ripes /tmp/minirubik-ripes/squashfs-root/AppRun \
  --xvfb /tmp/minirubik-ripes/Xvfb \
  --xvfb-library-dir /tmp/minirubik-toolchain/usr/lib/x86_64-linux-gnu
```

Host H2/H4 first certify the raw table bytes; this target gate verifies all
distance/nibble extractions and all abstract quarter turns through assembly.
Expected twist additions use explicit trits instead of `orientation_add`.
Complete concrete-state assembly H1/H3 remain outside this run's coverage.

## Remaining work and risks

The [requirements audit](CONSTRAINTS_AUDIT.md) distinguishes recorded test
passes from assignment compliance. Target-side replay and the final string
entry's three-case ISS/RV32_5S records are complete. The code-size win remains
deferred at the user's request: normalized assembly is 52 bytes larger than
GCC -O2 despite fewer retired instructions. Existing passing campaigns need
not be rerun unless their measured code changes.

1. Confirm the official handout. Complete concrete-state assembly H1/H3
   remains optional additional coverage; all 2,644 hard states and all abstract
   accessor combinations are already tested on RV32_ISS.
2. Preserve the measured benchmark boundary when making further optimizations.
   The final core's worst case is 6,729,300 instructions and its total over hard
   states is 13.25% below GCC -O2. Its code is 52 bytes larger and its maximum
   stack is 48 bytes larger; see `BENCHMARK.md` for the exact comparisons.
3. Implement a separate 35×25 LED renderer using validated concrete replay;
   verify physical color/twist conventions and MMIO addresses in Ripes.
   Keep its code and framebuffer out of benchmark binaries.
4. Observe actual IF/ID/EX/MEM/WB signals, stalls and forwarding in the GUI;
   CLI processor execution does not supply GUI screenshots or a walkthrough.

The first execution exposed Ripes' print-string syscall forwarding NUL bytes
to captured stdout. The output entry now emits characters individually and
all baseline cases were rerun. This was an output adaptation, not a claimed
search optimization. The ancestor bound relies on certified tables and the
eleven-move bound. Changed tables or a different puzzle diameter require
revisiting it before reuse.
