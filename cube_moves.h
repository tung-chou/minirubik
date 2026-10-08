#ifndef MINIRUBIK_CUBE_MOVES_H
#define MINIRUBIK_CUBE_MOVES_H

#include <stdint.h>

/* Each destination takes a cubie from source[face][destination]. */
static const uint8_t source[3][7] = {
    {1, 4, 2, 0, 3, 5, 6},
    {0, 1, 2, 4, 5, 6, 3},
    {0, 2, 5, 3, 1, 4, 6},
};
static const uint8_t twist[3][7] = {
    {1, 2, 0, 2, 1, 0, 0},
    {0, 0, 0, 1, 2, 1, 2},
    {0, 0, 0, 0, 0, 0, 0},
};

#endif
