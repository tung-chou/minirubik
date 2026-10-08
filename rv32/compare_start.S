/* Identical normalized-state measurement harness for GCC and assembly.
 * a0 = length; a1/a2/a3 = little-endian packed path; a5 = ABI error (0=PASS).
 * Input transport, ABI probes and result packing are included in both counts.
 * There is no renderer or program output. --regs retrieves the actual path.
 */
    .file "compare_start.S"
    .option norvc
    .option norelax
    .section .text.start,"ax",@progbits
    .globl _start
_start:
    lui sp, 0x100
    li t0, 0x5a55a55a
    sw t0, -2048(sp)
    li s0, 101
    li s1, 102
    li s2, 103
    li s3, 104
    li s4, 105
    li s5, 106
    li s6, 107
    li s7, 108
    li s8, 109
    li s9, 110
    li s10, 111
    li s11, 112
    la a0, compare_input
    la a1, compare_path
#ifdef BENCH_C
    call c_solve
#else
    call asm_solve
#endif
    li a5, 0
    .macro CHECK_S reg, expected
    li t0, \expected
    bne \reg, t0, .Labi_failed
    .endm
    CHECK_S s0, 101
    CHECK_S s1, 102
    CHECK_S s2, 103
    CHECK_S s3, 104
    CHECK_S s4, 105
    CHECK_S s5, 106
    CHECK_S s6, 107
    CHECK_S s7, 108
    CHECK_S s8, 109
    CHECK_S s9, 110
    CHECK_S s10, 111
    CHECK_S s11, 112
    lui t1, 0x100
    bne sp, t1, .Labi_failed
    lw t0, -2048(t1)
    li t1, 0x5a55a55a
    bne t0, t1, .Labi_failed
    j .Lpack_path
.Labi_failed:
    li a5, 1
.Lpack_path:
    la t6, compare_path
    .macro PACK dest, offset, count
    lbu \dest, \offset(t6)
    lbu t0, (\offset+1)(t6)
    slli t0, t0, 8
    or \dest, \dest, t0
    lbu t0, (\offset+2)(t6)
    slli t0, t0, 16
    or \dest, \dest, t0
    .if \count == 4
    lbu t0, (\offset+3)(t6)
    slli t0, t0, 24
    or \dest, \dest, t0
    .endif
    .endm
    PACK a1, 0, 4
    PACK a2, 4, 4
    PACK a3, 8, 3
    li a7, 10
    ecall
.Lhalt:
    /* The ISS can step past exit before the CLI observes termination. Keep
     * any such step harmless and outside the adjacent solver's prologue.
     */
    j .Lhalt

    .section .bench_input,"aw",@progbits
    .balign 4
    .globl compare_input
compare_input:
    .byte 1,0,2,3,4,5,6,0,0,0,0,0,0,0
    .section .bss,"aw",@nobits
    .globl compare_path
compare_path:
    .zero 11
