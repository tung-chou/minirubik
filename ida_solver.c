#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "pdb.h"
#include "pdb_data.h"

enum {
    CUBIES = 7,
    PERMUTATIONS = 5040,
    ORIENTATIONS = 729,
    STATES = PERMUTATIONS * ORIENTATIONS,
    MOVES = 9,
    /* Maximum shortest-path length in the half-turn metric. */
    MAX_DEPTH = 11
};

typedef struct {
    uint8_t p[CUBIES], o[CUBIES];
} state_t;

static const char *const move_names[MOVES] = {"R",  "R2", "R'", "B", "B2",
                                              "B'", "D",  "D2", "D'"};
static const uint8_t inverse_move[MOVES] = {2, 1, 0, 5, 4, 3, 8, 7, 6};

/* The three quarter-turns preserve the fixed front-upper-left corner. */
static state_t quarter_turn(state_t state, uint8_t face)
{
    state_t result;

    for (uint8_t i = 0; i < CUBIES; ++i) {
        uint8_t from = source[face][i];
        result.p[i] = state.p[from];
        result.o[i] = (uint8_t) ((state.o[from] + twist[face][i]) % 3U);
    }
    return result;
}

static state_t apply_move(state_t state, uint8_t move)
{
    uint8_t turns = (uint8_t) (move % 3U + 1U);
    for (uint8_t i = 0; i < turns; ++i)
        state = quarter_turn(state, (uint8_t) (move / 3U));
    return state;
}

static uint32_t rank_state(const state_t *state)
{
    uint32_t p = 0, o = 0;
    for (uint8_t i = 0; i < CUBIES; ++i) {
        uint8_t smaller = 0;

        for (uint8_t j = (uint8_t) (i + 1U); j < CUBIES; ++j)
            if (state->p[j] < state->p[i])
                ++smaller;
        p = p * (CUBIES - i) + smaller;
    }

    for (uint8_t i = 0; i < 6; ++i)
        o = o * 3U + state->o[i];
    return p * ORIENTATIONS + o;
}

/*@ requires \valid(state); requires rank < STATES; assigns *state; */
static void unrank_state(uint32_t rank, state_t *state)
{
    uint8_t available[CUBIES] = {0, 1, 2, 3, 4, 5, 6};
    uint32_t p = rank / ORIENTATIONS, o = rank % ORIENTATIONS, f = 720;
    uint8_t sum = 0;
    for (uint8_t i = 0; i < CUBIES; ++i) {
        uint8_t q = (uint8_t) (p / f);
        p %= f;
        state->p[i] = available[q];
        for (uint8_t j = q; j + 1U < (unsigned) CUBIES - i; ++j)
            available[j] = available[j + 1U];
        if (i < 5)
            f /= 6U - i;
    }
    for (uint8_t i = 6; i-- > 0;) {
        state->o[i] = (uint8_t) (o % 3U);
        sum = (uint8_t) (sum + state->o[i]);
        o /= 3U;
    }
    state->o[6] = (uint8_t) ((3U - sum % 3U) % 3U);
}

static int valid(const state_t *state)
{
    uint8_t sum = 0;
    for (uint8_t i = 0; i < CUBIES; ++i) {
        if (state->p[i] >= CUBIES || state->o[i] >= 3)
            return 0;
        /*@ loop invariant 0 <= j <= i;
            loop invariant \forall integer k; 0 <= k < j ==>
              state->p[k] != state->p[i];
            loop assigns j;
            loop variant i - j;
        */
        for (uint8_t j = 0; j < i; ++j)
            if (state->p[j] == state->p[i])
                return 0;
        sum = (uint8_t) (sum + state->o[i]);
    }
    return sum % 3U == 0;
}

static int parse_state(const char *input, state_t *state)
{
    for (int i = 0; i < 14; ++i) {
        int limit = i < 7 ? 7 : 3;
        if (input[i] < '1' || input[i] > '0' + limit)
            return 0;
        (i < 7 ? state->p : state->o)[i % 7] = (uint8_t) (input[i] - '1');
    }
    return input[14] == '\0' && valid(state);
}

/* stdout is fully buffered off a terminal, so a write error surfaces at the
 * flush, not at the printf that queued the bytes. Every exit path that has
 * produced output goes through here.
 */
static int output_failed(void)
{
    return fflush(stdout) != 0 || ferror(stdout);
}

static unsigned heuristic(const state_t *state);

