
import importlib
import logging
from core import matter
from core.swarm_sim_header import *
from core import agent
import numpy as np

TIMESTEP = .1 # NOTE: atm this is roughly equivalent to the length of a slotframe, should be much higher fidelity when fully 6TiSCH integrated

class VeloAgent(agent.Agent):
    def __init__(self, world, coordinates, color, agent_counter=0, velocities = None):
        super().__init__(world, coordinates, color)
        self.neighbors = []

    # change in time is one round
    # function adds the velo to the position

    # TODO: Refactor with the parent class to remove the code written twice.
    def move(self):
        #check to make sure that this doesnt throw an error and conforms to grid types.
        direction_coord = tuple(np.add(np.array(self.velocities) * TIMESTEP, self.coordinates))
        direction_coord = self.check_within_border(self.velocities, direction_coord)
        if self.world.grid.are_valid_coordinates(direction_coord) \
                and direction_coord not in self.world.agent_map_coordinates \
                and not self._Agent__isCarried: # this is a little jank IK
            if self.coordinates in self.world.agent_map_coordinates:
                del self.world.agent_map_coordinates[self.coordinates]
            self.coordinates = direction_coord
            self.world.agent_map_coordinates[self.coordinates] = self
            if self.world.vis is not None:
                self.world.vis.agent_changed(self)
            logging.info("Agent %s successfully moved to %s", str(self.get_id()), self.coordinates)
            self.world.csv_round.update_metrics(steps=1)
            self.csv_agent_writer.write_agent(steps=1)
            self.check_for_carried_matter()
            return True

        return False

    # updates the velocities
    def set_velocities(self, new_velocities):
        self.velocities = tuple(np.hstack([np.array(new_velocities), np.zeros(1)])[:3])

    # adds to the velocities.
    def add_velocities(self, dv):
        self.velocities = tuple(np.add(self.velocities, dv))

    def get_velocities(self):
        return tuple(self.velocities)
