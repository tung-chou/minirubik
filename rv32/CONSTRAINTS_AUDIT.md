# Stage 4 requirements audit — 2026-10-08

**Mandatory correctness, T5–T7 execution, and the supplied grading budgets now
pass.** The code-size win remains unsatisfied and deferred at the user's
request. The current verified text-entry ELF has new source/ELF hashes and
separate records. A rebuilt normalized assembly core is byte-identical to its
archived benchmark ELF; original GCC comparison configuration and evidence,
and the pre-verification full CLI archive, remain unchanged.

## T5–T7

| Requirement | Status | Evidence and scope |
| --- | --- | --- |
| T5: returned paths reach solved | PASS for all recorded successful cases | The final text wrapper concretely replays each solution and checks the exact solved cube. All 2,644 hard states pass both target and independent host replay; existing 404-case regression also passes. This is tested coverage, not an exhaustive assembly run over all 3,674,160 states. |
| T6: `21345671111111` has an optimal 11-move result | PASS | Both ISS and RV32_5S record length 11 and the same solving path. The certified BFS oracle establishes optimality. The diameter comes from the complete host H3 result, not the target samples. |
| T7: three cases on ISS and a visual pipeline model | PASS for the final text-entry executable | The same final CLI ELF passed solved, one-move and the required distance-11 input on ISS and RV32_5S. All paths and target verification status pass; actual records are in `validation/verified_t7/`. |

The three final text-entry cases, recorded on both processor models, are:

| Inlined state | Expected length | Returned path |
| --- | ---: | --- |
| `12345671111111` | 0 | Empty |
| `25314672313211` | 1 | `R'` |
| `21345671111111` | 11 | `R B' D2 R' B R' B' R D2 R B` |

RV32_5S is a visual pipeline processor model executed here through the CLI.
GUI screenshots and pipeline observations are separate, still pending work;
they are not needed to claim the recorded CLI executions. No execution claim
is made for an unspecified future grader input. The generic parser and search
support replacing the inlined string with any valid state, without changing
the algorithm or providing a precomputed solution.

## Constraints

| Constraint | Status | Evidence and limitation |
| --- | --- | --- |
| RV32I only; no M or other extensions; no compiler runtime calls | PASS | Archived inspection checks every linked instruction. Solver symbols and calls are handwritten assembly; no libc/libgcc helper is linked. Constant products use shifts/additions; parser modulo uses bounded subtraction. |
| No heap, recursion, or floating point; fixed storage | PASS | Search uses a fixed 240-byte frame with ten explicit ancestor records. Calls are acyclic; data and path buffers are sized at assembly time. The text-entry maximum call stack is 304 bytes. |
| Arbitrary valid 14-character inlined input | PASS for implementation and recorded coverage | `start.S` defines `asm_input` with `.asciz`; `asm_parse_state` validates length, digit ranges, uniqueness, and twist sum. Search depends on parsed coordinates, not a list of known vectors. |
| At least three required categories of test case | PASS | Solved, short scramble and the specified distance-11 vector pass through the final CLI on both models. |
| Validate solving results inside the target program | PASS | `asm_solve_text` calls handwritten `asm_verify_solution` on the original parsed cube and returned path. Only exact solved replay returns success; invalid lengths/IDs and nonsolving paths are rejected. The thirteen-case positive/negative gate passes on both models. Host replay remains independent. |
| Handwritten design rather than mechanical C translation | SATISFIED by documented design | Register-held search state, fixed ancestor frames, inline table operations, unrolled partial ranking, and a cached face-row pointer specialize the target implementation. |
| Beat final GCC -O2 reference in retired instructions | PASS over the reported full comparison set | Aggregate hard-case reduction is 13.25%; the specified hard case improves from 4,375,238 to 3,787,108 retired instructions. |
| Beat GCC -O2 in linked code size | **NOT SATISFIED; deferred** | Normalized assembly `.text` remains 1,664 bytes versus GCC's 1,612 bytes: 52 bytes larger (3.23%). The user explicitly requested no code-size optimization in this correctness change. The verified output CLI has 2,176 text bytes under its separate full-program boundary. |
| Report reference build and explain losses | PASS | `BENCHMARK.md` reports actual Stage 3 GCC -O2, flags, linked sections, stack, counts, and the size loss. Cached-row optimization adds 32 code bytes relative to the leaf variant while reducing instructions by 5.71%. |
| Measured iterative refinement and common conventions | PASS | Baseline, leaf, and cached variants are separately measured on the same inputs. Code size is bytes of linked `.text`, with rendering/output absent. Counts use pinned Ripes `--iret`; the common normalized-input harness is included, parsing/output/rendering excluded. Processor models are reported separately. |

The current measurements use GCC 13.2.0 with `-O2 -march=rv32i -mabi=ilp32`
and pinned Ripes `v2.2.6-106-g5b8a616`. They compare the actual final C solver
and assembly under the same normalized-state entry harness. They do not compare
the text/printing frontend against the normalized C core.

## Remaining work

The mandatory correctness gaps and final CLI instruction-budget verification
requested in this change are complete. Code-size improvement is deliberately
deferred; reporting the trade-off does not establish a size win. LED rendering
and GUI pipeline observations remain separate pending assignment work.

Full concrete-state assembly H1/H3 is additional coverage, not a prerequisite
implied by T5–T7 here. The complete host H3 already establishes diameter 11.

## Existing evidence

The final **verified full CLI** campaign passes all 2,644 hard states, including
optimal eleven-move lengths and both target and host replay. Its maximum is
**6,733,921**, with **zero** states exceeding 50,000,000; `21345671111111`
takes **3,791,721**. Parsing, validation, search, target replay, printing and
exit are included; the renderer is absent, static data is **84,868 bytes**.
See [VERIFIED_CLI.md](VERIFIED_CLI.md) and
[the current summary](validation/verified_cli_distance11/summary.json).
The earlier pre-verification measurements remain available in
[CLI_BENCHMARK.md](CLI_BENCHMARK.md) and their original archive.

- [Final text-entry ISS](validation/verified_t7/correctness_RV32_ISS.json) and
  [RV32_5S](validation/verified_t7/correctness_RV32_5S.json): 3/3 representative
  cases and 13/13 verifier gate cases on each model.
- [Verified CLI regression](validation/verified_cli_shallow/correctness_RV32_ISS.json):
  404/404, including twelve invalid inputs.

- [Full core comparison](validation/comparison_full/summary.json) and
  [actual paths and counts](validation/comparison_full/comparison.csv):
  2,660 inputs / 10,640 executions, all PASS.
- [RV32_5S core comparison](validation/comparison_5S/summary.json) and
  [actual paths and counts](validation/comparison_5S/comparison.csv):
  18 inputs / 72 executions, all PASS; correctly labelled a limited run.
- [Optimized text-entry ISS record](validation/optimized_cli/correctness_RV32_ISS.json):
  404/404 PASS.
- [Original text-entry RV32_5S record](validation/correctness_RV32_5S.json):
  22/22 PASS, with original source snapshot [phase1_solver.S](validation/phase1_solver.S).
- [Host H1–H4 gate output](validation/stage3_gates.txt): H3 matches all
  3,674,160 states, including exactly 2,644 states at distance 11.
- [Target accessor gate](validation/accessor_gate.json): all 136,080 packed
  distance checks and 204,120 abstract quarter turns PASS.
- [Benchmark conventions and refinement](BENCHMARK.md).
