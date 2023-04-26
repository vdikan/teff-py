#!/path/to/python
#FIXME^ put a path to python

import logging
import os.path as op
import numpy as np
from plumbum import local, cli
from plumbum.cmd import cp, ln, pwd, mkdir, awk

from teff_py.actions import ActionLocal, State
from teff_py.tdep_utils import get_rcmax, get_overdetermination_report, get_r_squared

class ForceConstants(ActionLocal):
    command = local["extract_forceconstants"]
    num_mpi_procs = 16

    def make_args_list(self):
        return [ 
            "-rc2", self.args_source["rc2"], 
            "-rc3", self.args_source["rc3_fixed"],
            ]

    def make_prefix(self):
        return "".join([
            self.__class__.__name__.lower(),    
            "_", str(self.args_source["rc2"]),
        ])

    @ActionLocal.change_state_on_prepare
    def prepare(self):
        files = ["forces", "meta", "positions", "ssposcar", "stat", "ucposcar"]
        for fname in files:
            ln(self.path+"/../infile."+fname,
               self.path+"/infile."+fname)


class PhDispRel(ActionLocal):
    command = local["phonon_dispersion_relations"]
    num_mpi_procs = 16

    def make_args_list(self):
        return []

    def make_prefix(self):
        return self.__class__.__name__.lower()

    @ActionLocal.change_state_on_prepare
    def prepare(self):
        ln(self.parent.path+"/infile.ucposcar",
           self.path+"/infile.ucposcar")
        ln(self.parent.path+"/outfile.forceconstant",
           self.path+"/infile.forceconstant")


class ThermalConductivity(ActionLocal):
    command = local["thermal_conductivity"]  
    num_mpi_procs = 16

    def make_args_list(self):
        return [ "--temperature", str(300) ] #NOTE: T is hard pinned to 300K

    # def make_prefix(self):
    #     return "".join([ self.__class__.__name__.lower() ])

    @ActionLocal.change_state_on_prepare  # this decorator is required
    def prepare(self):
        ln(self.parent.path+"/infile.ucposcar", 
           self.path+"/infile.ucposcar")
        files = ["forceconstant", "forceconstant_thirdorder"]
        for fname in files:
            ln(self.parent.path+"/outfile."+fname,
               self.path+"/infile."+fname)


class WfApp(cli.Application):
    # qg_max = cli.SwitchAttr("--qg-max", int, default=5, help="max num of q-points along each coordinate")

    console = logging.StreamHandler()
    verbose_output = cli.Flag("-v", default=False)

    def logging_setup(self):
        "Setup logging handlers for the application"
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
            datefmt='%d-%m-%Y %H:%M',
            filename='wf.log',
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

    # def main(self, rc2_start, rc2_stop, rc2_step=1):
    def main(self):

        self.logging_setup()

        rcmax = get_rcmax("infile.ssposcar")
        rc3_fixed = rcmax * 0.66666
        rc_range = list(np.arange(2.0,rcmax,0.25))
        
        convergence_data = {}
        results = {}
        fc_calculations = {}

        for rc2 in rc_range:
            fc_calc = ForceConstants({"rc2": rc2, "rc3_fixed": rc3_fixed})
            fc_calc.prepare()
            fc_calc.run()
            fc_calculations[rc2] = fc_calc

            # phonons

            ph_disp = PhDispRel([], parent=fc_calc)
            ph_disp.prepare()
            ph_disp.run()

            freq_data_fname = ph_disp.path + "/outfile.dispersion_relations"
            freq_data = np.loadtxt(freq_data_fname)[:, 1:]
            freq_data = freq_data[freq_data != 0]
            is_positive = np.all(freq_data > 1e-4)

            if is_positive:
                results[rc2] = freq_data
                convergence_data[rc2] = {
                    "overd": get_overdetermination_report(fc_calc.path+"/out.log"),
                    "rsquared": get_r_squared(fc_calc.path+"/out.log"),
                }
                
        
        for i in range(1,len(rc_range)):
            rc_iter = rc_range[i]
            rc_prev = rc_range[i-1]
            # rel_error = np.nanmax((results[rc_iter] - results[rc_prev]))
            rel_error = np.nanmax((results[rc_iter] - results[rc_prev]) / results[rc_iter])
            if rel_error > 1e-5:

                # thermal conductivity
                fc_parent = fc_calculations[rc_iter]
                th_cond = ThermalConductivity([], parent=fc_parent)
                th_cond.prepare()
                th_cond.run()

                th_cond_res = float(awk("{ print $2 }", th_cond.path+"/outfile.thermal_conductivity").strip())

                print(
                    rc_iter, 
                    rel_error, 
                    convergence_data[rc_iter]["overd"][2][1],
                    convergence_data[rc_iter]["overd"][3][1],
                    convergence_data[rc_iter]["rsquared"][2],
                    convergence_data[rc_iter]["rsquared"][3],
                    th_cond_res,
                )
        
        # print(rc3_fixed)

if __name__ == "__main__":
    WfApp.run()