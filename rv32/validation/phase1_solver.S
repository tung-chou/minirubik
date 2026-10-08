/* Handwritten RV32I implementation of ida_solver.c. No target C or libgcc.
 * All public functions follow the ILP32 ABI. Internal rank4/coordinates return
 * the two-word aggregate in a0/a1. Every machine stack frame is 16-byte aligned.
 */
    .file "solver.S"
    .option norvc
    .option norelax
    .text

/* a0 = NUL-terminated text, a1 = writable 14-byte state; return 1/0.
 * Read sequentially so a short string is rejected at its NUL, without reading
 * beyond it. Seven unique in-range digits imply a complete permutation.
 */
    .globl asm_parse_state
    .type asm_parse_state,@function
asm_parse_state:
    li t0, 0
    li t4, 0
    li t5, 0
.Lparse_permutation:
    lbu t1, 0(a0)
    addi t1, t1, -49
    li t2, 7
    bgeu t1, t2, .Lparse_invalid
    li t3, 1
    sll t3, t3, t1
    and t2, t4, t3
    bnez t2, .Lparse_invalid
    or t4, t4, t3
    sb t1, 0(a1)
    addi a0, a0, 1
    addi a1, a1, 1
    addi t0, t0, 1
    li t2, 7
    bltu t0, t2, .Lparse_permutation
    li t0, 0
.Lparse_orientation:
    lbu t1, 0(a0)
    addi t1, t1, -49
    li t2, 3
    bgeu t1, t2, .Lparse_invalid
    add t5, t5, t1
    sb t1, 0(a1)
    addi a0, a0, 1
    addi a1, a1, 1
    addi t0, t0, 1
    li t2, 7
    bltu t0, t2, .Lparse_orientation
    lbu t1, 0(a0)
    bnez t1, .Lparse_invalid
    li t2, 3
.Lparse_modulo:
    bltu t5, t2, .Lparse_sum
    addi t5, t5, -3
    j .Lparse_modulo
.Lparse_sum:
    bnez t5, .Lparse_invalid
    li a0, 1
    ret
.Lparse_invalid:
    li a0, 0
    ret
    .size asm_parse_state, .-asm_parse_state

/* a0 = four positions, a1 = four twists, return packed coordinate in a0.
 * Unrolled partial Lehmer rank, then base-three orientation rank.
 */
    .type asm_rank4,@function
asm_rank4:
    lbu t0, 0(a0)
    lbu t1, 1(a0)
    lbu t2, 2(a0)
    lbu t3, 3(a0)
    sltu t4, t0, t1
    sub t1, t1, t4
    /* Preserve original positions for the remaining comparisons. */
    lbu a2, 1(a0)
    sltu t4, t0, t2
    sltu t5, a2, t2
    sub t6, t2, t4
    sub t6, t6, t5
    sltu t4, t0, t3
    sltu t5, a2, t3
    sltu a3, t2, t3
    sub t3, t3, t4
    sub t3, t3, t5
    sub t3, t3, a3
    slli t4, t0, 2
    slli t0, t0, 1
    add t0, t0, t4
    add t0, t0, t1
    slli t4, t0, 2
    add t0, t0, t4
    add t0, t0, t6
    slli t0, t0, 2
    add t0, t0, t3
    lbu t1, 0(a1)
    lbu t2, 1(a1)
    slli t3, t1, 1
    add t1, t1, t3
    add t1, t1, t2
    lbu t2, 2(a1)
    slli t3, t1, 1
    add t1, t1, t3
    add t1, t1, t2
    lbu t2, 3(a1)
    slli t3, t1, 1
    add t1, t1, t3
    add t1, t1, t2
    slli t1, t1, 10
    or a0, t0, t1
    ret
    .size asm_rank4, .-asm_rank4

/* a0 = valid normalized state; return pattern A/B coordinates in a0/a1.
 * Inverse positions and twists are arranged by cubie identity on the stack.
 * The overlapping patterns are consecutive identities [0..3] and [3..6].
 */
    .globl asm_coordinates
    .type asm_coordinates,@function
asm_coordinates:
    addi sp, sp, -32
    sw ra, 28(sp)
    li t0, 0
    addi a1, a0, 7
.Lproject:
    lbu t1, 0(a0)
    lbu t2, 0(a1)
    add t3, sp, t1
    sb t0, 0(t3)
    sb t2, 7(t3)
    addi a0, a0, 1
    addi a1, a1, 1
    addi t0, t0, 1
    li t4, 7
    bltu t0, t4, .Lproject
    mv a0, sp
    addi a1, sp, 7
    call asm_rank4
    sw a0, 16(sp)
    addi a0, sp, 3
    addi a1, sp, 10
    call asm_rank4
    mv a1, a0
    lw a0, 16(sp)
    lw ra, 28(sp)
    addi sp, sp, 32
    ret
    .size asm_coordinates, .-asm_coordinates

