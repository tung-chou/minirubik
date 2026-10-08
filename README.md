# minirubik

An optimal C99 solver for the 2×2×2 Rubik’s Cube. It builds a breadth-first
table for all 3,674,160 states and solves every valid position in at most 11
half-turn-metric moves.

## Why a cube is a graph

Ernő Rubik created the original cube in 1974 to demonstrate how parts can move
independently without breaking the whole. A 3×3 cube has 20 moving pieces and
about 4.3 × 10¹⁹ reachable arrangements. The smaller 2×2 cube keeps the eight
corners and removes the edges and fixed centers. [Philo Li’s formula-free
introduction](https://philoli.com/zh/blog/solve-rubiks-cube-without-formulas/)
offers the key intuition: every turn is reversible, turns can be composed, and
their order matters—`R U` is generally not `U R`.

Human solvers use those facts to move a few pieces while restoring the rest;
the commutator `A B A⁻¹ B⁻¹` is the standard example. This program uses the
same group structure differently: it treats every valid arrangement as a node,
every face turn as an edge, and searches the entire graph once. It does not use
the article’s 3×3 Roux stages or a library of memorized algorithms.

The solver gives the eight corner positions the numbers `0–7`. The 2.5D
walkthrough below shows where those numbers are on the physical cube.

## How it works

1. Fix one corner to remove whole-cube rotations.
2. Rank the remaining corner permutation and six independent orientations into
   a dense integer.
3. Breadth-first search outward from solved using `R`, `B`, and `D`, including
   inverse and half turns.
4. Store one move toward solved for every state; following those moves gives an
   optimal solution of at most 11 moves.

## Build and run

```sh
make
make check
make prove   # optional: Frama-C WP proof, needs frama-c and alt-ergo
./solver 21345671111111
```

`make` builds three binaries. `solver` is the documented one, with contracts, a
`--self-test` mode, and diagnostics on stderr. `mini` is a golfed variant that
solves the same input and prints the same line, kept as a readability contrast;
it has no `--self-test` and prints nothing on failure, and it trades roughly
eight times the runtime and three times the memory for its brevity.

`ida_solver` uses IDA* with two four-corner pattern databases (PDBs):

```sh
make ida_solver  # automatically builds and runs the offline PDB generator
./ida_solver 21345671111111
make check-ida
```

`generate_pdb.c` runs abstract BFS for two sets of tracked cubie identities:
A = {1,2,3,4}, B = {4,5,6,7} (input numbering). Each abstraction records the
positions and twists of its four cubies; it has P(7,4) × 3^4 = 68,040 states.
The partial index is `perm_rank * 81 + ori_rank`. Distances are packed two
per byte, with even indices in the low nibble and odd indices in the high
nibble. It generates `pdb_a.bin`, `pdb_b.bin` (34,020 bytes each), and
`pdb_data.h` for embedding the packed tables in the executable. Both PDBs have
diameter 8. Build artifacts are ignored by Git and regenerated during a fresh
build. To regenerate explicitly, run `make generate_pdb` then `./generate_pdb`.

Search uses `g = current depth` and `h = max(PDB_A, PDB_B)`, pruning when
`g + h` exceeds the current threshold. Forgetting three cubies relaxes the
goal, so both exact abstract distances are admissible. Their maximum is also
admissible; adding them would double-count moves. IDA* starts at `h(start)`
and increases the threshold to the smallest exceeded `g + h`. It stops at the
first solution and keeps the same consecutive-face pruning and 11-move HTM
limit. Equally short solutions may differ from the BFS output.

Search carries two 32-bit abstract coordinates instead of copying the full
cube. Projection and partial ranking happen once per input. The offline
generator also builds a shared `coordinate_turn[3][840]` table (10,080 bytes)
and `orientation_add[81][81]` table (6,561 bytes). Each candidate needs two
permutation/delta loads, two orientation loads, and two packed distance loads.
There is no division or remainder in the search. It checks the child's
heuristic before descent. Search uses a loop and a fixed array of ten
16-byte ancestor records, with no recursion. The current node stays in scalar
variables; only accepted non-goal children save their parent's state. Once a
goal is found, search copies the successful moves to the output path.

The two PDBs and shared transition tables occupy 84,681 bytes, plus alignment
and path storage. The explicit ancestor stack uses 160 bytes of automatic
storage. There is no runtime BFS or heap allocation, and no dependency on
external PDB files or the working directory.
Its `--self-test` checks state ranking, move inverses, PDB indices and packed
entries. `make check-ida` uses independent abstract BFS to verify all PDB
entries and an independent concrete model to check CLI solutions and optimal
move counts. These checks need Python 3.

For the full-state distance oracle, H1/H2/H3/H4 correctness gates, and
exhaustive IDA* comparison, see
[`tests/README.md`](<tests/README.md>).
That document also describes the freestanding RV32I build, static-data check,
instruction-bound analysis, and pinned Ripes measurement runner. The current
RV32I build uses 84,709 bytes of static data. Its conservative instruction
bound for all 2,644 distance-11 states is 28,942,094, below 50,000,000.
This is an analyzed bound; a complete Ripes measurement report is still pending.

The handwritten Stage 4 RV32I baseline is in [`rv32/`](rv32/README.md).
`make rv32-asm` builds solution-output and silent ELF files; `make inspect-asm`
checks RV32I encodings, exported tables, and static data. Its recorded Ripes
baseline passes all 2,644 distance-11 states. The full normalized-core
comparison measures 10,640 executions across GCC `-O2` and three assembly
variants; the optimized assembly reduces total hard-state instructions by
13.25%, with a worst case of 6,729,300. See the [measured benchmark](rv32/BENCHMARK.md)
for conditions, exact outputs and tradeoffs, and that directory for build commands,
ABI/data layout, memory sizes and remaining visualization work. The original
BFS and Stage 3 C implementations remain intact.

The 14-digit argument describes the scramble and the printed line is the
solution. Both formats are explained below.

### Reading the 14-digit input

The program receives one 14-digit code with no spaces. For explanation, split
it into two groups:

```diagram
2134567 1111111
└── P ─┘ └── O ─┘
  cubies   twists
```

Imagine seven numbered seats and seven students. A position is a seat fixed in
space; a cubie is the physical corner that can move to another seat. In the
solved cube, cubie 1 sits in position 1, cubie 2 in position 2, and so on.
The real cube has no printed numbers; `0–7` are labels used only by this solver.

#### Step 1: Hold the cube in one direction

Keep `FRONT` facing you and `UP` pointing upward. Position `0` is the corner
nearest the upper-left of the front face. It is an anchor for describing the
other corners; the physical cubie is not glued in place.

```diagram
                              BACK
                    ·───────────────·
                   ╱               ╱│
                  ╱        UP     ╱ │
                 ╱               ╱  │
              [0]───────────────·   │
               │                │   │
               │     FRONT      │ R │
               │                │   ·
               │                │  ╱
               │                │ ╱
               │                │╱
               ·────────────────·
```

`R` marks the narrow `RIGHT` face.

#### Step 2: Separate the front and back layers

A 2×2×2 cube has only corner cubies. Looking from the fixed direction, four
corner positions touch the front face and four touch the back face. Each
bracketed number below names one whole corner, not one colored sticker:

```diagram
 FRONT LAYER                          BACK LAYER

 upper-left   upper-right             upper-left   upper-right
     [0]────────[1]                       [7]────────[4]
      │          │                         │          │
      │          │       front ↔ back      │          │
     [3]────────[2]                       [6]────────[5]
 down-left    down-right               down-left    down-right
```

The front layer runs clockwise from its upper-left corner as `0, 1, 2, 3`.
The back layer is drawn as if seen through the cube from the front: `7` is
upper-left, followed clockwise by `4, 5, 6`.

#### Step 3: Join the two layers into positions 0–7

Slide the back square up and to the right, the same direction the cube recedes
in Step 1, to get the complete 2.5D position map. The back edges are drawn
through the front face rather than hidden behind it:

```diagram
                           BACK
                      [7]────────[4]
                     ╱ │        ╱ │
                  [0]──│─────[1]  │
                   │   │      │   │
                   │  [6]─────│──[5]
                   │ ╱        │ ╱
                  [3]────────[2]
                      FRONT
```

The seven characters of `P` describe positions `1, 2, 3, 4, 5, 6, 7` in that
order; the anchor at position `0` is left out.

#### Step 4: Put the cubies into those positions

Compare the position map on the left with the filled cube on the right. Read
`P = 2134567` from left to right to fill the positions. The arrows below the
figure identify the two positions that change.

```diagram
 POSITION MAP                             AFTER P = 2134567
 (fixed seats)                            (cubies now in seats)

     [7]────────[4]                           [7]────────[4]
    ╱ │        ╱ │                           ╱ │        ╱ │
 [0]──│─────[1]  │                        [0]──│─────[2]  │
  │   │      │   │                         │   │      │   │
  │  [6]─────│──[5]                        │  [6]─────│──[5]
  │ ╱        │ ╱                           │ ╱        │ ╱
 [3]────────[2]                           [3]────────[1]
     FRONT                                    FRONT

 position:     1 2 3 4 5 6 7
 P says:       2 1 3 4 5 6 7
               │ │ └───────── cubies 3–7 stay in their matching seats
               │ └─────────── put cubie 1 in position 2: [2] becomes [1]
               └───────────── put cubie 2 in position 1: [1] becomes [2]
```

So the first two digits, `21`, exchange the two corners on the front-right
edge. The remaining digits, `34567`, leave the other five movable corners
where they were. `P` must contain every digit from `1` through `7` exactly
once; otherwise a cubie would be missing or duplicated.

The seven seats named by `P` are:

| Position | Corner of the cube |
| :---: | :--- |
| 1 | front, upper, right |
| 2 | front, down, right |
| 3 | front, down, left |
| 4 | back, upper, right |
| 5 | back, down, right |
| 6 | back, down, left |
| 7 | back, upper, left |

The second group, `O = 1111111`, describes the twist of the cubie in each of
those same seven positions:

| Digit | Meaning |
| :---: | :--- |
| 1 | not twisted |
| 2 | twisted by +120° |
| 3 | twisted by −120° |

Here every orientation digit is `1`, so the two corners change places without
being twisted. For a valid cube, convert orientation digits to `0`, `1`, and
`2`; their sum must be divisible by three. The solved code is
`12345671111111`. `make check` uses the exchanged-corner example above.

## Reading the solution

```sh
$ ./solver 21345671111111
B' R' D2 R' B R B' R D2 B R'
```

Each token is one face turn. Apply them left to right; after the last one the
cube is solved.

| Token | Meaning |
| :---: | :--- |
| `R` | turn the `RIGHT` face 90° clockwise |
| `B` | turn the `BACK` face 90° clockwise |
| `D` | turn the `DOWN` face 90° clockwise |

Clockwise means clockwise as seen by someone looking directly at that face from
outside the cube, so you have to walk around to the back to read `B` and look up
from underneath to read `D`. Two suffixes modify a turn:

| Suffix | Meaning |
| :---: | :--- |
| none | 90° clockwise |
| `'` | 90° counterclockwise, the inverse |
| `2` | 180°, direction does not matter |

`R`, `B`, and `D` are the only faces that appear, because turning `UP`, `FRONT`,
or `LEFT` would move the anchor at position `0`. A turn counts as one move
whichever suffix it carries, which is the half-turn metric; under that metric no
position needs more than 11 moves. Solving an already-solved cube prints an
empty line.

See [`report.md`](report.md) for the model, algorithm, diagrams, and Frama-C
validation notes.