static int self_test(void)
{
    const state_t solved = {{0, 1, 2, 3, 4, 5, 6}, {0}};
    state_t state;
    if (sizeof pdb_tables != PDB_COUNT * PDB_BYTES || heuristic(&solved) != 0)
        return 0;
    for (uint8_t move = 0; move < MOVES; ++move) {
        state = solved;
        state = apply_move(state, move);
        if (heuristic(&state) > 1)
            return 0;
        state = apply_move(state, inverse_move[move]);
        if (memcmp(&solved, &state, sizeof solved))
            return 0;
    }
    for (uint32_t rank = 0; rank < STATES; ++rank) {
        unrank_state(rank, &state);
        if (!valid(&state) || rank_state(&state) != rank)
            return 0;
    }
    for (unsigned pattern = 0; pattern < PDB_COUNT; ++pattern) {
        pdb_state_t goal = pdb_goal(pattern);
        uint32_t goal_rank = pdb_rank(&goal);
        for (uint32_t rank = 0; rank < PDB_STATES; ++rank) {
            pdb_state_t abstract = pdb_unrank(rank);
            unsigned distance = pdb_distance(pdb_tables[pattern], rank);
            if (pdb_rank(&abstract) != rank || distance > MAX_DEPTH ||
                (distance == 0) != (rank == goal_rank))
                return 0;
        }
    }
    return 1;
}

/* Project by cubie identity: track where each selected cubie is, along
 * with its current twist. Forgetting other cubies relaxes the goal, so each
 * PDB distance is a lower bound. Use max, never the sum of overlapping PDBs.
 */
static unsigned heuristic(const state_t *state)
{
    uint8_t position[CUBIES];
    for (uint8_t i = 0; i < CUBIES; ++i)
        position[state->p[i]] = i;
    unsigned best = 0;
    for (unsigned pattern = 0; pattern < PDB_COUNT; ++pattern) {
        pdb_state_t abstract;
        for (unsigned i = 0; i < PDB_CORNERS; ++i) {
            uint8_t at = position[pdb_corners[pattern][i]];
            abstract.pos[i] = at;
            abstract.ori[i] = state->o[at];
        }
        unsigned distance = pdb_distance(pdb_tables[pattern], pdb_rank(&abstract));
        if (distance > best)
            best = distance;
    }
    return best;
}

enum { SEARCH_FOUND = -1 };

/* Return SEARCH_FOUND, or the smallest f=g+h that exceeded the threshold.
 * g is the actual search depth. path has room for MAX_DEPTH moves.
 */
static int ida_search(state_t state, unsigned g, unsigned bound,
                      uint8_t previous_face, uint8_t path[MAX_DEPTH],
                      int *solution_length)
{
    unsigned h = heuristic(&state);
    unsigned f = g + h;
    if (f > bound)
        return (int) f;
    /* Both abstract goals together constrain all seven cubies.
     */
    if (h == 0) {
        *solution_length = (int) g;
        return SEARCH_FOUND;
    }

    int next_bound = MAX_DEPTH + 1;
    for (uint8_t face = 0; face < 3; ++face) {
        /* Consecutive turns of one face combine or cancel; skip them. */
        if (face == previous_face)
            continue;
        state_t next = state;
        for (uint8_t turn = 0; turn < 3; ++turn) {
            next = quarter_turn(next, face);
            path[g] = (uint8_t) (face * 3U + turn);
            int result = ida_search(next, g + 1U, bound, face, path,
                                    solution_length);
            if (result == SEARCH_FOUND)
                return SEARCH_FOUND;
            if (result < next_bound)
                next_bound = result;
        }
    }
    return next_bound;
}

static int solve(state_t state, uint8_t path[MAX_DEPTH])
{
    unsigned bound = heuristic(&state);
    while (bound <= MAX_DEPTH) {
        int length = -1;
        int result = ida_search(state, 0, bound, 3, path, &length);
        if (result == SEARCH_FOUND)
            return length;
        bound = (unsigned) result;
    }
    return -1;
}

int main(int argc, char **argv)
{
    state_t state;
    if (argc == 2 && !strcmp(argv[1], "--self-test")) {
        if (!self_test()) {
            fputs("self-test failed\n", stderr);
            return 1;
        }
        puts("3674160 rank/unrank checks passed; move inverses and packed PDB checks passed");
        return output_failed();
    }
    if (argc != 2 || !parse_state(argv[1], &state)) {
        /* C99 5.1.2.2.1 lets argv[0] be null when argc is 0. */
        fprintf(stderr, "usage: %s PPPPPPPOOOOOOO\n",
                argc > 0 && argv[0] ? argv[0] : "solver");
        return 2;
    }
    uint8_t path[MAX_DEPTH];
    int length = solve(state, path);
    if (length < 0) {
        fputs("no solution within depth limit\n", stderr);
        return 1;
    }
    const char *separator = "";
    for (int i = 0; i < length; ++i) {
        printf("%s%s", separator, move_names[path[i]]);
        separator = " ";
    }
    putchar('\n');
    return output_failed();
}
