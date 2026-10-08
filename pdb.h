#ifndef MINIRUBIK_PDB_H
#define MINIRUBIK_PDB_H

#include "cube_moves.h"

enum {
    PDB_CORNERS = 4,
    PDB_PERMUTATIONS = 840, /* P(7,4) */
    PDB_ORIENTATIONS = 81, /* 3^4, no orientation-sum constraint */
    PDB_STATES = PDB_PERMUTATIONS * PDB_ORIENTATIONS,
    PDB_BYTES = PDB_STATES / 2,
    PDB_COUNT = 2
};

/* Cubie identities, zero-based. Their union is all seven movable corners. */
static const uint8_t pdb_corners[PDB_COUNT][PDB_CORNERS] = {
    {0, 1, 2, 3}, {3, 4, 5, 6}
};

typedef struct {
    /* pos[i] and ori[i] describe the i-th tracked cubie, not a fixed seat. */
    uint8_t pos[PDB_CORNERS], ori[PDB_CORNERS];
} pdb_state_t;

static inline uint32_t pdb_rank(const pdb_state_t *state)
{
    uint32_t permutation = 0, orientation = 0;
    for (unsigned i = 0; i < PDB_CORNERS; ++i) {
        unsigned digit = state->pos[i];
        for (unsigned j = 0; j < i; ++j)
            if (state->pos[j] < state->pos[i])
                --digit;
        permutation = permutation * (7U - i) + digit;
        orientation = orientation * 3U + state->ori[i];
    }
    return permutation * PDB_ORIENTATIONS + orientation;
}

static inline pdb_state_t pdb_unrank(uint32_t rank)
{
    pdb_state_t state;
    uint8_t available[7] = {0, 1, 2, 3, 4, 5, 6};
    uint32_t permutation = rank / PDB_ORIENTATIONS;
    uint32_t orientation = rank % PDB_ORIENTATIONS;
    uint8_t digits[PDB_CORNERS];
    for (unsigned i = PDB_CORNERS; i-- > 0;) {
        digits[i] = (uint8_t) (permutation % (7U - i));
        permutation /= 7U - i;
        state.ori[i] = (uint8_t) (orientation % 3U);
        orientation /= 3U;
    }
    for (unsigned i = 0; i < PDB_CORNERS; ++i) {
        unsigned digit = digits[i];
        state.pos[i] = available[digit];
        for (unsigned j = digit; j + 1U < 7U - i; ++j)
            available[j] = available[j + 1U];
    }
    return state;
}

static inline pdb_state_t pdb_goal(unsigned pattern)
{
    pdb_state_t state;
    for (unsigned i = 0; i < PDB_CORNERS; ++i) {
        state.pos[i] = pdb_corners[pattern][i];
        state.ori[i] = 0;
    }
    return state;
}

static inline pdb_state_t pdb_quarter_turn(pdb_state_t state, unsigned face)
{
    for (unsigned i = 0; i < PDB_CORNERS; ++i) {
        uint8_t destination = 0;
        while (source[face][destination] != state.pos[i])
            ++destination;
        state.pos[i] = destination;
        state.ori[i] = (uint8_t) ((state.ori[i] + twist[face][destination]) % 3U);
    }
    return state;
}

/* Even abstract ranks use the low nibble, odd ranks the high nibble. */
static inline uint8_t pdb_distance(const uint8_t packed[PDB_BYTES], uint32_t rank)
{
    return (uint8_t) ((packed[rank / 2U] >> ((rank % 2U) * 4U)) & 15U);
}

#endif
