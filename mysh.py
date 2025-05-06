import signal
import os
import json
import shlex
import sys
import re

from parsing import split_by_pipe_op

#main -> load_config -> substitute_variable -> split_arg -> handle_command_with_pipe(execute_pipeline) -> handle_builtIn -> handle_command

DEFAULT_PROMPT = ">> "
DEFAULT_MYSH_VERSION = "1.0"
# DO NOT REMOVE THIS FUNCTION!
# This function is required in order to correctly switch the terminal foreground group to
# that of a child process.
def setup_signals() -> None:
    """
    Setup signals required by this program.
    """
    signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal_handler)

def signal_handler(sig, frame):
    """
    Handle the SIGINT signal by terminating the entire process group.
    """
    os.killpg(os.getpgid(0), signal.SIGINT)

def load_config():
    """
    Load the shell configuration from the .myshrc file.
    Handles variable substitution and default environment variable values.
    """
    # Initialize an empty dictionary to store the configuration.
    config = {}
    # Determine the path to the .myshrc file in the user's home directory.
    config_path = os.path.expanduser('~/.myshrc')
    # Check if the MYSHDOTDIR environment variable is set, and if so, update the config path.
    if "MYSHDOTDIR" in os.environ:
        config_path = os.path.join(os.environ["MYSHDOTDIR"], ".myshrc")

    try:
        #open the .myshrc file and load its JSON content into the config dictionary.
        with open(config_path, 'r') as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        pass
    except json.JSONDecodeError:
        print("mysh: invalid JSON format for .myshrc", file=sys.stderr)
        return {}
    valid_config = {}

    for key, value in config.items():
        # Check if the key is a valid shell variable name
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', key):
            print(f"mysh: .myshrc: {key}: invalid characters for variable name", file=sys.stderr)
        elif not isinstance(value, str):
            print(f"mysh: .myshrc: {key}: not a string", file=sys.stderr)
        else:
            valid_config[key] = value

    for key in valid_config:
        valid_config[key] = substitute_variables(valid_config[key], valid_config)

    for key, value in valid_config.items():
        os.environ[key] = value

    if "PS1" not in os.environ:
        os.environ["PS1"] = DEFAULT_PROMPT
    if "MYSH_VERSION" not in os.environ:
        os.environ["MYSH_VERSION"] = DEFAULT_MYSH_VERSION

    return valid_config

def substitute_variables(text, config):
    """
    Substitute environment variables in the given text using the provided config.
    Handles nested variable substitutions.
    """
    def replace_var(match):
        # Extract the variable name from the match group.
        var_name = match.group(1)
        if var_name in config:
            # If it exists in the config, recursively substitute its value
            return substitute_variables(config[var_name], config)
        elif var_name in os.environ:
            #check if it exists in the environment variables.
            return os.environ[var_name]
        else:
            return f"${{{var_name}}}"

    pattern = r'\${([A-Za-z_][A-Za-z0-9_]*)}'
    #replace all occurrences of the pattern in the text with the results of replace_var.
    return re.sub(pattern, replace_var, text)

def split_arg(com: str) -> list[str]:

    splited = []
    try:
        process_com = shlex.shlex(com, posix=True)
        process_com.escapedquotes += "'"
        process_com.whitespace_split = True
        splited = list(process_com)
        return splited
    except ValueError as e:
        print("mysh: syntax error: unterminated quote", file=sys.stderr)
        return []
    
def go_to_directory(path):
    try:
        if path == "~":
            path = os.path.expanduser("~")

        new_path = os.path.abspath(path)

        os.chdir(new_path)

        os.environ["PWD"] = os.path.realpath(os.getcwd())

    except FileNotFoundError:
        print(f"cd: no such file or directory: {path}", file=sys.stderr)
    except NotADirectoryError:
        print(f"cd: not a directory: {path}", file=sys.stderr)
    except PermissionError:
        print(f"cd: permission denied: {path}", file=sys.stderr)