/* Macros use only t0..t5. Table bases and current coordinates survive.
 * Multiplication by 81 is (x<<6)+(x<<4)+x, including orientation row offsets.
 */
    .macro TURN coordinate, turns, orientations
    andi t0, \coordinate, 1023
    slli t0, t0, 2
    add t0, t0, \turns
    lw t1, 0(t0)
    srli t2, t1, 10
    slli t3, t2, 6
    slli t4, t2, 4
    add t2, t2, t3
    add t2, t2, t4
    srli t3, \coordinate, 10
    add t2, t2, t3
    add t2, t2, \orientations
    lbu t2, 0(t2)
    slli t2, t2, 10
    andi t1, t1, 1023
    or \coordinate, t1, t2
    .endm

    .macro DISTANCE coordinate, result, table
    andi t0, \coordinate, 1023
    slli t1, t0, 6
    slli t2, t0, 4
    add t0, t0, t1
    add t0, t0, t2
    srli t1, \coordinate, 10
    add t0, t0, t1
    srli t1, t0, 1
    add t1, t1, \table
    lbu t1, 0(t1)
    andi t0, t0, 1
    slli t0, t0, 2
    srl \result, t1, t0
    andi \result, \result, 15
    .endm

/* Public leaf accessors support independent target-side table checks.
 * asm_turn_coordinate(a0=coordinate,a1=face); asm_coordinate_distance(a0,a1=pattern).
 * Preconditions: permutation<840, orientation<81, face<3, pattern<2.
 */
    .globl asm_turn_coordinate
    .type asm_turn_coordinate,@function
asm_turn_coordinate:
    li t0, 3360
    la a2, asm_coordinate_turn
.Lturn_row:
    beqz a1, .Lturn_ready
    add a2, a2, t0
    addi a1, a1, -1
    j .Lturn_row
.Lturn_ready:
    la a3, asm_orientation_add
    TURN a0, a2, a3
    ret
    .size asm_turn_coordinate, .-asm_turn_coordinate

    .globl asm_coordinate_distance
    .type asm_coordinate_distance,@function
asm_coordinate_distance:
    la a2, asm_pdb_a
    beqz a1, .Ldistance_ready
    la a2, asm_pdb_b
.Ldistance_ready:
    DISTANCE a0, a0, a2
    ret
    .size asm_coordinate_distance, .-asm_coordinate_distance

/* a0/a1=root coordinates, a2=bound (1..11), a3=11-byte path.
 * Return solution length, or negative smallest exceeded threshold.
 * 0..159: ten suspended ancestors {a,b,face,turn}; 160/164: root;
 * 176..224: callee-saved registers and ra. Fixed frame: 240 bytes.
 * An accepted non-goal child has h>=1 and depth+1+h<=11, hence depth<=10.
 * Rejected candidates do not write the explicit stack or the output path.
 */
    .type asm_search,@function
asm_search:
    addi sp, sp, -240
    sw s0, 176(sp)
    sw s1, 180(sp)
    sw s2, 184(sp)
    sw s3, 188(sp)
    sw s4, 192(sp)
    sw s5, 196(sp)
    sw s6, 200(sp)
    sw s7, 204(sp)
    sw s8, 208(sp)
    sw s9, 212(sp)
    sw s10, 216(sp)
    sw s11, 220(sp)
    sw ra, 224(sp)
    sw a0, 160(sp)
    sw a1, 164(sp)
    mv s0, a0
    mv s1, a1
    mv s2, a2
    mv s3, a3
    li s4, 0                         /* depth */
    li s5, 0                         /* face */
    li s6, 0                         /* turn */
    li s7, 3                         /* previous face */
    li s8, 12                        /* next bound */
    la s9, asm_coordinate_turn
    la s10, asm_orientation_add
    la s11, asm_pdb_a
    la a6, asm_pdb_b
.Lsearch_loop:
    li t0, 3
    beq s5, t0, .Lbacktrack
    beq s5, s7, .Lskip_face
    beq s6, t0, .Lnext_face
    /* face*3360 = face*(2048+1024+256+32). */
    slli t0, s5, 11
    slli t1, s5, 10
    add t0, t0, t1
    slli t1, s5, 8
    add t0, t0, t1
    slli t1, s5, 5
    add t0, t0, t1
    add a5, s9, t0
    TURN s0, a5, s10
    TURN s1, a5, s10
    addi s6, s6, 1
    DISTANCE s0, a0, s11
    DISTANCE s1, a1, a6
    bgeu a0, a1, .Lmax_ready
    mv a0, a1
.Lmax_ready:
    add t0, s4, a0
    addi t0, t0, 1
    bltu s2, t0, .Lprune
    beqz a0, .Lfound
    slli t0, s4, 4
    add t0, sp, t0
    sw s0, 0(t0)
    sw s1, 4(t0)
    sw s5, 8(t0)
    sw s6, 12(t0)
    addi s4, s4, 1
    mv s7, s5
    li s5, 0
    li s6, 0
    j .Lsearch_loop
