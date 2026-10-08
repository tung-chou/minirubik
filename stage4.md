## Stage 4 — Handwritten RV32I Assembly Solver

This section records the Phase 0–4 implementation, correctness validation,
incremental optimizations and measured comparison completed on 2026-10-08.
LED rendering and GUI pipeline observations remain pending. Unmeasured
results are marked `TBD`.
The supplied task and grading requirements specify RV32I, at most 128 KiB of
static data, and at most 50,000,000 retired instructions for each of the
2,644 distance-11 states. Section 4.9 verifies these limits using the final
full text-entry CLI executable.

### 4.1 RV32I Implementation

The final Stage 3 reference is `ida_solver.c`. The earlier sections of this
report describe the original BFS implementation in `solver.c`; that BFS
implementation and the optimized C implementation are both preserved.
Stage 4 adds `rv32/solver.S`, a handwritten implementation of the optimized
two-coordinate IDA* search. No target C or compiler-generated solver assembly
is linked into the handwritten solver executables. Separate compiler-comparison
and accessor-gate executables intentionally use C.

Each pattern tracks four identities: A = `{0,1,2,3}`, B = `{3,4,5,6}`.
An abstract coordinate contains a partial permutation rank in bits 0–9 and
a base-three orientation rank in bits 10–16. Each PDB has
`P(7,4) * 3^4 = 68,040` distances packed two per byte. The distance index
is `permutation * 81 + orientation`, with even entries in the low nibble.
The admissible heuristic is `max(PDB_A, PDB_B)`. The pattern union covers
every movable cubie, so the joint abstract goal is the concrete solved cube.

`asm_parse_state` combines parsing and validation, rejecting wrong lengths,
out-of-range digits, duplicate cubies, and nonzero orientation sum modulo
three. It reads the text sequentially and stops on an early NUL. It uses
a seven-bit permutation mask and bounded subtraction for the twist sum.
`asm_coordinates` builds one inverse map, and internal `asm_rank4` performs
unrolled partial Lehmer and orientation ranking with shifts and additions.
`asm_solve_text(text, path)` returns length `0..11`, `-2` for invalid input,
`-1` for search failure, or `-3` for failed concrete solution replay.
A successful text-entry result is returned only after `asm_verify_solution`
replays all moves on a copy of the original parsed cube and checks the exact
solved permutation and orientations. Its separate 42-byte concrete move
table uses no PDB/abstract transitions. `asm_solve(state, path)` is the normalized-state
entry used by the equivalent normalized-state compiler comparison.

`asm_search` retains the C move order, consecutive-face pruning, minimum
exceeded-threshold update, and iterative backtracking. Current coordinates,
cursors, bounds, and table bases stay in registers. Accepted non-goal children
save four words `{a,b,face,turn}` to a bounded explicit ancestor array;
rejected candidates write neither ancestors nor the output path. On success,
the saved cursors reconstruct the moves. No heap or recursion is used.

The shared quarter-turn table has `3 * 840` words. Each word holds the next
permutation and a twist delta. The `81 * 81` byte table performs componentwise
orientation addition modulo three. These tables and both PDBs are exported
from the existing generated Stage 3 C arrays by host-only `export_tables.c`.
PDB generation, BFS oracle construction, full ranking/unranking, concrete
reference replay, and `self_test()` remain host utilities.

The hot-path table operations use RV32I only. For example, the orientation
row offset replaces multiplication by 81 with shifts and additions:

```asm
srli t2, t1, 10       # transition's four-cubie twist delta
slli t3, t2, 6
slli t4, t2, 4
add  t2, t2, t3
add  t2, t2, t4       # delta * 81
srli t3, s0, 10      # old orientation
add  t2, t2, t3
add  t2, t2, s10     # orientation_add base
lbu  t2, 0(t2)
```

Non-leaf functions preserve `ra` and all modified saved registers. Frames
are aligned to 16 bytes. The search is a leaf. Ripes startup reads the
NUL-terminated `asm_input` slot and stores move IDs in `asm_path`. The output
build uses character ecalls; the silent build excludes them. Ripes ecall 10
exits with process status zero, while signed `a0` retains the solver result.
Hosted `argc/argv`, `--self-test`, and stdout error handling are not target APIs.

