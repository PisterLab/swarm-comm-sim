"""
\brief Discrete-event simulation engine.
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

# ========================== imports =========================================

from builtins import zip
from builtins import str
from builtins import range
from past.utils import old_div
from collections import OrderedDict
import hashlib
import platform
import random
import sys
import threading
import time
import traceback
import json

from . import Mote
from . import SimSettings
from . import SimLog
from . import Connectivity
from . import SimConfig

# special SwarmSim import
# insert at 1, 0 is the script path (or '' in REPL)
import os
SIMENGINE_ROOT_PATH = os.path.dirname(__file__)
SWARM_SIM_MASTER_PATH = os.path.join(
    SIMENGINE_ROOT_PATH,
    '../../gym-swarm-sim/envs/swarmsimmaster'
)
sys.path.insert(1, SWARM_SIM_MASTER_PATH)
import comms_env
import numpy as np


# =========================== defines =========================================

# =========================== body ============================================

class DiscreteEventEngine(threading.Thread):

    #===== start singleton
    _instance      = None
    _init          = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DiscreteEventEngine,cls).__new__(cls)
        return cls._instance
    #===== end singleton

    def __init__(self, cpuID=None, run_id=None, verbose=False):

        #===== singleton
        cls = type(self)
        if cls._init:
            return
        cls._init = True
        #===== singleton

        try:
            # store params
            self.cpuID                          = cpuID
            self.run_id                         = run_id
            self.verbose                        = verbose

            # local variables
            self.dataLock                       = threading.RLock()
            self.pauseSem                       = threading.Semaphore(0)
            self.simPaused                      = False
            self.goOn                           = True
            self.asn                            = 0
            self.exc                            = None
            self.events                         = {}
            self.uniqueTagSchedule              = {}
            self.random_seed                    = None
            self._init_additional_local_variables()

            # initialize parent class
            threading.Thread.__init__(self)
            self.name                           = u'DiscreteEventEngine'
        except:
            # an exception happened when initializing the instance

            # destroy the singleton
            cls._instance         = None
            cls._init             = False
            raise

    def destroy(self):
        cls = type(self)
        if cls._init:
            # initialization finished without exception

            if self.is_alive():
                # thread is start'ed
                self.play()           # cause one more loop in thread
                self._actionEndSim()  # causes self.gOn to be set to False
                self.join()           # wait until thread is dead
            else:
                # thread NOT start'ed yet, or crashed

                # destroy the singleton
                cls._instance         = None
                cls._init             = False
        else:
            # initialization failed
            pass # do nothing, singleton already destroyed

    #======================== thread ==========================================

    def run(self):
        """ loop through events """
        try:
            # additional routine
            self._routine_thread_started()

            # consume events until self.goOn is False
            while self.goOn:
                # tell robotic simulator to run for 1 ASN
                self._robo_sim_loop()
                with self.dataLock:

                    # abort simulation when no more events
                    if not self.events:
                        break

                    # update the current ASN
                    self.asn += 1

                    # perform any inter-simulator synchronization
                    self._robo_sim_sync()

                    if self.asn not in self.events:
                        continue

                    intraSlotOrderKeys = list(self.events[self.asn].keys())
                    intraSlotOrderKeys.sort()

                    cbs = []
                    for intraSlotOrder in intraSlotOrderKeys:
                        for uniqueTag, cb in list(self.events[self.asn][intraSlotOrder].items()):
                            # if uniqueTag == "recvTag": populate rcving_mote neighbor pose table # TODO: figure this out as abstract call
                            cbs += [cb]
                            del self.uniqueTagSchedule[uniqueTag]
                    del self.events[self.asn]

                # call the callbacks (outside the dataLock)
                for cb in cbs:
                    cb()
                    # if rcv_cb: update rcving_mote neighbor pose table

                self._robo_sim_update()

        except Exception as e:
            # thread crashed

            # record the exception
            self.exc = e

            # additional routine
            self._routine_thread_crashed()

            # print
            output  = []
            output += [u'']
            output += [u'==============================']
            output += [u'']
            output += [u'CRASH in {0}!'.format(self.name)]
            output += [u'']
            output += [traceback.format_exc()]
            output += [u'==============================']
            output += [u'']
            output += [u'The current ASN is {0}'.format(self.asn)]
            output += [u'The log file is {0}'.format(
                self.settings.getOutputFile()
            )]
            output += [u'']
            output += [u'==============================']
            output += [u'config.json to reproduce:']
            output += [u'']
            output += [u'']
            output  = u'\n'.join(output)
            output += json.dumps(
                SimConfig.SimConfig.generate_config(
                    settings_dict = self.settings.__dict__,
                    random_seed   = self.random_seed
                ),
                indent = 4
            )
            output += u'\n\n==============================\n'

            sys.stderr.write(output)

            # flush all the buffered log data
            SimLog.SimLog().flush()

        else:
            # thread ended (gracefully)

            # no exception
            self.exc = None

            # additional routine
            self._routine_thread_ended()

        finally:

            # destroy this singleton
            cls = type(self)
            cls._instance                      = None
            cls._init                          = False

    def join(self):
        super(DiscreteEventEngine, self).join()
        if self.exc:
            raise self.exc

    #======================== public ==========================================

    # === getters/setters

    def getAsn(self):
        return self.asn

    #=== scheduling

    def scheduleAtAsn(self, asn, cb, uniqueTag, intraSlotOrder):
        """
        Schedule an event at a particular ASN in the future.
        Also removed all future events with the same uniqueTag.
        """

        # make sure we are scheduling in the future
        assert asn > self.asn

        # remove all events with same uniqueTag (the event will be rescheduled)
        self.removeFutureEvent(uniqueTag)

        with self.dataLock:

            if asn not in self.events:
                self.events[asn] = {
                    intraSlotOrder: OrderedDict([(uniqueTag, cb)])
                }

            elif intraSlotOrder not in self.events[asn]:
                self.events[asn][intraSlotOrder] = (
                    OrderedDict([(uniqueTag, cb)])
                )

            elif uniqueTag not in self.events[asn][intraSlotOrder]:
                self.events[asn][intraSlotOrder][uniqueTag] = cb

            else:
                self.events[asn][intraSlotOrder][uniqueTag] = cb

            self.uniqueTagSchedule[uniqueTag] = (asn, intraSlotOrder)

    def scheduleIn(self, delay, cb, uniqueTag, intraSlotOrder):
        """
        Schedule an event 'delay' seconds into the future.
        Also removed all future events with the same uniqueTag.
        """

        with self.dataLock:
            asn = int(self.asn + (float(delay) / float(self.settings.tsch_slotDuration)))

            self.scheduleAtAsn(asn, cb, uniqueTag, intraSlotOrder)

    # === play/pause

    def play(self):
        self._actionResumeSim()

    def pauseAtAsn(self,asn):
        self.scheduleAtAsn(
            asn              = asn,
            cb               = self._actionPauseSim,
            uniqueTag        = (u'DiscreteEventEngine', u'_actionPauseSim'),
            intraSlotOrder   = Mote.MoteDefines.INTRASLOTORDER_ADMINTASKS,
        )

    # === misc

    def is_scheduled(self, uniqueTag):
        with self.dataLock:
            return uniqueTag in self.uniqueTagSchedule

    def removeFutureEvent(self, uniqueTag):
        with self.dataLock:
            if uniqueTag not in self.uniqueTagSchedule:
                # new event, not need to delete old instances
                return

            # get old instances occurences
            (asn, intraSlotOrder) = self.uniqueTagSchedule[uniqueTag]

            # make sure it's in the future
            assert asn >= self.asn

            # delete it
            del self.uniqueTagSchedule[uniqueTag]
            del self.events[asn][intraSlotOrder][uniqueTag]

            # and cleanup event structure if it's empty
            if not self.events[asn][intraSlotOrder]:
                del self.events[asn][intraSlotOrder]

            if not self.events[asn]:
                del self.events[asn]

    def terminateSimulation(self,delay):
        with self.dataLock:
            self.asnEndExperiment = self.asn+delay
            self.scheduleAtAsn(
                    asn                = self.asn+delay,
                    cb                 = self._actionEndSim,
                    uniqueTag          = (u'DiscreteEventEngine', u'_actionEndSim'),
                    intraSlotOrder     = Mote.MoteDefines.INTRASLOTORDER_ADMINTASKS,
            )

    # ======================== private ========================================

    def _actionPauseSim(self):
        assert self.simPaused==False
        self.simPaused = True
        self.pauseSem.acquire()

    def _actionResumeSim(self):
        if self.simPaused:
            self.simPaused = False
            self.pauseSem.release()

    def _actionEndSim(self):
        with self.dataLock:
            self.goOn = False

    def _actionEndSlotframe(self):
        """Called at each end of slotframe_iteration."""

        slotframe_iteration = int(old_div(self.asn, self.settings.tsch_slotframeLength))

        # print
        if self.verbose:
            print(u'   slotframe_iteration: {0}/{1}'.format(slotframe_iteration, self.settings.exec_numSlotframesPerRun-1))

        # schedule next statistics collection
        self.scheduleAtAsn(
            asn              = self.asn + self.settings.tsch_slotframeLength,
            cb               = self._actionEndSlotframe,
            uniqueTag        = (u'DiscreteEventEngine', u'_actionEndSlotframe'),
            intraSlotOrder   = Mote.MoteDefines.INTRASLOTORDER_ADMINTASKS,
        )

    # ======================== abstract =======================================

    def _init_additional_local_variables(self):
        pass

    def _routine_thread_started(self):
        pass

    def _routine_thread_crashed(self):
        pass

    def _routine_thread_ended(self):
        pass

    # ======================= Robotic Simulator Abstract ===============================

    def _robo_sim_loop(self, steps=1):
        pass

    def _robo_sim_sync(self):
        pass

    def _robo_sim_update(self):
        pass


class SimEngine(DiscreteEventEngine):

    DAGROOT_ID = 0

    def _init_additional_local_variables(self):
        self.settings                   = SimSettings.SimSettings()

        # set random seed
        if   self.settings.exec_randomSeed == u'random':
            self.random_seed = random.randint(0, sys.maxsize)
        elif self.settings.exec_randomSeed == u'context':
            # with context for exec_randomSeed, an MD5 value of
            # 'startTime-hostname-run_id' is used for a random seed
            startTime = SimConfig.SimConfig.get_startTime()
            if startTime is None:
                startTime = time.time()
            context = (platform.uname()[1], str(startTime), str(self.run_id))
            md5 = hashlib.md5()
            md5.update(u'-'.join(context).encode('utf-8'))
            self.random_seed = int(md5.hexdigest(), 16) % sys.maxsize
        else:
            assert isinstance(self.settings.exec_randomSeed, int)
            self.random_seed = self.settings.exec_randomSeed
        # apply the random seed; log the seed after self.log is initialized
        random.seed(a=self.random_seed)

        if self.settings.motes_eui64:
            eui64_table = self.settings.motes_eui64[:]
            if len(eui64_table) < self.settings.exec_numMotes:
                eui64_table.extend(
                    [None] * (self.settings.exec_numMotes - len(eui64_table))
                )
        else:
            eui64_table = [None] * self.settings.exec_numMotes

        self.motes = [
            Mote.Mote.Mote(id, eui64)
            for id, eui64 in zip(
                    list(range(self.settings.exec_numMotes)),
                    eui64_table
            )
        ]

        eui64_list = set([mote.get_mac_addr() for mote in self.motes])
        if len(eui64_list) != len(self.motes):
            assert len(eui64_list) < len(self.motes)
            raise ValueError(u'given motes_eui64 causes duplicates')

        # SwarmSim, TODO: this will be an RPC call implemented by the socket recipent
        # TODO: perform exchange of ASN information for SwarmSim timesteps
        # TODO: scale velocities accordingly, not terribly important right now
        robotCoords                     = [(float(i) / 10, 0, 0) for i in range(self.settings.exec_numMotes)] # FIXME: this isn't actually changing coordinates
        print(robotCoords)
        self.robot_sim                  = comms_env.SwarmSimCommsEnv(robotCoords)
        self.robot_sim.mote_key_map     = {}

        moteStates = self.robot_sim.get_all_mote_states()
        print(moteStates) # hmmm
        print(self.motes)
        for i, robot_mote_id in enumerate(moteStates.keys()):
            mote = self.motes[i]
            self.robot_sim.mote_key_map[mote.id] = robot_mote_id
            mote.setLocation(*(moteStates[robot_mote_id][:2]))
            print(mote.getLocation())

        self.connectivity               = Connectivity.Connectivity(self)
        self.log                        = SimLog.SimLog().log
        SimLog.SimLog().set_simengine(self)

        # log the random seed
        self.log(
            SimLog.LOG_SIMULATOR_RANDOM_SEED,
            {
                u'value': self.random_seed
            }
        )
        # flush buffered logs, which are supposed to be 'config' and
        # 'random_seed' lines, right now. This could help, for instance, when a
        # simulation is stuck by an infinite loop without writing these
        # 'config' and 'random_seed' to a log file.
        SimLog.SimLog().flush()

        # select dagRoot
        self.motes[self.DAGROOT_ID].setDagRoot()

        # boot all motes
        for i in range(len(self.motes)):
            self.motes[i].boot()

        print("Completed SimEngine Init.")

    def _routine_thread_started(self):
        # log
        self.log(
            SimLog.LOG_SIMULATOR_STATE,
            {
                u'name':   self.name,
                u'state':  u'started'
            }
        )

        # schedule end of simulation
        self.scheduleAtAsn(
            asn              = self.settings.tsch_slotframeLength*self.settings.exec_numSlotframesPerRun,
            cb               = self._actionEndSim,
            uniqueTag        = (u'SimEngine',u'_actionEndSim'),
            intraSlotOrder   = Mote.MoteDefines.INTRASLOTORDER_ADMINTASKS,
        )

        # schedule action at every end of slotframe_iteration
        self.scheduleAtAsn(
            asn              = self.asn + self.settings.tsch_slotframeLength - 1,
            cb               = self._actionEndSlotframe,
            uniqueTag        = (u'SimEngine', u'_actionEndSlotframe'),
            intraSlotOrder   = Mote.MoteDefines.INTRASLOTORDER_ADMINTASKS,
        )

    def _routine_thread_crashed(self):
        # log
        self.log(
            SimLog.LOG_SIMULATOR_STATE,
            {
                "name": self.name,
                "state": "crash"
            }
        )

    def _routine_thread_ended(self):
        # log
        self.log(
            SimLog.LOG_SIMULATOR_STATE,
            {
                "name": self.name,
                "state": "stopped"
            }
        )

    def get_mote_by_mac_addr(self, mac_addr):
        for mote in self.motes:
            if mote.is_my_mac_addr(mac_addr):
                return mote
        return None

    def get_mote_by_id(self, mote_id):
        # there must be a mote having mote_id. otherwise, the following line
        # raises an exception.
        return [mote for mote in self.motes if mote.id == mote_id][0]

    # ============== Robot Simulator Communication ====================

    def _robo_sim_loop(self, steps=1):
        self.robot_sim.main_loop(steps)

    def _robo_sim_sync(self):
        states = self.robot_sim.get_all_mote_states()
        for mote in self.motes:
            mote.setLocation(*(states[self.robot_sim.mote_key_map[mote.id]][:2]))
        
        self.connectivity.matrix.update()

    def _robo_sim_update(self):
        if self.asn % self.settings.rrsf_slotframe_len != 0:
            return

        agent_neighbor_dict = {}
        for agent in self.motes:
            if agent.neighbors:
                agent_neighbor_dict[self.robot_sim.mote_key_map[agent.id]] = agent.neighbors
                agent.neighbors = [] # flush neighbors

        self.robot_sim.set_all_mote_neighbors(agent_neighbor_dict)

    def _robo_sim_control(self):
        # NOTE: DEPRECATED
        # TODO: can make this modular (have an abstract control class that's set in config)

        R_COLLISION, R_CONNECTION = 1, 10
        R1, R2 = R_COLLISION, R_CONNECTION
        k_col, k_conn = R1*R1 + R2, R2

        control_inputs = {}
        for agent in self.motes:
            vx, vy, vz = 0, 0, 0
            for neighbor in self.mote_neighbors(agent):
                x1, y1 = agent.getLocation()
                x2, y2 = neighbor.getLocation()

                dist = np.sqrt((x2-x1)**2 + (y2-y1)**2)

                if agent == neighbor:
                    continue
                
                vx += 2*(x1-x2) * (k_conn*np.exp((dist)/(R2*R2)) / (R2*R2) - k_col*np.exp(-(dist)/(R1*R1)) / (R1*R1))
                vy += 2*(y1-y2) * (k_conn*np.exp((dist)/(R2*R2)) / (R2*R2) - k_col*np.exp(-(dist)/(R1*R1)) / (R1*R1))
                vz += 0
                
            control_inputs[self.robot_sim.mote_key_map[agent.id]] = (-vx, -vy, -vz)

        self.robot_sim.assign_velos(control_inputs)

    def mote_neighbors(self, agent):
        # TODO: include other cases (i.e. everyone needs to be updated??)
        # TODO: should maybe include a frequency at which things can be propagated for potential control
        conn_model = self.settings.control_connectivity_model
        if conn_model == "Full":
            return self.motes
        elif conn_model == "Updated":
            raise NotImplementedError()

        # TODO: move this to connectivity matrix modelling yeah?

        return self.motes
