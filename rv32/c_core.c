/* Export the actual Stage 3 solve() for RV32I GCC -O2, without a copy wrapper.
 * ILP32 passes this 14-byte aggregate indirectly in a0 and path in a1, exactly
 * matching the common assembly harness. The parameter is not modified by solve.
 * 'used' retains the static function; the assembler directive exports its name.
 * Only linkage/name change. The solver algorithm and representation are intact.
 */
#define MINIRUBIK_CORE_ONLY
#define solve __attribute__((used)) c_solve
#include "../ida_solver.c"
#undef solve

typedef char state_size_is_14[(sizeof(state_t) == 14) ? 1 : -1];
__asm__(".globl c_solve");
