/* Target-side H2/H4 port checks. Not linked into solver/benchmark binaries.
 * Host H2/H4 independently certify the table bytes; this gate exercises every
 * abstract coordinate through the handwritten accessors on the actual target.
 * Expected twists are computed with trits, not the orientation_add lookup.
 */
#include <stdint.h>
#include "solver.h"

extern const uint8_t asm_pdb_a[34020], asm_pdb_b[34020];
extern const uint32_t asm_coordinate_turn[3][840];
volatile uint32_t gate_distance_checks, gate_transition_checks;
volatile uint32_t gate_coordinate, gate_selector, gate_actual, gate_expected;

static int fail(unsigned coordinate, unsigned selector, unsigned actual,
                unsigned expected, int status)
{
    gate_coordinate = coordinate;
    gate_selector = selector;
    gate_actual = actual;
    gate_expected = expected;
    return status;
}

int accessor_gate_run(void)
{
    uint8_t digits[81][4];
    const unsigned weights[4] = {27, 9, 3, 1};
    for (unsigned rank = 0; rank < 81; ++rank) {
        unsigned remainder = rank;
        for (unsigned i = 0; i < 4; ++i) {
            unsigned q = 0;
            while (remainder >= weights[i]) {
                remainder -= weights[i];
                ++q;
            }
            digits[rank][i] = (uint8_t) q;
        }
    }
    for (unsigned pattern = 0; pattern < 2; ++pattern) {
        const uint8_t *packed = pattern ? asm_pdb_b : asm_pdb_a;
        unsigned index = 0;
        for (unsigned p = 0; p < 840; ++p) {
            for (unsigned o = 0; o < 81; ++o, ++index) {
                unsigned expected = packed[index >> 1];
                if (index & 1) expected >>= 4;
                expected &= 15;
                unsigned coordinate = p | (o << 10);
                unsigned actual = asm_coordinate_distance(coordinate, pattern);
                if (actual != expected)
                    return fail(coordinate, pattern, actual, expected, 1);
                ++gate_distance_checks;
            }
        }
    }
    for (unsigned face = 0; face < 3; ++face) {
        for (unsigned p = 0; p < 840; ++p) {
            uint32_t transition = asm_coordinate_turn[face][p];
            unsigned delta = transition >> 10;
            for (unsigned o = 0; o < 81; ++o) {
                unsigned rank = 0;
                for (unsigned i = 0; i < 4; ++i) {
                    unsigned twist = digits[o][i] + digits[delta][i];
                    if (twist >= 3) twist -= 3;
                    rank = (rank << 1) + rank + twist;
                }
                unsigned coordinate = p | (o << 10);
                unsigned expected = (transition & 1023) | (rank << 10);
                unsigned actual = asm_turn_coordinate(coordinate, face);
                if (actual != expected)
                    return fail(coordinate, face, actual, expected, 2);
                ++gate_transition_checks;
            }
        }
    }
    return 0;
}
