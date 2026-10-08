"""Check linked instructions, static data, and emitted assembly table bytes."""
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from measure_rv32 import elf_sections

# Canonical encodings allowed by RV32I. Reject compressed/extended instructions.
def rv32i(word):
    opcode, f3, f7 = word & 127, word >> 12 & 7, word >> 25
    if opcode in (0x37, 0x17, 0x6f):
        return True
    if opcode == 0x67:
        return f3 == 0
    if opcode == 0x63:
        return f3 in (0, 1, 4, 5, 6, 7)
    if opcode == 0x03:
        return f3 in (0, 1, 2, 4, 5)
    if opcode == 0x23:
        return f3 in (0, 1, 2)
    if opcode == 0x13:
        return ((f3 not in (1, 5)) or (f3 == 1 and f7 == 0)
                or (f3 == 5 and f7 in (0, 32)))
    if opcode == 0x33:
        return f7 == 0 or (f7 == 32 and f3 in (0, 5))
    return word in (0x00000073, 0x00100073)  # ecall/ebreak


def main():
    objdump = sys.argv[1] if len(sys.argv) > 1 else "riscv64-unknown-elf-objdump"
    table_bytes = subprocess.check_output([str(ROOT / "rv32/build/export_tables"), "--binary"])
    if len(table_bytes) != 84681:
        raise AssertionError("incorrect host table payload size")
    # Exported target bytes must exactly match the certified host PDB binaries.
    for name in ("solver", "bench"):
        path = ROOT / f"rv32/build/{name}.elf"
        data = path.read_bytes()
        sections = elf_sections(data)
        symbols = {}
        for line in subprocess.check_output([objdump, "-t", str(path)], text=True).splitlines():
            fields = line.split()
            if len(fields) >= 5 and fields[-1].startswith("asm_"):
                symbols[fields[-1]] = int(fields[0], 16)
        rodata = sections[".rodata"]
        start = rodata[4] + symbols["asm_pdb_a"] - rodata[3]
        if data[start:start + len(table_bytes)] != table_bytes:
            raise AssertionError(f"{name}: exported tables differ from Stage 3 C arrays")
        for pattern in ("a", "b"):
            offset = rodata[4] + symbols[f"asm_pdb_{pattern}"] - rodata[3]
            expected = (ROOT / f"pdb_{pattern}.bin").read_bytes()
            if len(expected) != 34020 or data[offset:offset + 34020] != expected:
                raise AssertionError(f"{name}: PDB {pattern} export mismatch")
        text = sections[".text"]
        if text[5] % 4:
            raise AssertionError("unaligned instruction section")
        for i in range(0, text[5], 4):
            word = struct.unpack_from("<I", data, text[4] + i)[0]
            if not rv32i(word):
                raise AssertionError(f"non-RV32I word {word:#x} at {text[3]+i:#x}")
        static = {n: s[5] for n, s in sections.items() if s[2] & 2 and not s[2] & 4}
        if sum(static.values()) > 131072:
            raise AssertionError("static memory exceeds 128 KiB")
        print(json.dumps(dict(elf=str(path.relative_to(ROOT)), status="PASS",
                              text_bytes=text[5], static_sections=static,
                              static_bytes=sum(static.values()), isa="RV32I",
                              exported_table_bytes_checked=len(table_bytes))))


if __name__ == "__main__":
    main()
