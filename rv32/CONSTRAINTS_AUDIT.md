# Stage 4 requirements audit — 2026-10-08

**The listed requirements are not all satisfied.** This audit reuses existing
execution records; no solver simulations, exhaustive gates, or benchmarks were
rerun. The current comparison sources, oracle, and all four benchmark ELFs match
the SHA-256 hashes in both archived processor summaries. The current text-entry
ELF also matches the optimized ISS correctness record.

## T5–T7

| Requirement | Status | Evidence and scope |
| --- | --- | --- |
| T5: returned paths reach solved | PASS for all recorded successful cases | The host runners independently replay every actual returned path. The final core comparison covers 2,660 inputs across four variants, including all 2,644 distance-11 states, with zero failures. This is tested assembly coverage, not an exhaustive assembly run over all 3,674,160 states. |
| T6: `21345671111111` has an optimal 11-move result | PASS | Both ISS and RV32_5S record length 11 and the same solving path. The certified BFS oracle establishes optimality. The diameter comes from the complete host H3 result, not the target samples. |
| T7: three cases on ISS and a visual pipeline model | PASS for the solver core; final string-entry coverage incomplete | The same final core ELFs passed solved, one-move, and distance-11 inputs on ISS and RV32_5S. The final 14-character text-entry ELF has an ISS record, but its three-case RV32_5S record is missing. The older text-entry pipeline smoke test covers solved/one-move/invalid inputs, not the required hard case. |

The three core cases, already present in both processor CSVs, are:

| Inlined state | Expected length | Returned path |
| --- | ---: | --- |
| `12345671111111` | 0 | Empty |
| `25314672313211` | 1 | `R'` |
| `21345671111111` | 11 | `R B' D2 R' B R' B' R D2 R B` |

RV32_5S is a visual pipeline processor model executed here through the CLI.
GUI screenshots and pipeline observations are separate, still pending work;
they are not needed to claim the recorded core executions. No execution claim
is made for an unspecified future grader input. The generic parser and search
support replacing the inlined string with any valid state, without changing
the algorithm or providing a precomputed solution.

## Constraints

| Constraint | Status | Evidence and limitation |
| --- | --- | --- |
| RV32I only; no M or other extensions; no compiler runtime calls | PASS | Archived inspection checks every linked instruction. Solver symbols and calls are handwritten assembly; no libc/libgcc helper is linked. Constant products use shifts/additions; parser modulo uses bounded subtraction. |
| No heap, recursion, or floating point; fixed storage | PASS | Search uses a fixed 240-byte frame with ten explicit ancestor records. Calls are acyclic; data and path buffers are sized at assembly time. The text-entry maximum call stack is 304 bytes. |
| Arbitrary valid 14-character inlined input | PASS for implementation and recorded coverage | `start.S` defines `asm_input` with `.asciz`; `asm_parse_state` validates length, digit ranges, uniqueness, and twist sum. Search depends on parsed coordinates, not a list of known vectors. |
| At least three required categories of test case | PASS for supplied automated cases | Solved, short scramble, and the specified distance-11 vector are in both core processor records. |
| Validate solving results inside the target program | **NOT SATISFIED** | Concrete path replay, solved-state comparison, and expected-length assertions are in `check_asm.py` and `compare.py`. `start.S` solves and prints; `compare_start.S` checks ABI/stack integrity only. The target accessor gate checks table operations, not whole solutions. Automated host validation does not fulfill this separate requirement. |
| Handwritten design rather than mechanical C translation | SATISFIED by documented design | Register-held search state, fixed ancestor frames, inline table operations, unrolled partial ranking, and a cached face-row pointer specialize the target implementation. |
| Beat final GCC -O2 reference in retired instructions | PASS over the reported full comparison set | Aggregate hard-case reduction is 13.25%; the specified hard case improves from 4,375,238 to 3,787,108 retired instructions. |
| Beat GCC -O2 in linked code size | **NOT SATISFIED** | Final assembly `.text` is 1,664 bytes versus GCC's 1,612 bytes: 52 bytes larger (3.23%). The baseline and leaf variants are also larger. Reporting and explaining the loss does not establish a code-size win. |
| Report reference build and explain losses | PASS | `BENCHMARK.md` reports actual Stage 3 GCC -O2, flags, linked sections, stack, counts, and the size loss. Cached-row optimization adds 32 code bytes relative to the leaf variant while reducing instructions by 5.71%. |
| Measured iterative refinement and common conventions | PASS | Baseline, leaf, and cached variants are separately measured on the same inputs. Code size is bytes of linked `.text`, with rendering/output absent. Counts use pinned Ripes `--iret`; the common normalized-input harness is included, parsing/output/rendering excluded. Processor models are reported separately. |

The current measurements use GCC 13.2.0 with `-O2 -march=rv32i -mabi=ilp32`
and pinned Ripes `v2.2.6-106-g5b8a616`. They compare the actual final C solver
and assembly under the same normalized-state entry harness. They do not compare
the text/printing frontend against the normalized C core.

## Work to complete before claiming compliance

1. Add handwritten target-side concrete replay and solved-state verification
   for the arbitrary input and returned path. Supply target self-test cases
   checking expected lengths 0, 1, and 11; keep validation outside the measured
   solver boundary for both implementations.
2. Reduce linked assembly `.text` below 1,612 bytes under the same benchmark
   convention while retaining the instruction advantage. With RV32I's
   four-byte instructions, the current binary needs at least a 56-byte reduction
   to become strictly smaller. New code requires new measurements; preserve
   the existing refinement records.
3. Record the three cases through the completed 14-character entry on ISS and
   RV32_5S. Reuse the existing core results; do not repeat the old exhaustive
   campaigns just to fill this frontend evidence gap.

Full concrete-state assembly H1/H3 is additional coverage, not a prerequisite
implied by T5–T7 here. The complete host H3 already establishes diameter 11.

## Existing evidence

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
