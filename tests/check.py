"""Exercise the gates without starting an exhaustive IDA* run."""

from pathlib import Path
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
DATA = HERE / "exact_distances.bin"
STATES = 3674160


def run(binary, *args, expected=0):
    result = subprocess.run(
        [str(HERE / binary), *(str(arg) for arg in args)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == expected, (args, result)
    return result


def rank(code):
    p = [int(c) - 1 for c in code[:7]]
    permutation = 0
    for i, value in enumerate(p):
        permutation = permutation * (7 - i) + sum(x < value for x in p[i + 1:])
    orientation = 0
    for c in code[7:13]:
        orientation = orientation * 3 + int(c) - 1
    return permutation * 729 + orientation


data = DATA.read_bytes()
assert len(data) == STATES
assert data[0] == 0 and data.count(0) == 1 and max(data) == 11
vectors = 0
for line in (HERE / "solutions.txt").read_text().splitlines():
    if not line or line.startswith("#"):
        continue
    code, solution = line.split("|")
    assert data[rank(code)] == len(solution.split()), code
    vectors += 1

result = run("verify_h3", "--check-table", DATA)
assert "TABLE PASS" in result.stdout and "IDA* not run" in result.stdout
result = run("verify_h1", DATA)
assert "H1 PASS" in result.stdout and "checked=3674160" in result.stdout
result = run("verify_h2", DATA)
assert "H2 PASS: tables=5 failures=0" in result.stdout
assert result.stdout.count("populated=68040/68040 max=8 expected_max=8") == 2
assert "solved_rank=35235 solved_value=0" in result.stdout
result = run("verify_h4")
assert "H4 PASS: checked=136080 mismatches=0" in result.stdout
assert result.stdout.count("even PASS: checked=34020") == 2
assert result.stdout.count("odd PASS: checked=34020") == 2
result = run("verify_h3", DATA, 0, 16)
assert "PARTIAL PASS" in result.stdout and "checked=16/3674160" in result.stdout
result = run("verify_h3", DATA, rank("21345671111111"), 1)
assert "PARTIAL PASS" in result.stdout and "distance 11: checked=1" in result.stdout

for start, count in ((-1, 1), (0, 0), (STATES, 1), (STATES - 1, 2),
                     ("1x", 1), ("999999999999999999999999", 1)):
    run("verify_h3", DATA, start, count, expected=2)
run("generate_distances", "one", "two", expected=2)
run("verify_h1", "one", "two", expected=2)
run("verify_h2", "one", "two", expected=2)
run("verify_h4", "unexpected", expected=2)

with tempfile.TemporaryDirectory(prefix="minirubik-gates-") as temp:
    temp = Path(temp)
    bad = temp / "bad.bin"
    for content in (data[:-1], data + b"\0", bytes([1]) + data[1:],
                    data[:1] + bytes([12]) + data[2:]):
        bad.write_bytes(content)
        run("verify_h3", "--check-table", bad, expected=1)
        run("verify_h1", bad, expected=1)
        run("verify_h2", bad, expected=1)
    # An in-range corrupt distance must fail the graph-based certification.
    damaged = bytearray(data)
    damaged[1] = 1 if damaged[1] != 1 else 2
    bad.write_bytes(damaged)
    result = run("verify_h3", "--check-table", bad, expected=1)
    assert any(message in result.stderr for message in
               ("oracle mismatch", "inadmissible heuristic"))
    run("verify_h3", temp / "missing.bin", expected=1)
    run("generate_distances", temp / "missing-dir" / "data.bin", expected=1)

print(f"Gates passed: {STATES} oracle states certified, {vectors} known distances; "
      "H1/H2/H4 exhaustive checks; 17 H3 IDA* states (including depth 11); "
      "invalid arguments and corrupt files")
