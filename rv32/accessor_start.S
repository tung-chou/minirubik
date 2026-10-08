/* Ripes target gate result: a0=status, a1/a2=checked counts,
 * a3=failed coordinate, a4=pattern/face, a5=actual, a6=expected.
 */
    .file "accessor_start.S"
    .option norvc
    .option norelax
    .section .text.start,"ax",@progbits
    .globl _start
_start:
    lui sp, 0x100
    call accessor_gate_run
    la t0, gate_distance_checks
    lw a1, 0(t0)
    la t0, gate_transition_checks
    lw a2, 0(t0)
    la t0, gate_coordinate
    lw a3, 0(t0)
    la t0, gate_selector
    lw a4, 0(t0)
    la t0, gate_actual
    lw a5, 0(t0)
    la t0, gate_expected
    lw a6, 0(t0)
    li a7, 10
    ecall
.Lhalt:
    j .Lhalt
