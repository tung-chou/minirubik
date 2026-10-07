.text
main:
   li t0 0x10000000
   addi t1 x0 0 #i=0
   addi t2 x0 1
   slli t2 t2 20
   # for (i=0; i < t2; i++)
loop:
   bge t1 t2 exit # exit when i>=t2
   sw t1 0(t0)
   addi t0 t0 4 
   addi t1 t1 1 #i++
   j loop
exit:
    li a7, 10
    ecall
