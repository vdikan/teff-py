
import tomli
import asyncio
# from time import sleep

import logging
import math
from plumbum.machines.paramiko_machine import ParamikoMachine
from plumbum.path.utils import copy
from plumbum import local, cli

from ase import Atoms
from ase.io import read
from numpy import sort, unique

from teff_py.actions import Action, State, ShellCommandRunner
from teff_py.async_actions import SlurmScheduledAction
from teff_py.plumbum_wrappers import hpc_wrapper
from teff_py.tdep_utils import get_rcmax, get_overdetermination_report, get_r_squared

import numpy as np
from numpy import sort, unique


def find_max_rc2(distances):
    thr = 1e-3                      # threshold to add to the cutoff
    half_distance = distances[-1] * 0.5 + thr
    i_rc2 = 1
    while distances[i_rc2] < half_distance:
        i_rc2 += 1

    return i_rc2

def find_rc3_list(distances, i_rc2=None, dist_thr=None):
    # FIXME: width of the window:
    i_rc2 = i_rc2 or find_max_rc2(distances)
    dist_thr = dist_thr or distances[i_rc2] / i_rc2 * 1.0  # <- coeff!

    i_rc3_list = []
    beg = 1
    end = 1

    while (end < i_rc2):
        if abs(distances[end] - distances[beg] <= dist_thr):
            end += 1
        else:
            # i_rc3_list.append(beg)
            i_rc3_list.append(end-1)
            beg = end
    # i_rc3_list.append(beg)
    i_rc3_list.append(end-1)

    return i_rc3_list

# # ## workflow Action stage specifications
class FCsToSubmit(SlurmScheduledAction):
    # command = hpc_wrapper(rem["extract_forceconstants"],
    #                       mprof_include_children=True,
    #                       num_mpi_procs=8)
    def __init__(self, args_source, parent=None, machine=local):
        self.rem = machine
        self.command = self.rem["sbatch"]
        super().__init__(args_source, parent)

    def make_args_list(self):
        return ["sub_fcs.sh"]   # essentially pass

    def make_prefix(self):
        return "sub_fcs_%s_%s" % (self.args_source["rc2"],
                                  self.args_source["rc3"])

    @Action.change_state_on_prepare
    def prepare(self):
        files = ["forces", "meta", "positions", "ssposcar", "stat", "ucposcar"]
        for fname in files:
            self.rem["ln"]("-s",
                           self.path+"/../infile."+fname,
                           self.path+"/infile."+fname)

        self.rem["cp"](self.path+"/../sub_fcs.sh",
                       self.path+"/sub_fcs.sh")
        self.rem["sed"]("-i",
                        "s/LABEL_RC2/%s/g" % self.args_source["rc2"],
                        self.path+"/sub_fcs.sh")
        self.rem["sed"]("-i",
                        "s/LABEL_RC3/%s/g" % self.args_source["rc3"],
                        self.path+"/sub_fcs.sh")


class WfApp(cli.Application):
    console = logging.StreamHandler()

    conf_file = cli.SwitchAttr("--conf-file", str, default="./conf.toml",
                               help="Configuration .toml file")
    verbose_output = cli.Flag("-v", default=False)

    def logging_setup(self):
        "Setup logging handlers for the application"
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
            datefmt='%d-%m-%Y %H:%M',
            filename=self.conf["local_base_path"] + '/wf.log',
            filemode='w',)

        # define a Handler which writes INFO messages or higher to the
        # sys.stderr
        if self.verbose_output:
            self.console.setLevel(logging.INFO)
        else:
            self.console.setLevel(logging.WARNING)

        self.console.setFormatter(
            logging.Formatter(
                '%(asctime)s %(name)-12s %(message)s',
                datefmt='%d-%m-%Y %H:%M',))

        # add the handler to the root logger
        logging.getLogger('').addHandler(self.console)

    def remote_machine_setup(self):
        self.rem = ParamikoMachine(
            self.conf["remote_host"],
            user=self.conf["remote_user"],
            connect_timeout=self.conf["connect_timeout"])

    def main(self):
        with open(self.conf_file, "rb") as f:
            self.conf = tomli.load(f)
            # print(self.conf["local_base_path"])

        self.logging_setup()
        self.remote_machine_setup()
        # print(self.rem["uname"]("-a"))

        inp_repo_dir = local.path(self.conf["inputs_repository"])
        with local.cwd(inp_repo_dir):
            # inp_systems = local["ls"]().split()
            inp_systems = ["216.02.AlAs"]

        for inp_sys in inp_systems:
            # paths preparation
            inp_path = inp_repo_dir / inp_sys

            loc_base_path = local.path(self.conf["local_base_path"])
            loc_path = loc_base_path / inp_sys

            rem_base_path = self.rem.path(self.conf["remote_base_path"])
            rem_path = rem_base_path / inp_sys

            # setup calc_system paths, if needed
            try:
                copy(inp_path, loc_path)
            except FileExistsError:
                pass

            try:
                copy(inp_path, rem_path)
            except FileExistsError:
                pass

            local.cwd.chdir(loc_path)
            self.rem.cwd.chdir(rem_path)

            # build input parameters
            atoms = read(loc_path / "infile.ssposcar", format="vasp")

            mic = True                      # Minimal Image Convention
            kw = {"mic": mic, "vector": False}
            distances_all = atoms.get_all_distances(**kw)

            thr = 1e-3                      # threshold to add to the cutoff
            distances_all = (distances_all + thr).round(decimals=5)
            distances_all = unique(sort(distances_all.flatten()))

            # print(distances_all)
            i_rc2 = find_max_rc2(distances_all)
            # print(i_rc2)
            i_rc3_list = find_rc3_list(distances_all, i_rc2)
            # print(i_rc3_list)

            calc_list = []
            for i_rc3 in i_rc3_list:
                args_source = {"rc2": distances_all[i_rc2],
                               "rc3": distances_all[i_rc3]}
                calc_list.append(FCsToSubmit(args_source, machine=self.rem))

            for calc in calc_list:
                # task.prepare()
                calc.state = State.PREPARED
                
            loop = asyncio.new_event_loop()

            async def group():
                tasks = [calc.run() for calc in calc_list]
                await asyncio.gather(*tasks)

            queue = loop.create_task(group())
            loop.run_until_complete(queue)

        # Shutdown
        self.rem.close()


if __name__ == "__main__":
    WfApp.run()
