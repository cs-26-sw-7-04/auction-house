#include <stdbool.h>
#define TEST bool

#define run_test(x)							\
    	if ( (x) )							\
    	{								\
    		tests_passed++;						\
    		fprintf(stdout, "%s PASSED\n", tests_success[tests_run]);	\
    		tests_run++;						\
    	}								\
    	else								\
    	{								\
    		tests_failed++;						\
    		fprintf(stderr, "%s FAILED\n", tests_fail[tests_run]);	\
    		tests_run++;						\
    	}								

