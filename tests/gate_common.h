#ifndef MINIRUBIK_GATE_COMMON_H
#define MINIRUBIK_GATE_COMMON_H

/* Compile the actual IDA* solve() into this gate. The exact-distance oracle
 * is never passed to solve(), ida_search(), or a search heuristic.
 */
#define main ida_cli_main
#include "../ida_solver.c"
#undef main

#include <errno.h>
#include <inttypes.h>
#include <stdlib.h>
#include <time.h>

/* An independent move model: cycles give the destination of each cubie,
 * unlike the solver's destination-to-source arrays.
 */
static inline state_t reference_move(state_t state, uint8_t move)
{
    static const uint8_t cycles[3][4] = {
        {0, 3, 4, 1}, {3, 6, 5, 4}, {1, 4, 5, 2}
    };
    static const uint8_t additions[3][4] = {
        {2, 1, 2, 1}, {2, 1, 2, 1}, {0, 0, 0, 0}
    };
    unsigned face = move / 3U;
    for (unsigned turn = 0; turn <= move % 3U; ++turn) {
        state_t next = state;
        for (unsigned i = 0; i < 4; ++i) {
            uint8_t from = cycles[face][i];
            uint8_t to = cycles[face][(i + 1U) % 4U];
            next.p[to] = state.p[from];
            next.o[to] = (uint8_t) ((state.o[from] + additions[face][i]) % 3U);
        }
        state = next;
    }
    return state;
}

/* Independently project a full state by scanning for each tracked identity. */
static inline pdb_state_t reference_project(const state_t *state, unsigned pattern)
{
    pdb_state_t result = {{0}, {0}};
    for (unsigned i = 0; i < PDB_CORNERS; ++i) {
        for (uint8_t at = 0; at < CUBIES; ++at) {
            if (state->p[at] == pdb_corners[pattern][i]) {
                result.pos[i] = at;
                result.ori[i] = state->o[at];
                break;
            }
        }
    }
    return result;
}

/* Supply the forgotten cubies and put the orientation-sum correction on an
 * untracked cubie. Every abstract state has a valid concrete representative.
 */
static inline state_t reference_complete(const pdb_state_t *abstract, unsigned pattern)
{
    state_t result;
    memset(result.p, UINT8_MAX, sizeof result.p);
    memset(result.o, 0, sizeof result.o);
    unsigned used = 0, sum = 0;
    for (unsigned i = 0; i < PDB_CORNERS; ++i) {
        uint8_t cubie = pdb_corners[pattern][i], at = abstract->pos[i];
        result.p[at] = cubie;
        result.o[at] = abstract->ori[i];
        used |= 1U << cubie;
        sum += abstract->ori[i];
    }
    uint8_t cubie = 0, last_untracked = 0;
    for (uint8_t at = 0; at < CUBIES; ++at) {
        if (result.p[at] != UINT8_MAX)
            continue;
        while (used & (1U << cubie))
            ++cubie;
        result.p[at] = cubie;
        used |= 1U << cubie;
        last_untracked = at;
    }
    result.o[last_untracked] = (uint8_t) ((3U - sum % 3U) % 3U);
    return result;
}

static inline int check_pdbs(void)
{
    for (unsigned pattern = 0; pattern < PDB_COUNT; ++pattern) {
        pdb_state_t goal = pdb_goal(pattern);
        uint32_t goal_rank = pdb_rank(&goal);
        for (uint32_t rank = 0; rank < PDB_STATES; ++rank) {
            pdb_state_t abstract = pdb_unrank(rank);
            state_t state = reference_complete(&abstract, pattern);
            pdb_state_t projected = reference_project(&state, pattern);
            unsigned d = pdb_distance(pdb_tables[pattern], rank);
            if (!valid(&state) || pdb_rank(&abstract) != rank ||
                pdb_rank(&projected) != rank || d > MAX_DEPTH ||
                (d == 0) != (rank == goal_rank)) {
                fprintf(stderr, "invalid PDB %c entry at rank %" PRIu32 "\n",
                        'A' + pattern, rank);
                return 0;
            }
            unsigned minimum = UINT8_MAX;
            for (uint8_t move = 0; move < MOVES; ++move) {
                state_t next = reference_move(state, move);
                projected = reference_project(&next, pattern);
                unsigned child = pdb_distance(pdb_tables[pattern], pdb_rank(&projected));
                if (child < minimum)
                    minimum = child;
            }
            if ((rank != goal_rank && d != minimum + 1U) ||
                (rank == goal_rank && minimum != 1)) {
                fprintf(stderr, "PDB %c distance mismatch at rank %" PRIu32 "\n",
                        'A' + pattern, rank);
                return 0;
            }
        }
    }
    fprintf(stderr, "Packed PDBs certified: 2 x %u abstract states\n",
            (unsigned) PDB_STATES);
    return 1;
}

