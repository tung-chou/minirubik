"""Check IDDFS output using corner cycles and independently computed distances."""

from collections import deque
from pathlib import Path
import subprocess
import sys


BINARY = str(Path(sys.argv[1]).resolve())
SOLVED = (tuple(range(7)), (0,) * 7)
MOVES = ("R", "R2", "R'", "B", "B2", "B'", "D", "D2", "D'")
# Each cycle lists where a cubie moves; twists are added at destinations.
CYCLES = ((0, 3, 4, 1), (3, 6, 5, 4), (1, 4, 5, 2))
TWISTS = ({0: 1, 1: 2, 3: 2, 4: 1}, {3: 1, 4: 2, 5: 1, 6: 2}, {})


def move(state, index):
    p, o = state
    face, turn = divmod(index, 3)
    cycle = CYCLES[face]
    for _ in range(turn + 1):
        np, no = list(p), list(o)
        for source, dest in zip(cycle, cycle[1:] + cycle[:1]):
            np[dest] = p[source]
            no[dest] = (o[source] + TWISTS[face].get(dest, 0)) % 3
        p, o = tuple(np), tuple(no)
    return p, o


def encode(state):
    return "".join(str(value + 1) for part in state for value in part)


def decode(code):
    return tuple(int(c) - 1 for c in code[:7]), tuple(int(c) - 1 for c in code[7:])


def run(*args, stdout=subprocess.PIPE):
    return subprocess.run(
        [BINARY, *args], stdout=stdout, stderr=subprocess.PIPE,
        text=True, timeout=120, check=False,
    )


def check_solution(state, distance):
    code = encode(state)
    result = run(code)
    assert result.returncode == 0, (code, result.returncode, result.stderr)
    tokens = result.stdout.split()
    assert len(tokens) == distance, (code, distance, result.stdout)
    assert result.stdout == " ".join(tokens) + "\n", (code, result.stdout)
    for token in tokens:
        assert token in MOVES, (code, token)
        state = move(state, MOVES.index(token))
    assert state == SOLVED, (code, result.stdout)


# Exhaust all states through depth 3, including solved and every single move.
distances = {SOLVED: 0}
queue = deque([SOLVED])
while queue:
    state = queue.popleft()
    distance = distances[state]
    check_solution(state, distance)
    if distance == 3:
        continue
    for index in range(9):
        child = move(state, index)
        if child not in distances:
            distances[child] = distance + 1
            queue.append(child)

vectors = 0
for line in Path(__file__).with_name("solutions.txt").read_text().splitlines():
    if not line or line.startswith("#"):
        continue
    code, known_solution = line.split("|")
    check_solution(decode(code), len(known_solution.split()))
    vectors += 1

invalid = (
    "", "1234567111111", "123456711111111", "02345671111111",
    "82345671111111", "12345671111110", "12345671111114",
    "1234567111111a", "11345671111111", "12345671111112",
)
for args in [(), (encode(SOLVED), encode(SOLVED))] + [(s,) for s in invalid]:
    result = run(*args)
    assert result.returncode == 2 and not result.stdout, (args, result)

result = run("--self-test")
assert result.returncode == 0, result.stderr
with open("/dev/full", "w") as full:
    for arg in (encode(SOLVED), "--self-test"):
        assert run(arg, stdout=full).returncode == 1, arg

print(f"IDDFS: {len(distances)} shallow states and {vectors} optimal vectors passed; "
      "invalid input, self-test and output errors passed")
