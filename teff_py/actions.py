"Base- and metaclasses for workflow ations protocol."

# import copy
import logging
import os.path as op
from enum import Enum, auto
from plumbum import local
from plumbum.cmd import mkdir, pwd
from plumbum.commands.processes import ProcessExecutionError

from .shell_command_wrappers import ShellCommandLocal


class State(Enum):
    NEW = auto()
    PREPARED = auto()
    RUNNING = auto()
    SUCCEEDED = auto()
    FAILED = auto()
    IGNORED = auto()


class ActionMeta(type):
    """Metaclass for definitions of workflow Action classes.
    Ensures presence of `default_attrs` and definition of
    `required_methods`."""

    default_attrs = {
        'parent': None,
        'path': "",
        'num_mpi_procs': None,
        'command': None,
        'args_source': [],
        'runner': None,
        'state': State.NEW,
        'logger': logging.getLogger(''),
    }

    required_methods = [
        'make_prefix',
        'make_pathname',
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


class ActionLocal(metaclass=ActionMeta):
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

    def make_pathname(self):
        if self.parent is None:
            return pwd().strip() + "/" + self.make_prefix()

        return self.parent.path + "/" + self.make_prefix()

    def make_args_list(self):
        return self.args_source

    def __init__(self, args_source, parent=None):
        # First store the `args_source` collection
        # and link to `parent` if present.
        #
        # Other methods used after will depend on them.
        self.args_source = args_source
        self.parent = parent

        self.path = self.make_pathname()
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
        def wrapper(*args):
            # args[0] refers to self
            if local.path(args[0].path).exists():
                args[0].state = State.IGNORED
                args[0].logger.info(
                    "%-10s Action-related path exists. Skipping.",
                    State.IGNORED.name)

                return

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
        def wrapper(*args):
            if args[0].state == State.PREPARED:
                args[0].state = State.RUNNING
                # Submtting the action command for execution.
                args[0].logger.debug("%-10s", State.RUNNING.name)

                f(*args)

                if args[0].runner.exit_code != 0:
                    args[0].state = State.FAILED
                    args[0].logger.error(
                        "%-10s Action command execution resulted in non-zero exit code.",
                        State.FAILED.name)
                    err_path = op.join(args[0].path, "err.log")
                    with open(err_path, "w") as err:
                        err.write("\n".join(args[0].runner.err_log))
                    args[0].logger.error("Error log written at: %s", err_path)
                else:
                    args[0].state = State.SUCCEEDED
                    # Action command successfully executed.
                    args[0].logger.info("%-10s", State.SUCCEEDED.name)

                out_path = op.join(args[0].path, "out.log")
                with open(out_path, "w") as out:
                    out.write("\n".join(args[0].runner.out_log))
                args[0].logger.debug("Output written at: %s", out_path)

        return wrapper

    @change_state_on_run
    def run(self):
        self.runner = ShellCommandLocal(
            self.command,
            self.make_args_list(),
            cwd=self.path,
            num_mpi_procs=self.num_mpi_procs,
        )

        with local.cwd(self.path):
            launch, message = self.runner.run()
            if launch:
                self.logger.debug(message)
            else:
                self.logger.warning(message)
