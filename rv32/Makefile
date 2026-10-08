RV32_CC ?= riscv64-unknown-elf-gcc
RV32_OBJDUMP ?= riscv64-unknown-elf-objdump
RV32_SIZE ?= riscv64-unknown-elf-size
RIPES ?= Ripes
RIPES_ARGS ?=
CHECK_ARGS ?= --shallow
COMPARE_ARGS ?=
HOST_CC ?= cc
BUILD := build
FLAGS := -march=rv32i -mabi=ilp32 -mno-relax -msmall-data-limit=0 -nostdlib -Wl,--no-relax -Wl,-T,../tests/rv32.ld
CFLAGS_CORE := -O2 -std=c99 -Wall -Wextra -Wpedantic -Werror -march=rv32i -mabi=ilp32 -mno-relax -msmall-data-limit=0 -ffreestanding -fno-builtin -fno-pie -fno-stack-protector -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -fstack-usage
ASM_OPTFLAGS := -DASM_REMOVE_LEAF_RA -DASM_CACHE_FACE_ROW

.PHONY: all inspect check compare compare-build clean
all: $(BUILD)/solver.elf $(BUILD)/bench.elf

../pdb_data.h: ../generate_pdb.c ../pdb.h ../cube_moves.h
	$(MAKE) -C .. pdb

$(BUILD):
	mkdir -p $@

$(BUILD)/export_tables: export_tables.c ../pdb_data.h | $(BUILD)
	$(HOST_CC) -O2 -std=c99 -Wall -Wextra -Wpedantic -Werror $< -o $@

$(BUILD)/tables.S: $(BUILD)/export_tables
	$< > $@.tmp
	mv $@.tmp $@

$(BUILD)/solver.elf: solver.S start.S $(BUILD)/tables.S ../tests/rv32.ld
	$(RV32_CC) $(FLAGS) $(ASM_OPTFLAGS) -DASM_PRINT solver.S start.S $(BUILD)/tables.S -o $@

$(BUILD)/bench.elf: solver.S start.S $(BUILD)/tables.S ../tests/rv32.ld
	$(RV32_CC) $(FLAGS) $(ASM_OPTFLAGS) solver.S start.S $(BUILD)/tables.S -o $@

$(BUILD)/c_core.o: c_core.c ../ida_solver.c ../pdb.h ../pdb_data.h ../cube_moves.h | $(BUILD)
	$(RV32_CC) $(CFLAGS_CORE) -c $< -o $@

$(BUILD)/gcc_O2.elf: $(BUILD)/c_core.o compare_start.S ../tests/rv32.ld
	$(RV32_CC) $(FLAGS) -Wl,--gc-sections -DBENCH_C compare_start.S $(BUILD)/c_core.o -o $@

$(BUILD)/asm_baseline.elf: solver.S compare_start.S $(BUILD)/tables.S ../tests/rv32.ld
	$(RV32_CC) $(FLAGS) -Wl,--gc-sections compare_start.S solver.S $(BUILD)/tables.S -o $@

$(BUILD)/asm_leaf.elf: solver.S compare_start.S $(BUILD)/tables.S ../tests/rv32.ld
	$(RV32_CC) $(FLAGS) -Wl,--gc-sections -DASM_REMOVE_LEAF_RA compare_start.S solver.S $(BUILD)/tables.S -o $@

$(BUILD)/asm_cached.elf: solver.S compare_start.S $(BUILD)/tables.S ../tests/rv32.ld
	$(RV32_CC) $(FLAGS) -Wl,--gc-sections $(ASM_OPTFLAGS) compare_start.S solver.S $(BUILD)/tables.S -o $@

compare-build: $(BUILD)/gcc_O2.elf $(BUILD)/asm_baseline.elf $(BUILD)/asm_leaf.elf $(BUILD)/asm_cached.elf

inspect: all
	$(RV32_SIZE) -A $(BUILD)/solver.elf $(BUILD)/bench.elf
	$(RV32_OBJDUMP) -d -M no-aliases $(BUILD)/bench.elf > $(BUILD)/bench.dis
	python3 inspect_elf.py "$(RV32_OBJDUMP)"

check: all
	python3 check_asm.py --ripes "$(RIPES)" $(CHECK_ARGS) $(RIPES_ARGS)

compare: compare-build
	python3 compare.py --cc "$(RV32_CC)" --objdump "$(RV32_OBJDUMP)" --ripes "$(RIPES)" $(COMPARE_ARGS) $(RIPES_ARGS)

clean:
	$(RM) -r $(BUILD)