### 4.2 Correctness Validation

The C reference was revalidated with independent abstract BFS and full H1–H4.
All 3,674,160 C solutions matched the exact BFS oracle and independent replay.
That result certifies the reference algorithm and tables; assembly search
coverage is stated separately below.

| Test | Coverage | Result |
| --- | --- | --- |
| Independent PDB BFS / C CLI checks | All PDB distances; 385 shallow states; eight vectors | PASS |
| C H1 | All 3,674,160 states, heuristic admissibility | PASS, zero violations |
| C H2 | PDBs, shared transitions, orientations, oracle | PASS |
| C H3 | All 3,674,160 searches, optimal lengths and replay | PASS, zero mismatches |
| C H4 | All 136,080 entries, both nibble parities | PASS |
| Assembly ELF inspection | Every instruction, both executables, all 84,681 table bytes | PASS |
| Assembly `RV32_ISS` | 385 depth-0–3 states, seven additional depth-8–11 vectors, twelve invalid inputs | PASS, 404/404 |
| Assembly `RV32_5S` | Solved, all nine one-move states, twelve invalid inputs | PASS, 22/22 |
| Original assembly all distance-11 states | All 2,644 hard states plus shallow, other vectors and invalid inputs | PASS, 3,047/3,047 |
| Optimized CLI | All shallow cases, additional vectors and invalid inputs | PASS, 404/404 |
| Pre-verification full CLI grading | Exactly all 2,644 distance-11 states; parsing, validation, search, printing and exit included | PASS, all host optimal/replay checks; zero over budget |
| Verified text-entry T7 | Same final ELF; solved, one-move and required distance-11 input on ISS and RV32_5S | PASS, 3/3 per model; target and host replay |
| Verifier positive/negative gate | Incorrect solutions, invalid move IDs/lengths, valid paths and original-state preservation | PASS, 13/13 on each model |
| Verified CLI regression | Existing shallow/vector/invalid-input suite | PASS, 404/404 |
| Verified full CLI grading | All 2,644 hard states, target replay included | PASS; maximum 6,733,921; zero over budget |
| Equivalent core comparison | GCC -O2 and three assembly variants; all hard states plus sixteen representative cases | PASS, 2,660 cases / 10,640 executions |
| Target H2/H4 accessor checks | Every packed distance entry and every abstract quarter turn | PASS, 136,080 distances / 204,120 transitions |
| Complete assembly H1/H3 | All 3,674,160 concrete states | TBD |

The host runner checks every successful target case for actual length, exact
output formatting, independent corner-cycle replay, and equality with the
validated C path. The final text-entry program additionally performs its own
concrete replay and solved-state check before returning a successful length.
The host runner checks the target's verification status in `a4` when requested.
Invalid cases cover empty/short/long input, illegal cubie/orientation digits,
non-digits, duplicates, and both nonzero twist-sum residues. Actual input,
expected/actual result, printed solution, PASS/FAIL, and retired count are
recorded in `rv32/validation/correctness_RV32_ISS.csv` and
`correctness_RV32_5S.csv`. Companion JSON files record configuration and hashes;
`stage3_gates.txt` contains the full C gate output.

The full baseline run is archived in `rv32/validation/distance11/`;
`optimized_cli/` contains the optimized text-entry results. The normalized
comparison in `comparison_full/` retrieves real move IDs from registers,
checks independent replay and BFS-optimal length, verifies exact path agreement
across all four variants, and checks saved registers and restored stack.
Its rank set was independently audited against all 2,644 oracle entries.
The target accessor gate exercises both nibble parities and all coordinate/face
combinations. Expected twists are calculated directly from trits rather than
the tested orientation-add lookup. Host H2/H4 certify the shared raw table bytes.

The detailed requirements audit is in
[`rv32/CONSTRAINTS_AUDIT.md`](rv32/CONSTRAINTS_AUDIT.md). Existing core tests pass
on ISS and RV32_5S; the final string-entry three-case suite now also passes on
both models, with records in `rv32/validation/verified_t7/`.
The assembly also remains 52 linked text bytes larger than GCC -O2, so an
instruction-count win does not establish a win on both required metrics.

