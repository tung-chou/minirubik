#include "gate_common.h"

static int parse_rank(const char *text, uint32_t *value)
{
    if (!*text)
        return 0;
    for (const char *p = text; *p; ++p)
        if (*p < '0' || *p > '9')
            return 0;
    errno = 0;
    char *end;
    unsigned long parsed = strtoul(text, &end, 10);
    if (errno || *end || parsed > STATES)
        return 0;
    *value = (uint32_t) parsed;
    return 1;
}

static void print_state(const state_t *state)
{
    for (unsigned i = 0; i < CUBIES; ++i)
        putchar('1' + state->p[i]);
    for (unsigned i = 0; i < CUBIES; ++i)
        putchar('1' + state->o[i]);
}

int main(int argc, char **argv)
{
    int table_only = argc >= 2 && !strcmp(argv[1], "--check-table");
    const char *filename = "exact_distances.bin";
    uint32_t start = 0, count = STATES;
    if (table_only) {
        if (argc > 3)
            goto usage;
        if (argc == 3)
            filename = argv[2];
    } else {
        if (argc > 4)
            goto usage;
        if (argc >= 2)
            filename = argv[1];
        if (argc >= 3 && (!parse_rank(argv[2], &start) || start >= STATES))
            goto usage;
        count = STATES - start;
        if (argc == 4 && (!parse_rank(argv[3], &count) || !count ||
                          count > STATES - start))
            goto usage;
    }

    uint8_t *distance = load_distances(filename);
    if (!distance)
        return 1;
    if (!check_pdbs() || !check_oracle(distance)) {
        free(distance);
        return 1;
    }
    if (table_only) {
        puts("TABLE PASS: all 3674160 exact distances certified; IDA* not run");
        free(distance);
        return output_failed();
    }

    fprintf(stderr, "Checking IDA* ranks [%" PRIu32 ", %" PRIu32 ")\n",
            start, start + count);
    uint32_t checked[MAX_DEPTH + 1] = {0}, errors[MAX_DEPTH + 1] = {0};
    uint32_t failures = 0;
    time_t last_progress = time(NULL);
    for (uint32_t rank = start; rank < start + count; ++rank) {
        state_t state;
        unrank_state(rank, &state);
        uint8_t path[MAX_DEPTH];
        /* No oracle-dependent bound or shortcut: test the real solve(). */
        int length = solve(state, path);
        unsigned expected = distance[rank];
        ++checked[expected];
        int path_ok = length >= 0 && length <= MAX_DEPTH;
        state_t result = state;
        if (path_ok) {
            for (int i = 0; i < length; ++i) {
                if (path[i] >= MOVES) {
                    path_ok = 0;
                    break;
                }
                result = reference_move(result, path[i]);
            }
            path_ok = path_ok && valid(&result) && rank_state(&result) == 0;
        }
        if (!path_ok || length != (int) expected) {
            ++failures;
            ++errors[expected];
            if (failures <= 20) {
                printf("FAIL rank=%" PRIu32 " state=", rank);
                print_state(&state);
                printf(" expected=%u actual=%d path=%s\n", expected, length,
                       path_ok ? "solved" : "invalid/unsolved");
            }
        }
        time_t now = time(NULL);
        if (difftime(now, last_progress) >= 5 || rank + 1U == start + count) {
            fprintf(stderr, "Checked %" PRIu32 "/%" PRIu32
                    "; mismatches=%" PRIu32 "; next rank=%" PRIu32 "\n",
                    rank - start + 1U, count, failures, rank + 1U);
            last_progress = now;
        }
    }
    printf("%s %s: checked=%" PRIu32 "/%u matched=%" PRIu32
           " mismatches=%" PRIu32 " ranks=[%" PRIu32 ",%" PRIu32 ")\n",
           start == 0 && count == STATES ? "FULL" : "PARTIAL",
           failures ? "FAIL" : "PASS", count, (unsigned) STATES,
           count - failures, failures, start, start + count);
    for (unsigned d = 0; d <= MAX_DEPTH; ++d)
        printf("distance %2u: checked=%" PRIu32 " mismatches=%" PRIu32 "\n",
               d, checked[d], errors[d]);
    free(distance);
    int failed = output_failed();
    return failures || failed ? 1 : 0;

usage:
    fprintf(stderr, "usage: %s [exact_distances.bin [start_rank [count]]]\n"
            "       %s --check-table [exact_distances.bin]\n", argv[0], argv[0]);
    return 2;
}
