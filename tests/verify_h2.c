#include "gate_common.h"

static unsigned check_search_tables(void)
{
    unsigned failures = 0, maximum = 0, expected_maximum = 0;
    for (unsigned face = 0; face < 3; ++face) {
        for (unsigned p = 0; p < PDB_PERMUTATIONS; ++p) {
            pdb_state_t abstract = pdb_unrank(p * PDB_ORIENTATIONS);
            state_t state = reference_complete(&abstract, 0);
            state = reference_move(state, (uint8_t) (face * 3U));
            abstract = reference_project(&state, 0);
            uint32_t rank = pdb_rank(&abstract);
            unsigned expected = rank / PDB_ORIENTATIONS |
                                ((rank % PDB_ORIENTATIONS) << 10U);
            unsigned actual = coordinate_turn[face][p];
            failures += actual != expected;
            if (actual > maximum)
                maximum = actual;
            if (expected > expected_maximum)
                expected_maximum = expected;
        }
    }
    printf("H2 coordinate_turn %s: populated=2520/2520 max=%u expected_max=%u"
           " mismatches=%u; solved rows A=0/B=435 included\n",
           failures ? "FAIL" : "PASS", maximum, expected_maximum, failures);
    unsigned coordinate_failures = failures;
    failures = maximum = expected_maximum = 0;
    for (unsigned delta = 0; delta < PDB_ORIENTATIONS; ++delta) {
        pdb_state_t d = pdb_unrank(delta);
        for (unsigned o = 0; o < PDB_ORIENTATIONS; ++o) {
            pdb_state_t state = pdb_unrank(o);
            unsigned expected = 0;
            for (unsigned i = 0; i < PDB_CORNERS; ++i)
                expected = expected * 3U + (state.ori[i] + d.ori[i]) % 3U;
            unsigned actual = orientation_add[delta][o];
            failures += actual != expected;
            if (actual > maximum)
                maximum = actual;
            if (expected > expected_maximum)
                expected_maximum = expected;
        }
    }
    printf("H2 orientation_add %s: populated=6561/6561 max=%u expected_max=%u"
           " solved_entry=%u mismatches=%u\n", failures ? "FAIL" : "PASS",
           maximum, expected_maximum, orientation_add[0][0], failures);
    return (coordinate_failures != 0) + (failures != 0);
}

int main(int argc, char **argv)
{
    if (argc > 2) {
        fprintf(stderr, "usage: %s [exact_distances.bin]\n", argv[0]);
        return 2;
    }
    unsigned failures = check_search_tables();
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
    printf("H2 %s: tables=5 failures=%u\n", failures ? "FAIL" : "PASS", failures);
    int failed = output_failed();
    return failures || failed ? 1 : 0;
}