static inline uint8_t *load_distances(const char *filename)
{
    FILE *file = fopen(filename, "rb");
    if (!file) {
        perror(filename);
        return NULL;
    }
    uint8_t *distance = malloc(STATES);
    if (!distance) {
        fputs("could not allocate distance table\n", stderr);
        fclose(file);
        return NULL;
    }
    int failed = fread(distance, 1, STATES, file) != STATES;
    if (fgetc(file) != EOF || ferror(file))
        failed = 1;
    if (fclose(file) != 0)
        failed = 1;
    if (failed) {
        fprintf(stderr, "%s must contain exactly %u bytes\n", filename,
                (unsigned) STATES);
        free(distance);
        return NULL;
    }
    for (uint32_t rank = 0; rank < STATES; ++rank) {
        if (distance[rank] > MAX_DEPTH || (distance[rank] == 0) != (rank == 0)) {
            fprintf(stderr, "invalid distance %u at rank %" PRIu32 "\n",
                    distance[rank], rank);
            free(distance);
            return NULL;
        }
    }
    return distance;
}

/* A complete oracle check, independent of the solver's move implementation.
 * d(0)=0, d(s)>0 otherwise, and d(s)=1+min d(neighbor) certify shortest
 * distances: descent gives a path of length d(s), and each edge can lower the
 * distance by at most one, so a shorter path is impossible.
 */
static inline int check_oracle(const uint8_t *distance)
{
    for (uint32_t rank = 0; rank < STATES; ++rank) {
        state_t state;
        unrank_state(rank, &state);
        if (!valid(&state) || rank_state(&state) != rank) {
            fprintf(stderr, "rank/unrank failed at %" PRIu32 "\n", rank);
            return 0;
        }
        unsigned minimum = UINT8_MAX;
        for (uint8_t move = 0; move < MOVES; ++move) {
            state_t next = reference_move(state, move);
            uint32_t child = rank_state(&next);
            if (distance[child] < minimum)
                minimum = distance[child];
        }
        if ((rank && distance[rank] != minimum + 1U) ||
            (!rank && minimum != 1)) {
            fprintf(stderr, "oracle mismatch at rank %" PRIu32
                    ": distance %u, minimum neighbor %u\n",
                    rank, distance[rank], minimum);
            return 0;
        }
    }
    fprintf(stderr, "Oracle certified: all %u states, all %u moves per state\n",
            (unsigned) STATES, (unsigned) MOVES);
    return 1;
}


/* Independent unpacked reference: abstract BFS using the corner-cycle model
 * above. It never calls pdb_quarter_turn(), pdb_distance(), or build_pdb().
 */
static inline uint8_t *reference_pdb(unsigned pattern)
{
    uint8_t *distance = malloc(PDB_STATES);
    uint32_t *queue = malloc((size_t) PDB_STATES * sizeof *queue);
    if (!distance || !queue) {
        fputs("could not allocate reference PDB\n", stderr);
        free(distance);
        free(queue);
        return NULL;
    }
    memset(distance, UINT8_MAX, PDB_STATES);
    pdb_state_t goal = pdb_goal(pattern);
    uint32_t goal_rank = pdb_rank(&goal);
    uint32_t head = 0, tail = 1;
    queue[0] = goal_rank;
    distance[goal_rank] = 0;
    while (head < tail) {
        uint32_t here = queue[head++];
        pdb_state_t abstract = pdb_unrank(here);
        state_t state = reference_complete(&abstract, pattern);
        for (uint8_t move = 0; move < MOVES; ++move) {
            state_t next = reference_move(state, move);
            pdb_state_t projected = reference_project(&next, pattern);
            uint32_t there = pdb_rank(&projected);
            if (distance[there] == UINT8_MAX) {
                distance[there] = (uint8_t) (distance[here] + 1U);
                queue[tail++] = there;
            }
        }
    }
    free(queue);
    if (tail != PDB_STATES) {
        fprintf(stderr, "reference PDB %c reached only %" PRIu32 " states\n",
                'A' + pattern, tail);
        free(distance);
        return NULL;
    }
    return distance;
}

#endif
