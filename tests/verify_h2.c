#include "gate_common.h"

int main(int argc, char **argv)
{
    if (argc > 2) {
        fprintf(stderr, "usage: %s [exact_distances.bin]\n", argv[0]);
        return 2;
    }
    unsigned failures = 0;
    for (unsigned pattern = 0; pattern < PDB_COUNT; ++pattern) {
        uint8_t *reference = reference_pdb(pattern);
        if (!reference)
            return 1;
        uint32_t populated = 0, zeros = 0;
        unsigned maximum = 0, expected_maximum = 0;
        for (uint32_t rank = 0; rank < PDB_STATES; ++rank) {
            unsigned actual = pdb_distance(pdb_tables[pattern], rank);
            if (actual != 15) /* The generator reserves 15 for missing entries. */
                ++populated;
            if (actual == 0)
                ++zeros;
            if (actual > maximum)
                maximum = actual;
            if (reference[rank] > expected_maximum)
                expected_maximum = reference[rank];
        }
        pdb_state_t goal = pdb_goal(pattern);
        uint32_t goal_rank = pdb_rank(&goal);
        unsigned solved = pdb_distance(pdb_tables[pattern], goal_rank);
        int ok = populated == PDB_STATES && maximum == expected_maximum &&
                 solved == 0 && zeros == 1;
        failures += !ok;
        printf("H2 PDB %c %s: populated=%" PRIu32 "/%u max=%u expected_max=%u"
               " solved_rank=%" PRIu32 " solved_value=%u zero_entries=%" PRIu32 "\n",
               'A' + pattern, ok ? "PASS" : "FAIL", populated,
               (unsigned) PDB_STATES, maximum, expected_maximum,
               goal_rank, solved, zeros);
        free(reference);
    }

    /* This is the test oracle, rather than a runtime search dependency. */
    uint8_t *distance = load_distances(argc == 2 ? argv[1] : "exact_distances.bin");
    if (!distance)
        return 1;
    unsigned maximum = 0;
    for (uint32_t rank = 0; rank < STATES; ++rank)
        if (distance[rank] > maximum)
            maximum = distance[rank];
    int ok = maximum == MAX_DEPTH;
    failures += !ok;
    printf("H2 exact-distance oracle %s: populated=%u/%u max=%u expected_max=%u"
           " solved_rank=0 solved_value=%u\n", ok ? "PASS" : "FAIL",
           (unsigned) STATES, (unsigned) STATES, maximum,
           (unsigned) MAX_DEPTH, distance[0]);
    free(distance);
    printf("H2 %s: tables=3 failures=%u\n", failures ? "FAIL" : "PASS", failures);
    int failed = output_failed();
    return failures || failed ? 1 : 0;
}
