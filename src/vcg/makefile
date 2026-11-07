CFLAGS = -Wall -Werror -Wextra -std=c99 -pedantic 
CC = gcc
TEST_DIR = ./tests
BUILD_DIR = ./build
OBJ =  $(wildcard $(BUILD_DIR)/lib/*.so)
PROCS != nproc
THREADS_PER_CORE = 2
AVAIL_THREADS = $$(($(PROCS) * $(THREADS_PER_CORE)))

ifndef VERBOSE
.SILENT:
endif

main: vcg.c vcg.h combinatorial
	mkdir -p build build/include build/lib
	$(CC) -o $(BUILD_DIR)/vcg.o $(CFLAGS) -fPIC -c vcg.c -DPROCS=$(AVAIL_THREADS) -lpthread
	$(CC) $(BUILD_DIR)/vcg.o -shared -o $(BUILD_DIR)/lib/libvcg.so
	rm $(BUILD_DIR)/vcg.o
	cp vcg.h $(BUILD_DIR)/include/vcg.h
.PHONY: test
test: $(TEST_DIR)/gentest.c main_debug $(wildcard $(TEST_DIR)/*.h)
	$(CC) $(CFLAGS) $(TEST_DIR)/gentest.c $(OBJ) -o $(TEST_DIR)/gentest
	./$(TEST_DIR)/gentest  $(TEST_DIR) $(TEST_DIR)/test.c $(filter-out $(TEST_DIR)/test_utils.h,$(wildcard $(TEST_DIR)/*.h))
	$(CC) $(CFLAGS) -ggdb $(TEST_DIR)/test.c $(OBJ) -o $(TEST_DIR)/test
	./$(TEST_DIR)/test
	#python $(TEST_DIR)/data_visualizer.py Time_test_output.csv
.PHONY: clean
clean:
	rm -rf $(BUILD_DIR) $(TEST_DIR)/test $(TEST_DIR)/gentest $(TEST_DIR)/test_combinatorial $(TEST_DIR)/test_combinatorial.c
main_debug: vcg.c vcg.h combinatorial_debug
	mkdir -p build build/include build/lib
	$(CC) -o $(BUILD_DIR)/vcg.o $(CFLAGS) -ggdb -fPIC -c vcg.c -DPROCS=$(AVAIL_THREADS) -lpthread
	$(CC) $(BUILD_DIR)/vcg.o -shared -o $(BUILD_DIR)/lib/libvcg.so
	rm $(BUILD_DIR)/vcg.o
	cp vcg.h $(BUILD_DIR)/include/vcg.h

# Combinatorial VCG (vcg_combinatorial.c), its own library so the bindings for vcg.c are unaffected
.PHONY: combinatorial combinatorial_debug test_combinatorial
combinatorial: vcg_combinatorial.c vcg_combinatorial.h
	mkdir -p build build/include build/lib
	$(CC) $(CFLAGS) -O2 -fPIC -shared -pthread -DPROCS=$(AVAIL_THREADS) vcg_combinatorial.c -o $(BUILD_DIR)/lib/libvcg_combinatorial.so
	cp vcg_combinatorial.h $(BUILD_DIR)/include/vcg_combinatorial.h
combinatorial_debug: vcg_combinatorial.c vcg_combinatorial.h
	mkdir -p build build/include build/lib
	$(CC) $(CFLAGS) -O2 -ggdb -fPIC -shared -pthread -DPROCS=$(AVAIL_THREADS) vcg_combinatorial.c -o $(BUILD_DIR)/lib/libvcg_combinatorial.so
	cp vcg_combinatorial.h $(BUILD_DIR)/include/vcg_combinatorial.h
# Runs only the combinatorial tests, so they are not held up by the tests of vcg.c
test_combinatorial: $(TEST_DIR)/gentest.c $(TEST_DIR)/combinatorial_vcg.h combinatorial_debug
	$(CC) $(CFLAGS) $(TEST_DIR)/gentest.c -o $(TEST_DIR)/gentest
	./$(TEST_DIR)/gentest $(TEST_DIR) $(TEST_DIR)/test_combinatorial.c $(TEST_DIR)/combinatorial_vcg.h
	$(CC) $(CFLAGS) -O2 -ggdb $(TEST_DIR)/test_combinatorial.c $(BUILD_DIR)/lib/libvcg_combinatorial.so -o $(TEST_DIR)/test_combinatorial
	./$(TEST_DIR)/test_combinatorial
