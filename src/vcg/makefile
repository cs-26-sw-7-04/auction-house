CFLAGS = -Wall -Werror -Wextra -std=c99 -pedantic
CC = gcc
TEST_DIR = ./tests
OBJ =  $(wildcard *.o)

main: main.c 
	$(CC) -o main.o $(CFLAGS) -c main.c 
.PHONY: test
test: $(TEST_DIR)/gentest.c main $(wildcard $(TEST_DIR)/*.h)
	$(CC) $(CFLAGS) $(TEST_DIR)/gentest.c $(OBJ) -o $(TEST_DIR)/gentest
	./$(TEST_DIR)/gentest  $(TEST_DIR) $(TEST_DIR)/test.c $(filter-out $(TEST_DIR)/test_utils.h,$(wildcard $(TEST_DIR)/*.h))
	$(CC) $(CFLAGS) -ggdb $(TEST_DIR)/test.c $(OBJ) -o $(TEST_DIR)/test
	./$(TEST_DIR)/test