Representative actual target outputs are:

```text
12345671111111 -> empty solution line; length 0
25314672313211 -> R'; length 1
21345671111111 -> R B' D2 R' B R' B' R D2 R B; length 11
11345671111111 -> invalid input or search failure; a0 = -2
12345671111112 -> invalid input or search failure; a0 = -2
```

Reproduction commands, from the repository root, are:

```sh
export PATH=/tmp/minirubik-toolchain/usr/bin:$PATH
make rv32-asm inspect-asm
make check-ida
make -C tests verify
python3 rv32/check_asm.py --shallow \
  --ripes /tmp/minirubik-ripes/squashfs-root/AppRun \
  --xvfb /tmp/minirubik-ripes/Xvfb \
  --xvfb-library-dir /tmp/minirubik-toolchain/usr/lib/x86_64-linux-gnu
```

These `/tmp` tools were present in the inspected environment. On another
machine, supply its RISC-V toolchain and the pinned extracted Ripes binary;
omit Xvfb when a display is available. Add `--smoke --proc RV32_5S` instead
of `--shallow` for the five-stage smoke suite. Add `--distance11` to the
ISS suite to reproduce exhaustive hard-case validation, after certifying the
oracle with the C gates. That run completed with 3,047 PASS in the continuation.
See `rv32/README.md` for the separate target-accessor and comparison commands.

Ripes configuration is `v2.2.6-106-g5b8a616`, CLI ELF input, RV32I with no ISA
extensions, `--iret --regs --json --runinfo`, and a 60-second simulation timeout
per state. The runner checks the executable SHA-256 against `ripes_pin.json`.

### 4.3 Memory Usage

The actual GNU-linked section sizes of the optimized text-entry builds are:

| Section | Output executable | Silent executable |
| --- | ---: | ---: |
| `.text` | 2,176 bytes | 2,012 bytes |
| `.rodata` | 84,825 bytes | 84,725 bytes |
| `.data` | 32 bytes | 32 bytes |
| `.bss` | 11 bytes | 11 bytes |
| Static data | **84,868 / 131,072 bytes** | **84,768 / 131,072 bytes** |

Table memory is `68,040 + 10,080 + 6,561 = 84,681` bytes. The writable input
slot reserves 32 bytes for valid and malformed test strings; the path is
eleven bytes. Concrete replay data/alignment add 44 bytes; output strings and
alignment add another 100 bytes. Non-allocated ELF metadata is not included.
The silent executable leaves 46,304 bytes of static headroom.

The original Phase 1 output/silent `.text` sizes were 1,812/1,664 bytes;
its source is preserved in `validation/phase1_solver.S`. The normalized
comparison removes unused functions through linker section collection and
uses a fourteen-byte input, so its sizes differ from these text-entry builds.

The ten 16-byte ancestor records occupy 160 bytes within a 240-byte search
frame. A non-goal accepted child satisfies `depth + 1 + h <= 11`, with
`h >= 1`, so at most ten ancestors are needed. The outer solver and text
wrapper each use 32 bytes. Maximum simultaneous stack is therefore
`32 + 32 + 240 = 304` bytes. Projection's separate 32-byte frame does not
overlap the search. Concrete replay's 32-byte leaf frame is used after search
returns, so maximum simultaneous stack remains 304 bytes. There is no dynamic
working-memory allocation.

Without the text wrapper the assembly core's maximum stack is 272 bytes.
GCC's actual `c_solve` is a leaf with one 224-byte frame, confirmed by its
disassembly and `validation/gcc_O2_stack.su`. Thus assembly uses 48 additional
stack bytes. Each benchmark call checks saved registers, restored `sp`, and
a guard 2,048 bytes below the initial stack pointer.

### 4.4 GCC -O2 vs. Handwritten Assembly

The measured comparison uses GCC 13.2.0 `-O2` and the handwritten core on the
pinned Ripes RV32_ISS, RV32I without extensions. Both binaries use the same
`compare_start.S`, fourteen-byte normalized input, eleven-byte path, identical
table values and result extraction. Counts include startup, saved-register/stack
checks, path packing and exit, and exclude parsing, program output and rendering.
The sixteen representative cases and all 2,644 hard states passed for all four
variants: **2,660 cases, 10,640 measured executions, FULL PASS**.

