/* Renderer/CLI compiled out. Patch only .bench_input between Ripes runs. */
#define MINIRUBIK_CORE_ONLY
#include "../ida_solver.c"

volatile state_t bench_input __attribute__((section(".bench_input"))) = {
    {1, 0, 2, 3, 4, 5, 6}, {0}
};
uint8_t bench_path[MAX_DEPTH];

int bench_run(void)
{
    state_t state = bench_input;
    return solve(state, bench_path);
}
