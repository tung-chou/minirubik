/* Test-only negative/positive replay cases, with input-preservation checks.
 * Exit registers: a0=0 PASS / 1 FAIL; a1=cases passed; a2=actual result.
 */
    .file "verification_gate.S"
    .option norvc
    .option norelax
    .section .text.start,"ax",@progbits
    .globl _start
_start:
    lui sp, 0x100
    addi sp, sp, -32
    la s0, cases
    li s1, 13
    li s2, 0
.Lcase:
    lw a0, 0(s0)
    mv t0, a0
    mv t1, sp
    li t2, 14
.Lsave_input:
    lbu t3, 0(t0)
    sb t3, 0(t1)
    addi t0, t0, 1
    addi t1, t1, 1
    addi t2, t2, -1
    bnez t2, .Lsave_input
    lw a1, 4(s0)
    lw a2, 8(s0)
    call asm_verify_solution
    mv a2, a0
    lw t0, 12(s0)
    bne a0, t0, .Lfailed
    lui t0, 0x100
    addi t0, t0, -32
    bne sp, t0, .Lfailed
    lw t0, 0(s0)
    mv t1, sp
    li t2, 14
.Lcheck_input:
    lbu t3, 0(t0)
    lbu t4, 0(t1)
    bne t3, t4, .Lfailed
    addi t0, t0, 1
    addi t1, t1, 1
    addi t2, t2, -1
    bnez t2, .Lcheck_input
    addi s0, s0, 16
    addi s2, s2, 1
    bltu s2, s1, .Lcase
    li a0, 0
    j .Lexit
.Lfailed:
    li a0, 1
.Lexit:
    mv a1, s2
    addi sp, sp, 32
    li a7, 10
    ecall
.Lhalt:
    j .Lhalt

    .section .rodata,"a",@progbits
solved:
    .byte 0,1,2,3,4,5,6, 0,0,0,0,0,0,0
scramble:
    .byte 1,4,2,0,3,5,6, 1,2,0,2,1,0,0
hard:
    .byte 1,0,2,3,4,5,6, 0,0,0,0,0,0,0
r:
    .byte 0
r2:
    .byte 1
r_inverse:
    .byte 2
round_trip:
    .byte 0,2
bad_id:
    .byte 9
bad_byte:
    .byte 255
hard_path:
    .byte 0,5,7,2,3,2,5,0,7,0,3
bad_hard_path:
    .byte 1,5,7,2,3,2,5,0,7,0,3
    .balign 4
cases:
    .word solved, r, 0, 1
    .word scramble, r, 0, 0
    .word scramble, r_inverse, 1, 1
    .word scramble, r, 1, 0
    .word scramble, r2, 1, 0
    .word solved, r, 1, 0
    .word solved, round_trip, 2, 1
    .word solved, bad_id, 1, 0
    .word solved, bad_byte, 1, 0
    .word solved, r, 12, 0
    .word solved, r, -1, 0
    .word hard, hard_path, 11, 1
    .word hard, bad_hard_path, 11, 0
