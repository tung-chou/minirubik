    .section .text.start,"ax",@progbits
    .globl _start
_start:
    lui sp, 0x100
    call bench_run
    /* a0 retains the solution length for Ripes --regs. */
    li a7, 10
    ecall
