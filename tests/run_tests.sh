#!/bin/bash

MYSH_PATH=${MYSH_PATH:-"./mysh.py"}
TEST_INPUT=${TEST_INPUT:-"./tests/io_files/all_test.in"}
TEST_OUTPUT=${TEST_OUTPUT:-"./tests/io_files/all_test.out"}

python3 "$MYSH_PATH" < "$TEST_INPUT" > output.tmp 2>&1

if diff output.tmp "$TEST_OUTPUT"; then
    echo "Test passed"
else
    echo "Test failed"
fi

rm output.tmp
