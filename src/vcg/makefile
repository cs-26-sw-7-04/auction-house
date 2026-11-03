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

main: vcg.c vcg.h
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
.PHONY: clean
clean:
	rm -rf $(BUILD_DIR) $(TEST_DIR)/test $(TEST_DIR)/gentest
main_debug: vcg.c vcg.h
	mkdir -p build build/include build/lib
	$(CC) -o $(BUILD_DIR)/vcg.o $(CFLAGS) -ggdb -fPIC -c vcg.c -DPROCS=$(AVAIL_THREADS) -lpthread
	$(CC) $(BUILD_DIR)/vcg.o -shared -o $(BUILD_DIR)/lib/libvcg.so
	rm $(BUILD_DIR)/vcg.o
	cp vcg.h $(BUILD_DIR)/include/vcg.h