def handle_builtin(command, config):
    args = command
    if not args:
        return False
    if args[0] == "exit":
        if len(args) > 2:
            print("exit: too many arguments", file=sys.stderr)
        elif len(args) == 2:
            if args[1].isdigit():
                sys.exit(int(args[1]))
            else:
                print(f"exit: non-integer exit code provided: {args[1]}", file=sys.stderr)
                return True
        elif len(args) == 1:
            sys.exit(0)

    elif args[0] == "pwd":
        if len(args) == 1:
            print(os.getcwd())

        elif len(args) == 2:
            if args[1] == "-P":
                print(os.path.realpath(os.getcwd()))
            elif args[1].startswith("-"):
                args_in = list(args[1])
                print(f"pwd: invalid option: {''.join(args_in[:2])}", file=sys.stderr)
            else:
                print("pwd: not expecting any arguments", file=sys.stderr)
        else:
            for arg in args[1:]:
                if not arg.startswith("-P"):
                    print(f"pwd: invalid option: {arg}", file=sys.stderr)
                    break
            else:
                print(os.path.realpath(os.getcwd()))
        return True
    
    elif args[0] == "cd":
        if len(args) > 2:
            print("cd: too many arguments", file=sys.stderr)
        if len(args) == 1:
            #no argument provided, change to home directory
            home_dir = os.path.expanduser("~")
            go_to_directory(home_dir)
        if len(args) == 2:
            go_to_directory(args[1])
        return True
    
    elif args[0] == "which":
        names = ["cd", "exit", "pwd", "which", "var"]

        if len(args) < 2:
            print("usage: which command ...", file=sys.stderr)
            
        def find_executable(name):
            pathDirs = os.getenv("PATH", os.defpath).split(os.pathsep)
            for dir in pathDirs:
                potential_path = os.path.join(dir, name)
                if os.path.isfile(potential_path) and os.access(potential_path, os.X_OK):
                    return potential_path
            return None
        for name in args[1:]:
            if name in names:
                print(f"{name}: shell built-in command")
            else:
                path = find_executable(name)
                if path:
                    print(path)
                else:
                    print(f"{name} not found")
        return True

    elif args[0] == "var":
        if len(args) < 3:
            print(f"var: expected 2 arguments, got {len(args)}", file=sys.stderr)
        elif args[1].startswith("-") and args[1] != "-s":
            arg = list(args[1])
            print(f"var: invalid option: {''.join(arg[:2])}", file=sys.stderr)

        elif args[1] != "-s":
            if len(args) > 3:
                num = len(args) - 1
                print(f"var: expected 2 arguments, got {num}", file=sys.stderr)

            if args[1] == "PROMPT":
                prompt_part = " ".join(args[2:]).strip('"').strip("'")
                if prompt_part.startswith("${"):
                    var_name = prompt_part.split("}")[0].strip("${")
                    var_value = os.environ.get(var_name, "")
                    remaining_part = prompt_part.split("}", 1)[1]
                    prompt_part = var_value + remaining_part
                os.environ["PROMPT"] = prompt_part
                return True
            elif not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', args[1]):
                print(f"var: invalid characters for variable {args[1]}")
            else:
                var_name = args[1]
                var_value = args[2]
                os.environ[var_name] = var_value

        else:
            if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', args[2]):
                print(f"mysh: syntax error: invalid characters for variable {args[2]}")
            else:
                if (args[3].startswith('"') and args[3].endswith('"')) or (args[3].startswith("'") and args[3].endswith("'")):
                    var_name = args[2]
                    command_to_run = shlex.split(args[3][1:-1])
                else:
                    var_name = args[2]
                    command_to_run = shlex.split(args[3])
                # Create a pipe, which returns two file descriptors, read_fd and write_fd.
                read_fd, write_fd = os.pipe()
                # Fork the current process to create a child process.
                pid = os.fork()

                # In the child process:
                if pid == 0:
                    # Close the read end of the pipe since the child will write.
                    os.close(read_fd)
                    # Redirect stdout to the write end of the pipe.
                    os.dup2(write_fd, 1)
                    # Close the original write end of the pipe.
                    os.close(write_fd)
                    # Replace the current process with the command to be executed.
                    os.execvp(command_to_run[0], command_to_run)
                # In the parent process:
                else:
                    # Close the write end of the pipe since the parent will read.
                    os.close(write_fd)
                    # Read the output from the read end of the pipe, limited to 1024 bytes, and decode it to a string.
                    output = os.read(read_fd, 1024).decode().strip()
                    # Close the read end of the pipe.
                    os.close(read_fd)
                    # Wait for the child process to finish and get its exit status.
                    _, status = os.waitpid(pid, 0)
                    # If the child process exited normally and with a status code of 0 (success):
                    if os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0:
                        os.environ[var_name] = output
        return True
    
    elif args[0] == "echo":
        output = []
        for arg in args[1:]:
            if "\\$" in arg:
                escaped_part = arg.replace("\\$", "$")
                output.append(escaped_part)
            elif arg.startswith("${") and arg.endswith("}"):
                var_name = arg[2:-1]
                if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', var_name):
                    var_name = var_name.replace("${","").replace("}","")
                    print(f"mysh: syntax error: invalid characters for variable {var_name}")
                    return True
                else:
                    var_output = os.environ.get(var_name, "")
                    output.append(var_output)
            elif (arg.startswith('"') and arg.endswith('"')) or (arg.startswith("'") and arg.endswith("'")):
                stripped_arg = arg[1:-1]
                if "${" in stripped_arg:
                    start = stripped_arg.index("${") + 2
                    end = stripped_arg.index("}")
                    var_name = stripped_arg[start:end]
                    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', var_name):
                        var_name = var_name.replace("${","").replace("}","")
                        print(f"mysh: syntax error: invalid characters for variable {var_name}")
                        return True
                    else:
                        var_value = os.environ.get(var_name, "")
                        stripped_arg = stripped_arg.replace(f"${{{var_name}}}", var_value)
                output.append(arg[0] + stripped_arg + arg[-1])
            else:
                output.append(arg)
        print(" ".join(output))
        return True

    elif args[0] == "cat":
        for arg in args[1:]:
            if arg.startswith("${") and arg.endswith("}"):
                var_name = arg[2:-1]
                if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', var_name):
                    print(f"mysh: syntax error: invalid characters for variable {var_name}")
                    return True
        for filename in args[1:]:
            if filename.startswith("~"):
                filename = os.path.expanduser(filename)
            
            if not os.path.exists(filename):
                print(f"cat: {filename}: No such file or directory", file=sys.stderr)
                return True

            if os.path.isdir(filename):
                return True

            try:
                with open(filename, 'r') as file:
                    for line in file:
                        print(line, end="")
            except IOError as e:
                return True
        return True
    else:
        handle_command(args)
        return False

