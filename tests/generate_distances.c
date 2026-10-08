/* Reuse the actual BFS implementation, rather than maintaining a second BFS. */
#define main bfs_cli_main
#include "../solver.c"
#undef main

#include <inttypes.h>

enum { EXACT_DIAMETER = 11 };

/* build_table gives one move along a shortest path. Memoize the lengths of
 * those paths: each previously unknown state is assigned a distance once.
 */
static uint8_t *exact_distances(const uint8_t *table)
{
    uint8_t *distance = malloc(STATES);
    if (!distance)
        return NULL;
    memset(distance, UINT8_MAX, STATES);
    distance[0] = 0;
    for (uint32_t rank = 1; rank < STATES; ++rank) {
        uint32_t chain[EXACT_DIAMETER];
        unsigned length = 0;
        uint32_t here = rank;
        while (distance[here] == UINT8_MAX) {
            if (length == EXACT_DIAMETER || table[here] >= MOVES) {
                fputs("invalid BFS path or diameter\n", stderr);
                free(distance);
                return NULL;
            }
            chain[length++] = here;
            state_t state;
            unrank_state(here, &state);
            state = apply_move(state, table[here]);
            here = rank_state(&state);
        }
        unsigned d = distance[here];
        if (d + length > EXACT_DIAMETER) {
            fputs("BFS path exceeds diameter\n", stderr);
            free(distance);
            return NULL;
        }
        while (length)
            distance[chain[--length]] = (uint8_t) ++d;
    }
    return distance;
}

int main(int argc, char **argv)
{
    if (argc > 2) {
        fprintf(stderr, "usage: %s [exact_distances.bin]\n", argv[0]);
        return 2;
    }
    const char *filename = argc == 2 ? argv[1] : "exact_distances.bin";
    uint8_t diameter;
    uint8_t *table = build_table(&diameter);
    if (!table || diameter != EXACT_DIAMETER) {
        fputs("could not build complete BFS table with diameter 11\n", stderr);
        free(table);
        return 1;
    }
    uint8_t *distance = exact_distances(table);
    free(table);
    if (!distance) {
        fputs("could not derive exact distances\n", stderr);
        return 1;
    }
    uint32_t histogram[EXACT_DIAMETER + 1] = {0};
    for (uint32_t rank = 0; rank < STATES; ++rank)
        ++histogram[distance[rank]];

    /* Raw bytes: byte r is the shortest HTM distance of unrank_state(r).
     * There is no header, padding, or byte-order dependency.
     */
    FILE *file = fopen(filename, "wb");
    if (!file) {
        perror(filename);
        free(distance);
        return 1;
    }
    int failed = fwrite(distance, 1, STATES, file) != STATES;
    if (fclose(file) != 0)
        failed = 1;
    free(distance);
    if (failed) {
        fprintf(stderr, "could not write complete distance file: %s\n", filename);
        return 1;
    }
    printf("Wrote %u distances (%u bytes) to %s; diameter %u\n",
           (unsigned) STATES, (unsigned) STATES, filename, diameter);
    for (unsigned d = 0; d <= EXACT_DIAMETER; ++d)
        printf("distance %2u: %" PRIu32 " states\n", d, histogram[d]);
    return output_failed();
}
