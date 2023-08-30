"Base- and metaclasses for workflow actions protocol."

import copy
import logging
from enum import Enum, auto
from plumbum.commands.processes import ProcessExecutionError
from plumbum.path import LocalPath


class State(Enum):
    NEW = auto()
    PREPARED = auto()
    RUNNING = auto()
    SUBMITTED = auto()
    FINISHED = auto()
    SUCCEEDED = auto()
    FAILED = auto()
    IGNORED = auto()


class ShellCommandRunner():
    # A basic wrapper over shell commands.
    # Executes only once. Stores split `stdout` and `stderr`
    # in `self.out_log` and `self.error_log` vectors.
    def __init__(self, command, args, num_mpi_procs=None, cwd="./"):
        self._exit_code = None
        self._out_log = []
        self._err_log = []

        #DEPRECATED
        # try:
        #     self.args = command.args + args
        # except AttributeError:
        #     self.args = args

        self.args = args
        self.cwd = cwd

        self.command = command
        #DEPRECATED
        # self.num_mpi_procs = num_mpi_procs
        # if num_mpi_procs is None:
        #     self.command = command
        # else:
        #     machine = command.machine
        #     self.command = machine["mpirun"]["-np", num_mpi_procs, command]

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


class ActionMeta(type):
    """Metaclass for definitions of workflow Action classes.
    Ensures presence of `default_attrs` and definition of
    `required_methods`."""

    default_attrs = {
        'parent': None,
        'path': LocalPath(""),
        'num_mpi_procs': None,
        'command': None,
        'args_source': [],
        'runner': None,
        'state': State.NEW,
        'logger': logging.getLogger(''),
    }

    required_methods = [
        'make_prefix',
        #DEPRECATED 'make_pathname',
        'make_path',
        'make_args_list',
        'change_state_on_prepare',
        'change_state_on_run',
        'prepare',
        'run',
    ]

    @staticmethod
    def _check_field(field_name, bases, fields):
        if field_name in fields:
            return True

        for base in bases:
            if hasattr(base, field_name):
                return True

        return False

    def __new__(mcs, name, bases=None, fields=None):
        for attr_name in mcs.default_attrs:
            if not mcs._check_field(attr_name, bases, fields):
                fields[attr_name] = mcs.default_attrs[attr_name]

        for method_name in mcs.required_methods:
            if not mcs._check_field(method_name, bases, fields):
                raise Exception(f"Method {method_name} must be defined in {name}.")

        return type.__new__(mcs, name, bases, fields)


class Action(metaclass=ActionMeta):
    "Default action class. Demonstrates the actions protocol compliance."

    # TODO: consider turning those into properties
    # @property
    # def state(self):
    #     return copy.deepcopy(self._state)

    # @property
    # def runner(self):
    #     return copy.deepcopy(self._runner)

    def make_prefix(self):
        return self.__class__.__name__.lower()

    def make_path(self):
        if self.parent is None:
            pwd = self.command.machine["pwd"]
            path = self.command.machine.path(pwd().strip())

            return path / self.make_prefix()

        return self.parent.path / self.make_prefix()

    def make_args_list(self):
        return self.args_source

    def __init__(self, args_source, parent=None):
        # First store the `args_source` collection
        # and link to `parent` if present.
        #
        # Other methods used after will depend on them.
        self.args_source = args_source
        self.parent = parent

        self.path = self.make_path()
        self.logger = logging.getLogger(self.make_prefix())

        # Action initialized.
        self.logger.debug("%-10s", self.state.name)
        self.logger.debug("Args source collection received: %s",
                          self.args_source)
        if self.parent is not None:
            self.logger.debug("Parent action linked: %s",
                              self.parent.make_prefix())

    @staticmethod
    def change_state_on_prepare(f):
        """Decorators to take care of logging and state changing for
        the `prepare' method.
        
        Can be re-used for blocking (serial) processing of direct
        Actions subclasses. Also can serve as state flow example
        for e.g. asynchronous implementations.

        """
        def wrapper(*args):
            # args[0] refers to self
            if args[0].command.machine.path(args[0].path).exists():
                args[0].state = State.IGNORED
                args[0].logger.info(
                    "%-10s Action-related path exists. Skipping.",
                    State.IGNORED.name)

                return

            mkdir = args[0].command.machine["mkdir"]
            mkdir("-p", args[0].path)
            f(*args)
            args[0].state = State.PREPARED
            # Action-related path ready for execution.
            args[0].logger.info("%-10s", State.PREPARED.name)

        return wrapper

    @change_state_on_prepare
    def prepare(self):
        pass

    @staticmethod
    def change_state_on_run(f):
        """Decorators to take care of logging and state changing for
        the `run' method.
        
        Can be re-used for blocking (serial) processing of direct
        Actions subclasses. Also can serve as state flow example
        for e.g. asynchronous implementations.

        """
        def wrapper(*args):
            if args[0].state == State.PREPARED:
                args[0].state = State.RUNNING
                # Submtting the action command for execution.
                args[0].logger.debug("%-10s", State.RUNNING.name)

                f(*args)

                # machine = args[0].command.machine
                session = args[0].command.machine.session()
                if args[0].runner.exit_code != 0:
                    args[0].state = State.FAILED
                    args[0].logger.error(
                        "%-10s Action command execution resulted in non-zero exit code.",
                        State.FAILED.name)
                    #DEPRECATED err_path = op.join(args[0].path, "err.log")
                    err_path = args[0].path / "err.log"
                    #DEPRECATED
                    # with open(err_path, "w") as err:
                    #     err.write("\n".join(args[0].runner.err_log))
                    #REVIEW
                    # (machine["echo"]["-n", args[0].runner.err_log] |
                    #  machine["tee"][err_path])()
                    session.run("echo -n \"%s\" | tee %s" %
                                ("\n".join(args[0].runner.err_log), err_path))
                    args[0].logger.error("Error log written at: %s", err_path)
                else:
                    args[0].state = State.SUCCEEDED
                    # Action command successfully executed.
                    args[0].logger.info("%-10s", State.SUCCEEDED.name)

                #DEPRECATED out_path = op.join(args[0].path, "out.log")
                out_path = args[0].path / "out.log"
                #DEPRECATED
                # with open(out_path, "w") as out:
                #     out.write("\n".join(args[0].runner.out_log))
                #REVIEW
                # (machine["echo"]["-n", args[0].runner.out_log] |
                #  machine["tee"][out_path])()
                session.run("echo -n \"%s\" | tee %s" %
                            ("\n".join(args[0].runner.out_log), out_path))
                args[0].logger.debug("Output written at: %s", out_path)

        return wrapper

    @change_state_on_run
    def run(self):
        self.runner = ShellCommandRunner(
            self.command,
            self.make_args_list(),
            cwd=self.path,
            num_mpi_procs=self.num_mpi_procs,
        )

        with self.command.machine.cwd(self.path):
            launch, message = self.runner.run()
            if launch:
                self.logger.debug(message)
            else:
                self.logger.warning(message)
