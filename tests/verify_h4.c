#include "gate_common.h"

int main(int argc, char **argv)
{
    if (argc != 1) {
        fprintf(stderr, "usage: %s\n", argv[0]);
        return 2;
    }
    uint32_t total_failures = 0;
    for (unsigned pattern = 0; pattern < PDB_COUNT; ++pattern) {
        uint8_t *reference = reference_pdb(pattern);
        if (!reference)
            return 1;
        uint32_t checked[2] = {0}, failures[2] = {0};
        for (uint32_t rank = 0; rank < PDB_STATES; ++rank) {
            unsigned parity = rank % 2U;
            ++checked[parity];
            unsigned actual = pdb_distance(pdb_tables[pattern], rank);
            if (actual != reference[rank]) {
                ++failures[parity];
                ++total_failures;
                if (total_failures <= 20)
                    printf("H4 FAIL PDB=%c rank=%" PRIu32 " parity=%s"
                           " packed=%u unpacked=%u\n", 'A' + pattern, rank,
                           parity ? "odd" : "even", actual, reference[rank]);
            }
        }
        for (unsigned parity = 0; parity < 2; ++parity)
            printf("H4 PDB %c %s %s: checked=%" PRIu32 " mismatches=%" PRIu32 "\n",
                   'A' + pattern, parity ? "odd" : "even",
                   failures[parity] ? "FAIL" : "PASS", checked[parity], failures[parity]);
        free(reference);
    }
    printf("H4 %s: checked=%u mismatches=%" PRIu32 "\n",
           total_failures ? "FAIL" : "PASS", (unsigned) (PDB_COUNT * PDB_STATES),
           total_failures);
    int failed = output_failed();
    return total_failures || failed ? 1 : 0;
}
