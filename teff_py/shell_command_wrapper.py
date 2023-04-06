from plumbum import local, CommandNotFound

class ShellCommandWrapperBase():
    # A basic wrapper over shell commands.
    # Executes only once. Stores split `stdout` and `stderr` in 
    # private `self._out_log` and `self._error_log` vectors.
    def __init__(self, command, *args):
        self._exit_code = None
        self._out_log = []
        self._err_log = []

        self.args = list(args)

        try: 
            self.command = local[command]
        except CommandNotFound:   # wrap the exception
            self._exit_code = 127  # if specified command is not found
            self._err_log.append(f"command not found: {command}")


    def add_arg(self, arg, value=None):
        if value is not None:
            self.args.append(f"{arg}={value}")
        else:
            self.args.append(arg)


    def run(self):
        # if len(self.out_log) > 0:
        if self._exit_code is not None:
            return False, "Command already executed!"
        
        cmd = self.command[self.args]
        exit_code, stdout, stderr = cmd.run()
        self._exit_code = exit_code
        self._out_log = stdout.split("\n")
        self._err_log = stderr.split("\n")
        
        return True, "Attempting command execution."