`c_core.c` exposes the actual Stage 3 `solve` function with only name/linkage
changes. ILP32 passes its fourteen-byte aggregate indirectly in `a0` and path
in `a1`, matching the common assembly entry without adding a C copy wrapper.
The existing C `-O3` analytical bound is a separate artifact and is not used
as an `-O2` measurement. Every instruction and all 84,681 table bytes in each
linked comparison executable are checked before execution.

| Metric under equivalent conditions | GCC -O2 | Optimized assembly | C minus assembly | Improvement |
| --- | ---: | ---: | ---: | ---: |
| Solved state retired instructions | 371 | 326 | 45 | 12.13% |
| One-move `25314672313211` | 641 | 602 | 39 | 6.08% |
| Required hard case `21345671111111` | 4,375,238 | 3,787,108 | 588,130 | 13.44% |
| Maximum over all hard states | 7,762,682 | 6,729,300 | 1,033,382 | 13.31% |
| Total over all hard states | 3,537,903,354 | 3,069,039,820 | 468,863,534 | 13.25% |
| Linked `.text`, including common harness | 1,612 bytes | 1,664 bytes | -52 bytes | -3.23% |
| Static data | 84,717 bytes | 84,706 bytes | 11 bytes | 0.013% |
| Maximum machine stack | 224 bytes | 272 bytes | -48 bytes | -21.43% |
| Optimal length, replay, ABI on all hard cases | PASS | PASS | — | — |

The worst inputs differ: C reaches its maximum at rank 1,137,240,
`32145671111111`; assembly at rank 3,645, `12347651111111`. The maximum-row
percentage compares two maxima, not one input. The aggregate percentage is
`100 * (sum(C) - sum(assembly)) / sum(C)` over the same 2,644 inputs.
All per-state assembly counts stay below 50,000,000; the maximum is 13.46%
of that budget. Static data also stays below 131,072 bytes.

Compiler flags include `-O2 -march=rv32i -mabi=ilp32 -mno-relax
-msmall-data-limit=0 -ffreestanding -fno-builtin -fno-pie
-fno-stack-protector -ffunction-sections -fdata-sections`; both links use
`-nostdlib --no-relax --gc-sections` and `tests/rv32.ld`. Neither libc nor
libgcc is linked. Full flags, hashes, commands and every actual path/count are
archived in `rv32/validation/comparison_full/`; `rv32/BENCHMARK.md` provides
reproduction commands. Host execution milliseconds are recorded for diagnostics
and are not used as the instruction-count improvement metric.

The original text/output baseline also passed all hard states with a measured
maximum of 7,136,518 instructions, including validation and printing. Those
counts use a different boundary and are not mixed with the core comparison.

### 4.5 Assembly Optimizations

The baseline incorporates the final Stage 3 design: one-time projection,
abstract coordinates, shared transitions, child pruning before descent,
fixed ancestors, and successful-path-only writes. Hot accessors are expanded
as assembly macros, table bases stay in registers, constant multiplication
uses shifts/additions, and packed nibble extraction uses shifts and masks.
The baseline and each incremental assembly variant were measured separately
over the same complete hard-state set and retained identical solving paths.

| Variant | Total hard-state instructions | Saved vs preceding assembly variant | Linked `.text` | Correctness |
| --- | ---: | ---: | ---: | --- |
| Original assembly operations | 3,254,943,926 | — | 1,640 bytes | PASS |
| Remove leaf `ra` save/restore | 3,254,914,982 | 28,944 (0.000889%) | 1,632 bytes | PASS |
| Also cache face-row pointer | 3,069,039,820 | 185,875,162 (5.71%) | 1,664 bytes | PASS |

The leaf optimization saves two instructions per threshold search and eight
code bytes; its search-wide benefit is very small. Face-row caching removes
eight shift/add instructions from each candidate, advances the pointer when
the face changes, resets it on descent, and recomputes it on backtracking.
It costs 32 code bytes relative to the leaf variant but saves 5.71% retired
instructions on the complete set. The default build enables both; baseline
and intermediate binaries remain separately reproducible.

