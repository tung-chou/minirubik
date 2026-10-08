#include "gate_common.h"

int main(int argc, char **argv)
{
    if (argc > 2) {
        fprintf(stderr, "usage: %s [exact_distances.bin]\n", argv[0]);
        return 2;
    }
    uint8_t *distance = load_distances(argc == 2 ? argv[1] : "exact_distances.bin");
    if (!distance)
        return 1;
    /* Certify d(s) before using it as an oracle. */
    if (!check_oracle(distance)) {
        free(distance);
        return 1;
    }
    uint32_t failures = 0;
    unsigned maximum = 0;
    for (uint32_t rank = 0; rank < STATES; ++rank) {
        state_t state;
        unrank_state(rank, &state);
        unsigned h = heuristic(&state); /* The actual search heuristic. */
        if (h > maximum)
            maximum = h;
        if (h > distance[rank]) {
            ++failures;
            if (failures <= 20)
                printf("H1 FAIL rank=%" PRIu32 " h=%u d=%u\n",
                       rank, h, distance[rank]);
        }
    }
    printf("H1 %s: checked=%u admissible=%" PRIu32
           " violations=%" PRIu32 " max_h=%u\n",
           failures ? "FAIL" : "PASS", (unsigned) STATES,
           (uint32_t) STATES - failures, failures, maximum);
    free(distance);
    int failed = output_failed();
    return failures || failed ? 1 : 0;
}