def handle_command(command) -> None:
    expanded_command = []
    for arg in command:
        if arg.startswith("~"):
            arg = os.path.expanduser(arg)
        expanded_command.append(arg)

    command = expanded_command
    for arg in command:
        if '/' in arg:
            if not os.path.exists(arg):
                print(f"mysh: no such file or directory: {arg}", file=sys.stderr)
                return
            elif os.path.isdir(arg):
                print(f"mysh: is a directory: {arg}", file=sys.stderr)
                return
            elif not os.access(arg, os.X_OK):
                print(f"mysh: permission denied: {arg}", file=sys.stderr)
                return

    try:
        child_pid = os.fork()
        if child_pid == 0:
            try:
                # Set the process group ID of the child process to its own PID.
                #makes the child process the leader of a new process group.
                os.setpgid(0, 0)
            except PermissionError:
                pass
            # Replace the current child process with the command to be executed
            os.execvp(command[0], command)
            #Exits the child process with a status code of 1, failure
            sys.exit(1)
        else:
            child_pgid = os.getpgid(child_pid)
            # Open the controlling terminal for the parent process.
            with open('/dev/tty') as tty:
                # Get the file descriptor for the terminal.
                tty_fd = tty.fileno()
                # Set the terminal's foreground process group to the child's process group.
                os.tcsetpgrp(tty_fd, child_pgid)
                # Wait for the child process to finish and get its exit status.
                _, status = os.waitpid(child_pid, 0)
                # After the child process finishes, set the terminal's foreground process group back to the parent.
                os.tcsetpgrp(tty_fd, os.getpgrp())
    except FileNotFoundError:
        print(f"mysh: command not found: {command[0]}", file=sys.stderr)
    except NotADirectoryError:
        print(f"mysh: is a directory: {command[0]}", file=sys.stderr)
        return
    except PermissionError:
        print(f"mysh: permission denied: {command[0]}", file=sys.stderr)
        return

def execute_pipeline(commands: list[list[str]]) -> None:
    num_commands = len(commands)
    processes = []
    prev_fd = None

    signal.signal(signal.SIGINT, signal_handler)

    for i, command in enumerate(commands):
        if i < num_commands - 1:
            read_fd, write_fd = os.pipe()
        else:
            read_fd, write_fd = None, None
        
        pid = os.fork()
        
        if pid == 0:
            os.setpgid(0, 0)
            if prev_fd is not None:
                os.dup2(prev_fd, 0)
                os.close(prev_fd)
            if write_fd is not None:
                os.dup2(write_fd, 1)
                os.close(write_fd)
            if read_fd is not None:
                os.close(read_fd)
            os.execvp(command[0], command)
            sys.exit(1)
        else:
            if i == 0:
                os.setpgid(pid, pid)
            else:
                os.setpgid(pid, processes[0])
            if prev_fd is not None:
                os.close(prev_fd)
            if write_fd is not None:
                os.close(write_fd)
            prev_fd = read_fd
            processes.append(pid)

    for pid in processes:
        os.waitpid(pid, 0)

def handle_command_with_pipes(command_str: str, config):

    commands = split_by_pipe_op(command_str)

    for cmd in commands:
        if not cmd.strip():
            print("mysh: syntax error: expected command after pipe", file=sys.stderr)
            return
    command_list = [split_arg(cmd) for cmd in commands]
    
    if len(command_list) > 1:
        execute_pipeline(command_list)
    else:
        handle_builtin(command_list[0], config)
    
def main() -> None:
    setup_signals()

    if "PROMPT" not in os.environ:
        os.environ["PROMPT"] = DEFAULT_PROMPT
    
    config = load_config()

    while True:
        try:
            prompt = os.environ.get("PROMPT", DEFAULT_PROMPT)
            command = input(prompt).strip()

            if not command:
                continue

            if command == "exit":
                break

            handle_command_with_pipes(command, config)

        except KeyboardInterrupt:
            print()
            continue
        except EOFError:
            print()
            break

if __name__ == "__main__":
    main()
