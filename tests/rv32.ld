ENTRY(_start)
PHDRS
{
    code PT_LOAD FLAGS(5);
    constants PT_LOAD FLAGS(4);
    writable PT_LOAD FLAGS(6);
}
SECTIONS
{
    . = 0x1000;
    .text : { KEEP(*(.text.start)) *(.text .text.*) } :code
    .rodata : { *(.rodata .rodata.* .srodata .srodata.*) } :constants
    .data : { KEEP(*(.bench_input)) *(.data .data.* .sdata .sdata.*) } :writable
    .bss (NOLOAD) : { *(.bss .bss.* .sbss .sbss.*) *(COMMON) } :writable
    /DISCARD/ : { *(.comment) *(.eh_frame*) }
}
