"Asynchronous workflow actions definitions."

import asyncio
import copy
from teff_py.actions import Action, State


class ScheduledAction(Action):
    "REVIEW: Experimental base action for asynchronous remote submission."
    async def submit_hook(self):
        raise NotImplementedError

    async def run_hook(self):
        raise NotImplementedError

    async def run(self):
        if self.state == State.PREPARED:
            super().run()       # action task submission command
            self.state = State.SUBMITTED
            await self.submit_hook()

        await self.run_hook()


class SlurmScheduledAction(ScheduledAction):
    "REVIEW: Action to be dispatched on remote with Slurm sheduler."
    _id = None
    poll_interval = 5           # polling time interval, seconds
   
    @property
    def id(self):
        return copy.deepcopy(self._id)

    async def submit_hook(self):
        session = self.command.machine.session()
        self._id = session.run(
            "cat %s/out.log | awk '{print $4}'" % self.path
        )[1].strip()

    async def run_hook(self):
        session = self.command.machine.session()
        while len(session.run("squeue | grep %s" % self.id,
                              retcode=None)[1]) > 0:
            print("Waiting for task %s - %s" %
                  (self.make_prefix(), self.id))
            await asyncio.sleep(self.poll_interval)
        print("Finished task %s - %s" % (self.make_prefix(), self.id))
