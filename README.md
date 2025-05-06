
# INFO1112 Assignment 1

## Command Translation Process

The command translation process begins with loading the configuration file using the `load_config()` function to initialize environment variables. Next, the user's input is parsed by the `split_by_pipe_op` function. The shell then uses the `substitute_variable` function to replace environment variables in the input with their corresponding values. Finally, the input is executed either by the `handle_builtIn` function for custom commands or by the `handle_command` function as a standard Unix command.

## Environment Variable Substitution

The `substitute_variable` function is responsible for replacing variables within the user's input with their corresponding values. It scans the input for patterns that match environment variables and then fetches the corresponding values to replace the variables in the input string. If the user wants to prevent a variable from being substituted, they can escape the substitution by placing a backslash (`\`) before the dollar sign (`$`), which allows the variable to be interpreted as a literal string.

## Pipeline Handling

First, the shell uses the `split_by_pipe_op` function to split the input into several commands based on the pipe symbol (`|`). Then, with `handle_command_with_pipe`, the shell manages the creation of a child process for each command in the pipeline. The `os.pipe()` function is used to create read and write file descriptors, allowing commands to pass their output as input to the next command. The shell redirects the output of one command to the input of the next command by duplicating the file descriptors with `os.dup2()`.

   ```python
   def execute_pipeline(commands):
       input_fd = None
       for command in commands:
           input_fd = handle_command_with_pipe(command, input_fd)
       if input_fd is not None:
           os.close(input_fd)
   ```
## Testing

I used input/output (I/O) tests to focus on testing one function of the code at a time. For each function, I provided different inputs to simulate various situations that might be encountered in the shell, including error cases and edge cases.
