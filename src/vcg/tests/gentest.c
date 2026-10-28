#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stddef.h>
#include <ctype.h>

#define TEST_INPUT_BUFFER_SIZE 1024


#define da_append(xs, x)								\
	do {										\
	if ((xs)->count >= (xs)->capacity){						\
	if ((xs)->capacity == 0) (xs)->capacity = 256;					\
	else (xs)->capacity *= 2;							\
	(xs)->items = realloc((xs)->items, (xs)->capacity*sizeof(*(xs)->items));	\
	}										\
	(xs)->items[(xs)->count++] = (x);						\
	} while(0)									\

#define str_append(xs, x)								\
	do {										\
	if ((xs)->count >= (xs)->capacity-1){						\
	if ((xs)->capacity == 0) (xs)->capacity = 256;					\
	else (xs)->capacity *= 2;							\
	(xs)->items = realloc((xs)->items, (xs)->capacity*sizeof(*(xs)->items));	\
	}										\
	(xs)->items[(xs)->count++] = (x);						\
	(xs)->items[(xs)->count+1] = 0;							\
	} while(0)									\

typedef struct{
	char* items;
	int count;
	int capacity;
} dstring;

typedef struct
{
	size_t line;
	size_t col;
	size_t offset;
} cursor;

typedef struct
{
	char* name;
	char* file;
	int line;
	int col;
} function;

typedef struct
{
	function** items;
	int count;
	int capacity;
} functions;

typedef struct
{
	char** items;
	int count;
	int capacity;
} files_t;
files_t files = {0};

char test_input_buffer[TEST_INPUT_BUFFER_SIZE];
functions funcarr = {0};



bool generate_tests(char* input_file, char* test_dir)
{
	FILE* in = fopen(input_file, "r");
	size_t bytes_read;
	char* file_to_include;
	if (in == NULL)
	{
		perror("error opening file");
		return false;
	}
	dstring file_loc = {0};
	size_t test_dir_len = strlen(test_dir);
	size_t input_file_len = strlen(input_file);
	for (size_t i = 0; i < input_file_len; i++) str_append(&file_loc, input_file[i]);

	if (strlen(input_file) > test_dir_len && !strncmp(input_file, test_dir, test_dir_len))
		file_to_include = input_file + (test_dir_len > 1 ?  test_dir_len + 1 : 0);
	da_append(&files, file_to_include);
	cursor cur = {0};
	cur.line = 1;
	bytes_read = fread(test_input_buffer, sizeof(char), sizeof(test_input_buffer), in);
	dstring str = {0};
	bool parsing_function = false;
	bool might_be_function = false;
	bool macro_definition = false;
	char next_char = 0;
	
	while (cur.offset <= bytes_read) 
	{
		next_char = test_input_buffer[cur.offset];
		if (next_char == '\n' && !might_be_function)
		{
			cur.col = 0;
			cur.line++;
			cur.offset++;
			continue;
		}
		if (cur.offset+1 > bytes_read)
		{
			bytes_read = fread(test_input_buffer, sizeof(char), sizeof(test_input_buffer), in);
			cur.offset = 0;
			next_char = test_input_buffer[cur.offset];
		}
		if (next_char == '#') macro_definition = true;

		while (macro_definition)
		{
			if (next_char == '\n')
			{
				macro_definition = false;
				cur.col = 0;
				cur.line++;
			}
			if (cur.offset + 1 == bytes_read)
			{
				bytes_read = fread(test_input_buffer, sizeof(char), sizeof(test_input_buffer), in);
				cur.offset = 0;
			
			}
			cur.offset++;
			next_char = test_input_buffer[cur.offset];
		}
		if (next_char == 'T' && !might_be_function)
		{
			might_be_function = true;
			str.count = 0;
			str_append(&str, next_char);
			cur.col++;
			cur.offset++;
			continue;

		}
		else if (might_be_function)
		{
			str_append(&str, next_char);
			if (str.count == 5 && !strcmp(str.items, "TEST "))
			{
				str.count = 0;
				parsing_function = true;
			}
			else if (isblank(next_char) && !parsing_function)
			{
				might_be_function = false;
			}
			if (next_char == '\n')
			{
				str.count--;
				str.items[str.count] = 0;

				cur.col = 0;
				cur.offset++;
				if (parsing_function)
				{
					parsing_function = false;
					might_be_function = false;
					function *func = malloc(sizeof(function));
					func->name = malloc(str.count+1);
					strncpy(func->name, str.items, str.count+1);

					func->file = malloc(file_loc.count+1);
					strncpy(func->file, file_loc.items, file_loc.count+1);

					func->line = cur.line;
					func->col = cur.col;
					da_append(&funcarr, func);
					printf("found function: %s:%d:%d %s\n", func->file, func->line,func->col, func->name);
				}
				cur.line++;
				str.count = 0;

			}

		}
		cur.col++;
		cur.offset++;
		
	}

	fclose(in);
	return true;
}