```asm
# On descent, face becomes zero:
mv a5, s9                 # cached row = coordinate_turn[0]
# On a face change:
li t0, 3360
add a5, a5, t0            # next 840-word row
# On backtracking, FACE_ROW reconstructs the restored parent's row.
```

The initial C pointer wrapper failed to link because GCC inserted `memcpy`;
exporting the original aggregate-argument solver resolved the issue and avoids
charging an artificial wrapper copy to C. Initial ISS final registers showed
an extra 224-byte stack decrement while the in-program ABI probe passed.
Its match to the adjacent C prologue suggests execution past the exit ecall.
A harmless terminal self-loop after exit resolves the observation and is used
identically in all variants; failed harness results are excluded. These are
measurement corrections, not performance experiments. No other unsuccessful
search optimization experiment is claimed. Cursor reductions and alternative
PDB scheduling remain untested.

The first target execution also revealed a real output
failure: Ripes' print-string ecall included NUL bytes in captured stdout.
The entry now prints characters individually, and the complete baseline
suite was rerun successfully. This is an I/O correction, not a speedup result.

### 4.6 LED Matrix Visualization

Renderer implementation and GUI verification are `TBD`. The required matrix
is 35×25. The next implementation will replay the returned moves on a concrete
cube, draw the initial state, update after every move, and show solved. It
must verify the sticker orientation convention and configured Ripes MMIO
address. Renderer code, frame storage, and ecalls must remain outside the
instruction-count executable. No LED screenshot or animation is claimed.

### 4.7 Pipeline Observation

The RV32_5S CLI smoke suite passed 22 cases, which verifies execution on that
processor model. The equivalent normalized-core comparison additionally passed
18 representative inputs across four variants (72 executions), including the
required hard case; evidence is in `validation/comparison_5S/`. That partial
suite does not certify every hard state on RV32_5S. GUI signal observations,
cycle-by-cycle walkthrough, stalls,
forwarding evidence, and screenshots remain `TBD`.

The final fourteen-character text-entry program now passes all three required
representative inputs on both ISS and RV32_5S, including in-program replay.
The same ELF was used on both models. Actual paths, lengths and retired counts
are archived in `rv32/validation/verified_t7/`; this closes T7 execution coverage
without claiming GUI signal observations or screenshots.

For the manual walkthrough, load `rv32/build/solver.elf` into Ripes, choose
RV32_5S with no extensions, and step to the quarter-turn macro. Locate
`lw t1, 0(t0)` followed by `srli t2, t1, 10`. Track both instructions through
IF (PC/instruction), ID (source register numbers/values), EX (address and ALU
result), MEM (table read address/data), and WB (destination register/write
enable). Record the actual forwarding selection and any load-use stall.
Then observe `bltu s2, t0, .Lprune`, recording its branch decision, destination
PC, and any flushed instructions. Capture successive cycles and their signals;
do not substitute expected pipeline behavior for observed evidence.

### 4.8 Discussion and Reflection

The useful translation boundary is the optimized runtime, rather than the
original BFS solver or every C utility. Precomputed tables keep the target
small and remove arithmetic and full-cube copying from the hot loop. Explicit
ancestors give a bounded working set and preserve search order. The first
baseline already fits the provisional static-data budget and returns verified
optimal paths on both tested processor models.

The complete hard-case comparison now establishes the measured worst-case
instruction count under the stated boundary. The final assembly reduces total
hard-state instructions by 13.25% versus GCC -O2 while using 52 more code bytes
and 48 more stack bytes. Thus instruction reduction does not imply a smaller
program or smaller stack. Both variants fit the provisional assignment limits.

Remaining uncertainty concerns confirmation of the official handout, physical
visualization, GUI pipeline signals, and optional assembly H1/H3 coverage over
all 3,674,160 concrete states. Complete hard-state coverage is distinct from
that larger exhaustive domain. The next required work is the separate LED
renderer and observed pipeline demonstration; no screenshot or GUI success
is claimed by the CLI results.

### 4.9 Historical Full-Program Benchmark Before In-Program Verification

