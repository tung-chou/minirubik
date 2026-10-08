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
| H2 | `verify_h2.c` | Both runtime PDBs are fully populated, have the reference maximum, and have exactly one zero at their solved entry. The test oracle's size, population, maximum, and solved entry are also checked. |
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
