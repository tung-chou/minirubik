CC ?= cc
CFLAGS ?= -O3 -std=c99 -Wall -Wextra -Wpedantic
GATES := verify_h1 verify_h2 verify_h3 verify_h4

.PHONY: all distances verify verify-h1 verify-h2 verify-h3 verify-h4 check-table check clean

all: generate_distances $(GATES)

generate_distances: generate_distances.c ../solver.c
	$(CC) $(CFLAGS) $< -o $@

../pdb_data.h: ../generate_pdb.c ../pdb.h ../cube_moves.h
	$(MAKE) -C .. pdb

$(GATES): %: %.c gate_common.h ../ida_solver.c ../pdb.h ../cube_moves.h ../pdb_data.h
	$(CC) $(CFLAGS) $< -o $@

exact_distances.bin: generate_distances
	./generate_distances $@

distances: exact_distances.bin

verify-h1: verify_h1 exact_distances.bin
	./verify_h1 exact_distances.bin

verify-h2: verify_h2 exact_distances.bin
	./verify_h2 exact_distances.bin

verify-h3: verify_h3 exact_distances.bin
	./verify_h3 exact_distances.bin

verify-h4: verify_h4
	./verify_h4

# Full search comparison is separate from the normal test suite.
verify: verify-h1 verify-h2 verify-h4 verify-h3

check-table: verify_h3 exact_distances.bin
	./verify_h3 --check-table exact_distances.bin

# Exhaust H1/H2/H4, but use a small H3 range and a depth-11 case.
check: all exact_distances.bin
	python3 check.py

clean:
	$(RM) generate_distances $(GATES)
