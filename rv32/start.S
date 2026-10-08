/* Ripes entry: edit asm_input in memory or patch it using check_asm.py.
 * ASM_PRINT selects solution output; the benchmark build omits all printing.
 */
    .file "start.S"
    .option norvc
    .option norelax
    .section .text.start,"ax",@progbits
    .globl _start
_start:
    lui sp, 0x100
    la a0, asm_input
    la a1, asm_path
    call asm_solve_text
#ifdef ASM_PRINT
    mv s0, a0
    bltz s0, .Lerror
    li s1, 0
    la s2, asm_path
.Lprint_loop:
    beq s1, s0, .Lnewline
    beqz s1, .Lprint_move
    li a0, 32
    li a7, 11
    ecall
.Lprint_move:
    lbu t0, 0(s2)
    slli t0, t0, 2
    la a0, asm_move_names
    add a0, a0, t0
    call asm_print_string
    addi s2, s2, 1
    addi s1, s1, 1
    j .Lprint_loop
.Lnewline:
    li a0, 10
    li a7, 11
    ecall
    j .Lprint_done
.Lerror:
    la a0, asm_invalid_message
    call asm_print_string
.Lprint_done:
    mv a0, s0
#endif
    /* Keep the signed result in a0 for --regs; Ripes ecall 10 exits with 0. */
    li a7, 10
    ecall

#ifdef ASM_PRINT
/* Ripes' print-string ecall forwards its trailing NUL to captured stdout.
 * Emit characters individually to keep solution output identical to the C CLI.
 */
asm_print_string:
    mv t6, a0
.Lprint_character:
    lbu a0, 0(t6)
    beqz a0, .Lprint_string_done
    li a7, 11
    ecall
    addi t6, t6, 1
    j .Lprint_character
.Lprint_string_done:
    ret
#endif

#ifdef ASM_PRINT
    .section .rodata,"a",@progbits
asm_move_names:
    .asciz "R"
    .balign 4
    .asciz "R2"
    .balign 4
    .asciz "R'"
    .balign 4
    .asciz "B"
    .balign 4
    .asciz "B2"
    .balign 4
    .asciz "B'"
    .balign 4
    .asciz "D"
    .balign 4
    .asciz "D2"
    .balign 4
    .asciz "D'"
asm_invalid_message:
    .asciz "invalid input or search failure\n"
#endif
    .section .bench_input,"aw",@progbits
    .globl asm_input
asm_input:
    .asciz "21345671111111"
    .zero 17                         /* 32-byte patch area for invalid inputs */
    .section .bss,"aw",@nobits
    .globl asm_path
asm_path:
    .zero 11