void write_tests(FILE* out)
{
	for (int i = 0; i < files.count; i++)
	{
		fprintf(out, "#include \"%s\"\n", files.items[i]);
	}
	fprintf(out, "#ifndef print_test_report_\n");
	fprintf(out, "#define print_test_report_ \n");
	fprintf(out, "#include <stdio.h>\n");
	fprintf(out, "void print_test_report(int run, int pass, int fail)\n");
	fprintf(out, "{\n\tprintf(\"%%d/%%d tests passed\\n\", pass, run);\n");
	fprintf(out, "\tprintf(\"%%d/%%d tests failed\\n\", fail, run);\n}\n");
	fprintf(out, "#endif\n");
	fprintf(out, "char* tests_success[] = {\n");
	for (int i = 0; i < funcarr.count; i++)
	{
		fprintf(out, "\t\"%s:%d:%d: info: %s\",\n", funcarr.items[i]->file, funcarr.items[i]->line, funcarr.items[i]->col, funcarr.items[i]->name);
	}
	fprintf(out, "};\n");
	fprintf(out, "char* tests_fail[] = {\n");
	for (int i = 0; i < funcarr.count; i++)
	{
		fprintf(out, "\t\"%s:%d:%d: error: %s\",\n", funcarr.items[i]->file, funcarr.items[i]->line, funcarr.items[i]->col, funcarr.items[i]->name);
	}
	fprintf(out, "};\n");
	fprintf(out, "int main()\n{\n");
	fprintf(out, "\tint tests_run = 0;\n");
	fprintf(out, "\tint tests_passed = 0;\n");
	fprintf(out, "\tint tests_failed = 0;\n");
	printf("writing %d tests\n", funcarr.count);
	for (int i = 0; i < funcarr.count; i++)
	{
		fprintf(out, "\trun_test(%s);\n", funcarr.items[i]->name);
		fprintf(stdout, "wrote function: %s\n", funcarr.items[i]->name);
	}
	fprintf(out, "\tprint_test_report(tests_run, tests_passed, tests_failed);\n");
	fprintf(out, "}\n");
}

int main(int argc, char** argv)
{
	if (argc <= 1)
	{
		fprintf(stdout, "USAGE: gentest test_dir/ output.c input.h...\n");
		return 1;
	}

	if (argc < 4)
	{
		fprintf(stderr, "too few arguments %d\n", argc);
		return 1;
	}

	FILE* tests_out = fopen(argv[2], "w");

	for (int i = 3; i < argc; i++)
	{
		if (generate_tests(argv[i], argv[1]))
		{
			fprintf(stdout, "generated test calls from %s\n", argv[i]);
		}
		else
		{
			fprintf(stdout, "failed to generate test calls from %s\n", argv[i]);
			continue;
		}
	}
	write_tests(tests_out);
	fclose(tests_out);
	fprintf(stdout, "finished generating tests\n");
}
