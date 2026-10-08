# Stage 4 work record

## Phase 0/1

Selected the final `ida_solver.c` implementation, preserved all C solvers,
and added handwritten runtime assembly, host table export, ELF checks, and
Ripes correctness runners. The original source and its 404-case ISS / 22-case
five-stage evidence remain under `validation/`. No commit or push was made.

## Phase 2–4 continuation, 2026-10-08

- Original assembly: all 2,644 distance-11 states, 385 shallow states,
  six other deep vectors and twelve invalid inputs: **3,047 PASS**.
- Optimized CLI: **404 PASS**, including invalid input and the required hard case.
- Target accessor gate: **136,080 distance entries and 204,120 quarter turns PASS**.
  Independent host H2/H4 first certify table bytes; target expected twists use
  explicit trits and do not consult the orientation-add lookup.
- Added an identical normalized-state harness for actual GCC `-O2` and three
  assembly variants. It checks saved registers, stack restoration, a guard,
  actual length, all move IDs, independent replay, and exact path agreement.
- Optimization 1 removes leaf search's `ra` stores/loads. Optimization 2 caches
  the face-row pointer between cursor changes. Both remain separately buildable;
  the default output/silent executables enable both. Original Phase 1 source
  is preserved as `validation/phase1_solver.S`.
- Representative RV32_5S comparison: **18 cases / 72 executions PASS**, including
  the required eleven-move case. This is CLI execution, not GUI pipeline evidence.

Complete benchmark results and the final measured worst case are recorded
in `BENCHMARK.md` and `validation/comparison_full/`; per-input actual paths
and all four retired counts are included in CSV. Metadata includes source,
oracle, Ripes and ELF hashes, compiler flags and execution commands.

## Historical full-program grading verification before target replay

The final optimized `solver.elf` was force-rebuilt with the existing two
optimization switches and solution printing enabled, with no LED renderer.
Its ELF hash matches the prior optimized CLI. Added `--distance11-only` to
the correctness runner to select exactly all 2,644 oracle-certified hard
states and record full-program budget statistics. Every case terminated
normally, returned eleven moves, and passed independent host replay and the
validated C path comparison. No additional search optimization was performed.

Maximum retired count: **6,729,751**, state `12347651111111`, rank 3,645.
Over 50,000,000: **0**. Required vector `21345671111111`: **3,787,559**.
These counts include text parsing, validation, search, path generation,
printing and exit, unlike the earlier normalized-input core benchmark.
Evidence is in `validation/final_cli_distance11/`; `CLI_BENCHMARK.md` contains
the summary and reproducible commands. The GCC -O2 comparison and all solver
sources remained unchanged, verified by hashes before and after the run.

## Mandatory correctness completion

Added `asm_verify_solution` to the text wrapper only. It copies the original
parsed cube, replays concrete moves independently of PDB/abstract transitions,
checks exact solved bytes, and rejects invalid move IDs/lengths. Failure returns
`-3`; `a4` exposes target verification status. The 304-byte maximum call stack
is unchanged. Added thirteen positive/negative verifier cases and optional
runner selectors; preserved existing test and benchmark defaults.

The same final text-entry ELF passes all three T7 inputs on ISS and RV32_5S,
and the verifier gate passes 13/13 on both. Existing ISS regression: 404/404.
Full hard set: 2,644/2,644 optimal eleven-move solutions, target verification
and independent host replay PASS. Maximum **6,733,921**, state
`12347651111111`, rank 3,645; over 50,000,000: **0**. Required vector:
**3,791,721**. Static data is **84,868** bytes; output CLI text is 2,176 bytes.

No additional performance optimization was made. The rebuilt normalized
assembly core is byte-identical to the archived comparison ELF. GCC comparison
sources/configuration/evidence remain unchanged; its 52-byte code-size loss
is deferred at the user's request. Historical CLI evidence remains untouched.
New records are in `validation/verified_t7/`, `verified_cli_shallow/` and
`verified_cli_distance11/`. See `VERIFIED_CLI.md` for reproducible commands.

## Corrected issues

The initial C wrapper caused GCC to emit an unresolved `memcpy` for an
aggregate copy. The final bridge exports the actual Stage 3 solve function;
RV32 ILP32 passes its fourteen-byte aggregate indirectly, matching the common
assembly caller without a copy wrapper or runtime library.

Without an instruction after the exit ecall, ISS reporting showed `sp`
decremented by 224 bytes although the in-program ABI check passed. This matches
the adjacent C prologue; stepping past exit is the inferred explanation.
A harmless terminal self-loop fixes the observation in all four binaries.
Failed harness results were excluded from the benchmark.

## Remaining work

Confirm the official assignment handout. Implement the separate 35×25 LED
renderer, verify physical sticker/twist conventions and configured MMIO,
and collect GUI IF/ID/EX/MEM/WB, stalls and forwarding evidence. No screenshots
or LED demonstration have been completed. Assembly H1/H3 over every one of
the 3,674,160 concrete states remains optional additional coverage; the complete
hard-case coverage must not be presented as that larger exhaustive result.
