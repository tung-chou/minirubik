#ifndef MINIRUBIK_ASM_SOLVER_H
#define MINIRUBIK_ASM_SOLVER_H

#include <stdint.h>

enum { ASM_MAX_DEPTH = 11 };
typedef struct {
    uint8_t p[7], o[7];
} asm_state_t;
typedef struct {
    uint32_t a, b;
} asm_coordinate_pair_t;

/* text must be readable and NUL-terminated; path holds eleven writable bytes.
 * Returns a verified length 0..11, -2 for invalid input, -1 for search failure,
 * or -3 if concrete solution replay fails.
 */
int asm_solve_text(const char *text, uint8_t path[ASM_MAX_DEPTH]);
int asm_parse_state(const char *text, asm_state_t *state);

/* Replay a path on a copy of a valid state; return 1 iff the result is solved.
 * Length must be 0..11, move IDs 0..8. Invalid length/IDs return 0.
 */
int asm_verify_solution(const asm_state_t *state, const uint8_t *path, unsigned length);

/* The following entries require a valid normalized state / abstract coordinate.
 * Cubies are 0..6, twists 0..2, and the twist sum must be divisible by three.
 */
int asm_solve(const asm_state_t *state, uint8_t path[ASM_MAX_DEPTH]);
asm_coordinate_pair_t asm_coordinates(const asm_state_t *state);
uint32_t asm_turn_coordinate(uint32_t coordinate, unsigned face);
unsigned asm_coordinate_distance(uint32_t coordinate, unsigned pattern);

#endif
