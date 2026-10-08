/* Host-only operation counts. The RV32 benchmark does not include counters. */
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static uint64_t visits, expansions;
#define IDA_VISIT() (++visits)
#define IDA_EXPAND() (++expansions)
#define main ida_cli_main
#include "../ida_solver.c"
#undef main

int main(int argc, char **argv)
{
    if (argc > 3) {
        fprintf(stderr, "usage: %s [exact_distances.bin [counts.csv]]\n", argv[0]);
        return 2;
    }
    const char *filename = argc >= 2 ? argv[1] : "exact_distances.bin";
    FILE *file = fopen(filename, "rb");
    if (!file) {
        perror(filename);
        return 1;
    }
    FILE *csv = argc == 3 ? fopen(argv[2], "w") : NULL;
    if (argc == 3 && !csv) {
        perror(argv[2]);
        fclose(file);
        return 1;
    }
    if (csv)
        fputs("rank,visits,expansions\n", csv);
    uint32_t tested = 0, worst_rank = 0, worst_charge_rank = 0;
    uint64_t maximum = 0, total = 0, total_expansions = 0, maximum_charge = 0;
    for (uint32_t rank = 0; rank < STATES; ++rank) {
        int d = fgetc(file);
        if (d == EOF) {
            fputs("incomplete exact-distance file\n", stderr);
            fclose(file);
            return 1;
        }
        if (d != MAX_DEPTH)
            continue;
        state_t state;
        unrank_state(rank, &state);
        uint8_t path[MAX_DEPTH];
        visits = expansions = 0;
        if (solve(state, path) != MAX_DEPTH) {
            fprintf(stderr, "wrong solution length at rank %" PRIu32 "\n", rank);
            fclose(file);
            return 1;
        }
        ++tested;
        if (csv)
            fprintf(csv, "%" PRIu32 ",%" PRIu64 ",%" PRIu64 "\n",
                    rank, visits, expansions);
        total += visits;
        total_expansions += expansions;
        uint64_t charge = visits + 5 * expansions;
        if (charge > maximum_charge) {
            maximum_charge = charge;
            worst_charge_rank = rank;
        }
        if (visits > maximum) {
            maximum = visits;
            worst_rank = rank;
        }
    }
    fclose(file);
    if (csv && fclose(csv)) {
        perror(argv[2]);
        return 1;
    }
    printf("distance11=%" PRIu32 " visits=%" PRIu64 " expansions=%" PRIu64
           " max_visits=%" PRIu64 " worst_rank=%" PRIu32
           " max_charge=%" PRIu64 " worst_charge_rank=%" PRIu32 "\n",
           tested, total, total_expansions, maximum, worst_rank,
           maximum_charge, worst_charge_rank);
    return output_failed();
}
