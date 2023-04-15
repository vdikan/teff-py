import copy
from plumbum import local

class ShellCommandLocal():
    # A basic wrapper over shell commands.
    # Executes only once. Stores split `stdout` and `stderr`
    # in `self.out_log` and `self.error_log` vectors.
    def __init__(self, command, args, num_mpi_procs=None, cwd="./"):
        self._exit_code = None
        self._out_log = []
        self._err_log = []

        try:
            self.args = command.args + args
        except AttributeError:
            self.args = args

        self.cwd = cwd

        self.num_mpi_procs = num_mpi_procs
        if num_mpi_procs is None:
            self.command = command
        else:
            self.command = local["mpirun"]["-np", num_mpi_procs, command]

    def add_arg(self, arg, value=None):
        if value is not None:
            self.args.append(f"{arg}={value}")
        else:
            self.args.append(arg)

    @property
    def exit_code(self):
        return self._exit_code

    @property
    def out_log(self):
        return copy.deepcopy(self._out_log)

    @property
    def err_log(self):
        return copy.deepcopy(self._err_log)

    def run(self):
        # if len(self.out_log) > 0:
        if self._exit_code is not None:
            return False, "Command already executed! Skipping."

        cmd = self.command[self.args].with_cwd(self.cwd)
        exit_code, stdout, stderr = cmd.run(retcode=None)

        self._exit_code = exit_code
        self._out_log = stdout.split("\n")
        self._err_log = stderr.split("\n")

        return True, "Attemped command execution."
