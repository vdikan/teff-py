

def wrap_mpirun(command, num):
    mpirun = command.machine["mpirun"]["-np", num]

    return mpirun[command]


def wrap_mprof(command):
    mprof = command.machine["mprof"]["run", "--include-children"]

    return mprof[command]


def wrap_ld_library_path(command):
    machine = command.machine
    ld_lib_env = machine["env"]["LD_LIBRARY_PATH=%s" %
                                machine.env.get("LD_LIBRARY_PATH")]

    return ld_lib_env[command]


class HPCCommandWrapper(object):
    def __call__(self, command, num_mpi_procs=None):
        if num_mpi_procs:
            return wrap_ld_library_path(
                wrap_mprof(
                    wrap_mpirun(command, num_mpi_procs)))
        else:
            return wrap_ld_library_path(
                wrap_mprof(command))


hpc_wrapper = HPCCommandWrapper()
