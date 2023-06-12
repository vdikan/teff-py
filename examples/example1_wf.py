#!/path/to/envs/teff-py/bin/python
# ^FIXME
# ^The path to the python executable in the environment
# where `teff_py` is installed.
#
# `plumbum` preserves the environment of the shell from which
# the script is called, even if the python interpreter is 
# different and located in external environment.
#
# This approach can be used therefore in complex environents
# with DFT and TDEP codes installed and activated through
# `spack`, `environment_modules` etc

####################################################################

# In this script I define the whole workflow executable that
# calculates thermal conductivity for the `example_1_fcc_al`
# from the TDEP software suit across a series of parameters. 
# 
# DISCLAIMER: This is a mere demonstration of an approach to
# composing real, real-world applicable workflows in a fast
# and handy manner. Results of this example don't mean much.
#
# The workflow works on the files of the original example at
# two stages:
# 1. extracts force constants for a selected cutoff value "rc2"
# of the 2nd order FCs. "rc3" is also specified equal to "rc2-1".
# 2. for each calculation in 1), computes thermal conductivity
# on a series of q-point grids. Grid size is specified with "qg"
# parameter, resulting grid size equal along each axis.
# 
# This is performed for a range of "rc2" input parameters. 
# Resulting thermal conductivity values are collected in a dataframe
# and visualized on a "heatmap"-like histogram with "rc2" and "qg"
# along the axis.

####################################################################

# system-related imports:
import logging
import os.path as op
# imports from `plumbum` for shell commands 
# and cli-application wrapper:
from plumbum import local, cli
from plumbum.cmd import cp, ln, mkdir, cat, grep, awk, tail

# my workflow engine actions:
from teff_py.actions import Action, State
 
# data-analysis package zoo imports:
# numpy, pandas, seaborn, etc.
# Although they are not required by the wf engine actions flow,
# the resulting workflows most certain would e.g. build proper
# dataframes, populate databases, output auxiliary plots, and so on.
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# Logging Setup.
# Both my engine and `plumbum` use python built-in `logging` module
# for output of technical information. 
# Each worflow application can tweak the logging format and levels
# according to the user likes. I find the following to be nice defaults. 
# You might want to ignore this section.
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
    datefmt='%d-%m-%Y %H:%M',
    filename='wf.log',
    filemode='w',
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
#console.setLevel(logging.WARNING)
console.setFormatter(
    logging.Formatter(
        '%(asctime)s %(name)-12s %(message)s',
        datefmt='%d-%m-%Y %H:%M',))
logging.getLogger('').addHandler(console)


# Workflow Actions Specifications. 
# -------------------------------
#
# The proposed approach to compose workflows with my engine is: 
# 1) define Action classes for workflow stages and
# 2) use their instances in a workflow, that is in fact an
# arbitrary python program.
#
# The following actions are subclasses of `ActionLocal` class. 
# In most cases they will need to specify 2 argument fields:
# - `command` - local executable command (wraped in `plumbum.local`)
# - `num_mpi_procs` - when not `None`, the command above will be fed 
#    to `mpirun` with this number of procs.
# ...as well as methods:
# - `make_args_list`
# - `make_prefix`
# - `prepare`
# 
# By design, each action instance receives `args_source` collection
# and optional link to `parent` action. Note that `args_source` is 
# an arbitrary python container. The user specifies, by redefining
# `make_args_list` how to build (unpack) shell command arguments for
# instaces of each concrete Action class from the `args_source`.
# Simiarly, `make_prefix` defines how to build a string label which
# is used for logging and calculation directory pathname generation. 
#
# The `prepare` method should be used to prepare the action instance
# directory for command execution: input files generation, linking, 
# copying etc. The instance directory path at this time is init under
# `self.path`. Similarly, if the action has a parent action instance, 
# that directory location is found under `self.parent.path`. 
#
# For a full list of customizable argument and method fields inspect
# `teff_py.actions.ActionMeta` class. 
# One aim of my work is to provide reasonable default actions behavior.
#
# This was a lengthy protocol explanation, but the usage is compact
# and clear. First, we define the action for `extract_forceconstants`
# from TDEP:
class FCs(Action):
    command = local["extract_forceconstants"]  # this executable should be visible in $PATH
    num_mpi_procs = 16

    def make_args_list(self):
        # we expect to receive a source collection like:
        # {"rc2": 6.0, "rc3": 5.0}
        # from it we build a list of switches and args to our shell command:
        return [
            "-rc2", self.args_source["rc2"],
            "-rc3", self.args_source["rc3"],
        ]

    def make_prefix(self):
        # the label will look like: `{classname}.{rc2}_{rc3}`
        return "".join([
            self.__class__.__name__.lower(),
            ".", str(self.args_source["rc2"]),
            "_", str(self.args_source["rc3"]),
        ])

    @Action.change_state_on_prepare  # this decorator is required
    def prepare(self):
        # link the needed `infile.`-files from the example root directory above
        # (note the use of handy shell command shortcut from `plumbum`)
        files = ["forces", "meta", "positions", "ssposcar", "stat", "ucposcar"]
        for fname in files:
            ln(self.path+"/../infile."+fname,
               self.path+"/infile."+fname)


