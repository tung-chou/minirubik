/* Host-only exporter: reuse the final Stage 3 tables verbatim. */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "../pdb_data.h"

static void bytes(const char *name, const uint8_t *data, unsigned size)
{
    printf(".balign 4\n.globl %s\n%s:\n", name, name);
    for (unsigned i = 0; i < size; ++i) {
        if (i % 16 == 0) printf("    .byte ");
        printf("%u%s", data[i], i % 16 == 15 || i + 1 == size ? "\n" : ",");
    }
    printf(".size %s, .-%s\n", name, name);
}

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "--binary")) {
        if (fwrite(pdb_tables, 1, 68040, stdout) != 68040) return 1;
        for (unsigned f = 0; f < 3; ++f)
            for (unsigned p = 0; p < 840; ++p) {
                uint32_t word = coordinate_turn[f][p];
                for (unsigned byte = 0; byte < 4; ++byte)
                    if (putchar((int) ((word >> (8 * byte)) & 255)) == EOF) return 1;
            }
        if (fwrite(orientation_add, 1, 6561, stdout) != 6561) return 1;
        return fflush(stdout) != 0 || ferror(stdout);
    }
    if (argc != 1) {
        fputs("usage: export_tables [--binary]\n", stderr);
        return 2;
    }
    puts("/* Generated from pdb_data.h. Do not edit. */\n.file \"tables.S\"\n.section .rodata,\"a\",@progbits");
    bytes("asm_pdb_a", pdb_tables[0], 34020);
    bytes("asm_pdb_b", pdb_tables[1], 34020);
    puts(".balign 4\n.globl asm_coordinate_turn\nasm_coordinate_turn:");
    for (unsigned f = 0; f < 3; ++f)
        for (unsigned p = 0; p < 840; ++p)
            printf("    .word %u\n", (unsigned) coordinate_turn[f][p]);
    puts(".size asm_coordinate_turn, .-asm_coordinate_turn");
    bytes("asm_orientation_add", &orientation_add[0][0], 6561);
    return fflush(stdout) != 0 || ferror(stdout);
}