.Lprune:
    bgeu t0, s8, .Lsearch_loop
    mv s8, t0
    j .Lsearch_loop
.Lskip_face:
    addi s5, s5, 1
    j .Lsearch_loop
.Lnext_face:
    addi s5, s5, 1
    li s6, 0
    beqz s4, .Lrestore_root
    addi t0, s4, -1
    slli t0, t0, 4
    add t0, sp, t0
    lw s0, 0(t0)
    lw s1, 4(t0)
    j .Lsearch_loop
.Lrestore_root:
    lw s0, 160(sp)
    lw s1, 164(sp)
    j .Lsearch_loop
.Lbacktrack:
    beqz s4, .Lexhausted
    addi s4, s4, -1
    slli t0, s4, 4
    add t0, sp, t0
    lw s0, 0(t0)
    lw s1, 4(t0)
    lw s5, 8(t0)
    lw s6, 12(t0)
    li s7, 3
    beqz s4, .Lsearch_loop
    lw s7, -8(t0)                    /* preceding ancestor's face */
    j .Lsearch_loop
.Lexhausted:
    neg a0, s8
    j .Lsearch_return
.Lfound:
    li t0, 0
    mv t1, sp
.Lcopy_path:
    beq t0, s4, .Llast_move
    lw t2, 8(t1)
    lw t3, 12(t1)
    slli t4, t2, 1
    add t2, t2, t4
    add t2, t2, t3
    addi t2, t2, -1
    add t3, s3, t0
    sb t2, 0(t3)
    addi t0, t0, 1
    addi t1, t1, 16
    j .Lcopy_path
.Llast_move:
    slli t0, s5, 1
    add t0, t0, s5
    add t0, t0, s6
    addi t0, t0, -1
    add t1, s3, s4
    sb t0, 0(t1)
    addi a0, s4, 1
.Lsearch_return:
    lw s0, 176(sp)
    lw s1, 180(sp)
    lw s2, 184(sp)
    lw s3, 188(sp)
    lw s4, 192(sp)
    lw s5, 196(sp)
    lw s6, 200(sp)
    lw s7, 204(sp)
    lw s8, 208(sp)
    lw s9, 212(sp)
    lw s10, 216(sp)
    lw s11, 220(sp)
    lw ra, 224(sp)
    addi sp, sp, 240
    ret
    .size asm_search, .-asm_search

/* a0 = valid normalized state, a1 = path; return optimal length or -1.
 * Validation belongs to asm_solve_text. This entry supports a fair C-core
 * comparison with the existing normalized-state benchmark.
 */
    .globl asm_solve
    .type asm_solve,@function
asm_solve:
    addi sp, sp, -32
    sw ra, 28(sp)
    sw s0, 24(sp)
    sw s1, 20(sp)
    sw s2, 16(sp)
    sw s3, 12(sp)
    mv s0, a1
    call asm_coordinates
    mv s1, a0
    mv s2, a1
    li a1, 0
    call asm_coordinate_distance
    mv s3, a0
    mv a0, s2
    li a1, 1
    call asm_coordinate_distance
    bgeu s3, a0, .Lbound_ready
    mv s3, a0
.Lbound_ready:
    beqz s3, .Lsolve_zero
.Lthreshold:
    li t0, 11
    bltu t0, s3, .Lsolve_failed
    mv a0, s1
    mv a1, s2
    mv a2, s3
    mv a3, s0
    call asm_search
    bgez a0, .Lsolve_return
    neg s3, a0
    j .Lthreshold
.Lsolve_zero:
    li a0, 0
    j .Lsolve_return
.Lsolve_failed:
    li a0, -1
.Lsolve_return:
    lw s3, 12(sp)
    lw s2, 16(sp)
    lw s1, 20(sp)
    lw s0, 24(sp)
    lw ra, 28(sp)
    addi sp, sp, 32
    ret
    .size asm_solve, .-asm_solve

/* a0=text, a1=11-byte path. -2=invalid, -1=search failure, 0..11=length.
 * Maximum simultaneous stack: 32+32+240 = 304 bytes.
 */
    .globl asm_solve_text
    .type asm_solve_text,@function
asm_solve_text:
    addi sp, sp, -32
    sw ra, 28(sp)
    sw a1, 16(sp)
    mv a1, sp
    call asm_parse_state
    beqz a0, .Ltext_invalid
    mv a0, sp
    lw a1, 16(sp)
    call asm_solve
    j .Ltext_return
.Ltext_invalid:
    li a0, -2
.Ltext_return:
    lw ra, 28(sp)
    addi sp, sp, 32
    ret
    .size asm_solve_text, .-asm_solve_text
