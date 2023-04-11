"Base- and metaclasses for workflow ations protocol."

# import copy
from enum import Enum, auto
from plumbum import local
from plumbum.cmd import mkdir
from plumbum.commands.processes import ProcessExecutionError

from .shell_command_wrapper import ShellCommandWrapperBase


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
        'parent_path': "",
        'path': "",
        'num_mpi_procs': None,
        'command': None,
        'args_source': [],
        'runner_type': type,
        'runner': None,
        'state': State.NEW,
    }

    required_methods = [
        'make_pathname',
        'make_args_list',
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


class ActionDefault(metaclass=ActionMeta):
    "Default action class. Demonstrates the actions protocol compliance."

    # @property
    # def state(self):
    #     return copy.deepcopy(self._state)

    # @property
    # def runner(self):
    #     return copy.deepcopy(self._runner)

    def make_pathname(self):
        return self.parent_path + "/" + self.__class__.__name__.lower()

    def make_args_list(self):
        return self.args_source

    def __init__(self, args_source):
        self.path = self.make_pathname()
        self.args_source = args_source
        self.runner = ShellCommandWrapperBase(
            self.command,
            self.make_args_list(),
            cwd=self.path,
            num_mpi_procs=self.num_mpi_procs,
        )

    def prepare(self):
        try:
            mkdir(self.path)
            self.state = State.PREPARED
        except ProcessExecutionError:
            self.state = State.IGNORED

    def run(self):
        assert self.state == State.PREPARED
        self.state = State.RUNNING

        with local.cwd(self.path):
            self.runner.run()

        if self.runner.exit_code != 0:
            self.state = State.FAILED
            return
        self.state = State.SUCCEEDED