Before the concrete replay addition, the optimized text-entry `solver.elf` passed the
official retired-instruction condition on pinned Ripes
`v2.2.6-106-g5b8a616`, `RV32_ISS`, with no ISA extensions and no LED renderer.
Exactly all 2,644 distance-11 inputs terminated normally and returned optimal
eleven-move solutions that passed independent host concrete replay.

| Full CLI metric | Result |
| --- | ---: |
| Maximum retired instructions | **6,729,751** |
| Corresponding input / rank | `12347651111111` / 3,645 |
| States above 50,000,000 | **0 / 2,644** |
| `21345671111111` retired instructions | **3,787,559** |
| Static `.rodata + .data + .bss` | **84,792 / 131,072 bytes** |

These are actual `--iret` counts for startup, string parsing, state validation,
search, solution generation, printing and normal exit. They are separate from
the normalized-input compiler comparison in section 4.4, whose maximum and
required-vector assembly counts remain 6,729,300 and 3,787,108. The final CLI
ELF matches the previously archived optimized binary; no new solver
optimization or GCC comparison change was made.

[`rv32/CLI_BENCHMARK.md`](rv32/CLI_BENCHMARK.md) records reproducible commands.
[`summary.json`](rv32/validation/final_cli_distance11/summary.json) records
hashes, coverage and budget statistics;
[`counts.csv`](rv32/validation/final_cli_distance11/counts.csv) contains every
actual input, rank, path, expected/actual length and instruction count.
These historical results and their source hashes are preserved. Current
measurements after adding target replay are reported separately; the original
normalized-input GCC comparison in section 4.4 remains unchanged.

### 4.10 Mandatory Correctness Completion and Verified CLI Measurement

The final text wrapper now replays returned moves on a copy of the original
parsed concrete cube and requires the exact solved permutation and twists.
Invalid lengths, move IDs and nonsolving paths are rejected. Failed verification
returns `-3`; the CLI exposes verified success in `a4`. Host independent replay,
optimal-length assertions and exact C path checks remain in place.

The same final fourteen-character CLI ELF passes solved `12345671111111`,
short scramble `25314672313211` and required hard vector `21345671111111`
on both pinned ISS and RV32_5S. Actual lengths are 0, 1 and 11. ISS retired
counts are 631, 1,503 and 3,791,721; RV32_5S counts are 630, 1,502 and
3,791,720. Target and host replay both pass. The thirteen-case verifier
positive/negative gate passes on both models, and the existing ISS regression
suite remains 404/404 PASS. This closes T7 execution and target-verification
gaps without claiming GUI pipeline observations.

All 2,644 distance-11 states were remeasured using the final verified CLI,
renderer absent, pinned `v2.2.6-106-g5b8a616`, RV32_ISS, no extensions:

| Verified full CLI metric | Result |
| --- | ---: |
| Optimal eleven-move result, target and independent host replay | 2,644/2,644 PASS |
| Maximum retired instructions | **6,733,921** |
| Corresponding input / rank | `12347651111111` / 3,645 |
| States above 50,000,000 | **0** |
| Required vector retired instructions | **3,791,721** |
| Static `.rodata + .data + .bss` | **84,868 / 131,072 bytes** |

Counts include startup, parsing, validation, search, solution generation,
in-program concrete replay, printing and normal exit. Replay's leaf frame
does not overlap search, so maximum stack remains 304 bytes. No new performance
optimization was performed. A rebuilt normalized assembly ELF is byte-identical
to the previous core benchmark: its unused replay code/data are removed by
section collection. Section 4.4 and its archived GCC comparison are unchanged;
the 52-byte code-size loss remains deferred, while the 13.25% aggregate retired
instruction advantage is retained. Neither normalized-core counts nor the
historical pre-verification CLI counts should be substituted for this new result.

[`rv32/VERIFIED_CLI.md`](rv32/VERIFIED_CLI.md) contains commands and evidence
links; [the summary](rv32/validation/verified_cli_distance11/summary.json) and
[per-state counts](rv32/validation/verified_cli_distance11/counts.csv) record
the actual verified executable. Mandatory correctness and the supplied memory
and instruction budgets pass. The deliberate code-size trade-off, LED rendering
and GUI signal observations remain outside this correctness change.
