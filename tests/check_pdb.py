"""Compare both packed PDBs against an independent abstract BFS."""

from collections import deque
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent.parent
PATTERNS = ((0, 1, 2, 3), (3, 4, 5, 6))
CYCLES = ((0, 3, 4, 1), (3, 6, 5, 4), (1, 4, 5, 2))
TWISTS = ({0: 1, 1: 2, 3: 2, 4: 1}, {3: 1, 4: 2, 5: 1, 6: 2}, {})
TRANSITIONS = []
for cycle, twists in zip(CYCLES, TWISTS):
    quarter = dict(zip(cycle, cycle[1:] + cycle[:1]))
    destinations, additions = list(range(7)), [0] * 7
    for _ in range(3):
        for at in range(7):
            destinations[at] = quarter.get(destinations[at], destinations[at])
            additions[at] = (additions[at] + twists.get(destinations[at], 0)) % 3
        TRANSITIONS.append((tuple(destinations), tuple(additions)))


def index(pos, ori):
    # Lexicographic rank of an ordered sample without replacement.
    available = list(range(7))
    permutation = 0
    for at, weight in zip(pos, (120, 20, 4, 1)):
        permutation += available.index(at) * weight
        available.remove(at)
    orientation = sum(o * weight for o, weight in zip(ori, (27, 9, 3, 1)))
    return permutation * 81 + orientation


for pattern, filename in zip(PATTERNS, ("pdb_a.bin", "pdb_b.bin")):
    packed = (ROOT / filename).read_bytes()
    assert len(packed) == 34020
    goal = (pattern, (0,) * 4)
    distances = {goal: 0}
    queue = deque([goal])
    while queue:
        pos, ori = queue.popleft()
        distance = distances[(pos, ori)]
        rank = index(pos, ori)
        actual = (packed[rank // 2] >> ((rank % 2) * 4)) & 15
        assert actual == distance, (filename, rank, actual, distance)
        for destinations, additions in TRANSITIONS:
            child = (
                tuple(destinations[at] for at in pos),
                tuple((o + additions[at]) % 3 for at, o in zip(pos, ori)),
            )
            if child not in distances:
                distances[child] = distance + 1
                queue.append(child)
    assert len(distances) == 68040
    print(f"{filename}: all 68040 packed distances match independent BFS")

# Regeneration must reproduce the embedded data and both binary files.
with tempfile.TemporaryDirectory(prefix="minirubik-pdb-") as temp:
    result = subprocess.run([str(ROOT / "generate_pdb")], cwd=temp,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    for filename in ("pdb_a.bin", "pdb_b.bin", "pdb_data.h"):
        assert (Path(temp) / filename).read_bytes() == (ROOT / filename).read_bytes()

print("Offline PDB regeneration is deterministic; packing and goal indices passed")