# And for the second stage, the action for TDEP's `thermal_conductivity` 
# is defined according to the same template.
class TC(Action):
    command = local["thermal_conductivity"]  # this executable should be visible in $PATH
    num_mpi_procs = 16

    def make_args_list(self):
        # We expect to receive a source collection like: {"qg": 16}
        # because one value is all we need to build a cubic grid.
        # We also expect to get a `FCs` instance as `parent` action.
        # The temperature is hard-coded to be 300K - but for other 
        # Actions we might want to parametrize over temperature too
        # or even use a switch for temperature range.
        # What's important imo is that my approach defines clear entry
        # points to perform such variations. 
        qg = self.args_source["qg"]
        return [
            "-qg", qg, qg, qg,
            "--temperature", str(300)
        ]

    def make_prefix(self):
        # the label will look like: `{classname}.{qg}`
        return "".join([
            self.__class__.__name__.lower(),
            ".", str(self.args_source["qg"]),
        ])

    @Action.change_state_on_prepare  # this decorator is required
    def prepare(self):
        # link ucposcar from the parent calculation
        ln(self.parent.path+"/infile.ucposcar", 
           self.path+"/infile.ucposcar")
        # link AND rename forceconstant files
        files = ["forceconstant", "forceconstant_thirdorder"]
        for fname in files:
            ln(self.parent.path+"/outfile."+fname,
               self.path+"/infile."+fname)


# Wrapping workflow method in a `plumbum.cli.Application`
# turns our python script into a proper shell program...
class WfApp(cli.Application):
    #...where the Q-point grid size can be an optionally switched attribute...
    qg_max = cli.SwitchAttr("--qg-max", int, default=5, help="max num of q-points along each coordinate")

    #...and the positional arguments will define a range of 2nd order FCs cutoff values.
    def main(self, rc2_start, rc2_stop, rc2_step=1):
        # In this `cli.Application`-wrapped `main` function
        # we define our workflow. Anything goes. For example:

        # 1. Build an array of `args_sources` for `FCs` from input arguments to our workflow:
        args_collections = [
            {"rc2": float(i), "rc3": float(i-1)}
            for i in range(int(rc2_start), 1+int(rc2_stop), int(rc2_step))
        ]

        results = []  # 2. Define empty results container

        # 3. prepare and run `extract_forceconstants` for each value of "rc2".
        # by default, a separate subfolder will be built:
        for a_coll in args_collections:
            fc = FCs(a_coll)
            fc.prepare()
            fc.run()

            # pipe = grep["-A1", "OVERDETERMINATION", fc.path+"/out.log"] | tail[-1] | awk['{ print $5 }']
            # over = int(pipe().strip())
            # print(over)
            # print(type(over))

            # 4. prepare and run offspring `thermal_conductivity` 
            # for each value of "qg".
            # by default, separate subfolders will be built; the subdir tree
            # reflects the hierarchy of calculations:
            for qg in range(3, self.qg_max+1):
                tc = TC({"qg": qg}, parent=fc)
                tc.prepare()
                tc.run()

                # 5. parse/collect results. 
                # Note that together with python file processing and regex utils
                # regular shell commands can be also used with `plumbum`.
                # Here I `cat` a file where a single lie is expected:
                tc_line = cat(op.join(tc.path, "outfile.thermal_conductivity"))
                results.append([
                    fc.args_source["rc2"], 
                    tc.args_source["qg"],
                    np.float64(tc_line.strip().split()[1]),
                    ])
 
        # 6. Postprocess collected results.
        # Here: building a dataframe and a histogram.
        df = pd.DataFrame( np.array(results), columns = ['rc2', 'qg', 'kappa'])
        
        print(df.sort_values(by='kappa', ascending=False).head(10))
        
        sns.set() 
        df = df.pivot(index='rc2', columns=['qg'], values='kappa')
        ax = sns.heatmap(df)
        plt.title("Resulting Thermal Conductivity Map")
        plt.show()  

# Finally, run our workflow when executing the script.
if __name__ == "__main__":
    WfApp.run()
