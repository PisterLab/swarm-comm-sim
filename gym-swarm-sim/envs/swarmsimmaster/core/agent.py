"""
.. module:: agent
   :platform: Unix, Windows
   :synopsis: This module provides the interfaces of the agents

.. moduleauthor:: Ahmad Reza Cheraghi

TODO: Erase Memory

"""
import importlib
import logging
from core import matter
from core.swarm_sim_header import *


class Agent(matter.Matter):

    def __init__(self, world, coordinates, color, agent_counter=0):
        """Initializing the agent"""
        super().__init__(world, coordinates, color, agent_counter)
        self.number = agent_counter
        self.__isCarried = False
        self.carried_item = None
        self.carried_agent = None
        self.steps = 0
        self.velocities = (0.0,) * 3
        csv_generator_module = importlib.import_module('components.generators.csv.%s' % world.config_data.csv_generator)
        self.csv_agent_writer = csv_generator_module.CsvAgentData(self.get_id(), self.number)

    def carries_item(self):
        if self.carried_item is None:
            return False
        else:
            return True

    def carries_agent(self):
        if self.carried_agent is None:
            return False
        else:
            return True

    def is_carried(self):
        """
        Get the status if it is taken or not
        :return: boolean, carried status
        """
        return self.__isCarried

    def is_on_item(self):
        """
        Checks if the agent is on an item

        :return: boolean, True if on item
        """
        if self.coordinates in self.world.item_map_coordinates:
            return True
        else:
            return False

    def is_on_location(self):
        """
        Checks if the agent is on a location

        :return: True: On a location; False: Not on a location
        """
        if self.coordinates in self.world.location_map_coordinates:
            return True
        else:
            return False

    def move_to(self, direction):
        """
        Moves the agent to the given direction

        :param direction: The direction is defined by loaded grid class
        :return: True: Success Moving;  False: Non moving
        """
        self.velocities = direction
        direction_coord = get_coordinates_in_direction(self.coordinates, direction)
        direction_coord = self.check_within_border(direction, direction_coord)
        if self.world.grid.are_valid_coordinates(direction_coord) \
                and direction_coord not in self.world.agent_map_coordinates \
                and not self.__isCarried:
            if self.coordinates in self.world.agent_map_coordinates:
                del self.world.agent_map_coordinates[self.coordinates]
            self.coordinates = direction_coord
            self.world.agent_map_coordinates[self.coordinates] = self
            if self.world.vis is not None:
                self.world.vis.agent_changed(self)
            logging.info("Agent %s successfully moved to %s", str(self.get_id()), direction)
            self.world.csv_round.update_metrics(steps=1)
            self.csv_agent_writer.write_agent(steps=1)
            self.check_for_carried_matter()
            return True

        return False

    def check_for_carried_matter(self):
        if self.carried_item is not None:
            self.carried_item.coordinates = self.coordinates
            if self.world.vis is not None:
                self.world.vis.item_changed(self.carried_item)
        elif self.carried_agent is not None:
            self.carried_agent.coordinates = self.coordinates
            if self.world.vis is not None:
                self.world.vis.agent_changed(self.carried_agent)

    def check_within_border(self, direction, direction_coord):
        if self.world.config_data.border == 1:
            if self.world.config_data.type == 1:
                if abs(direction_coord[0]) > self.world.get_x_size():
                    direction_coord = (
                        -1 * (self.coordinates[0] - direction[0]), direction_coord[1], direction_coord[2])
                if abs(direction_coord[1]) > self.world.get_y_size():
                    direction_coord = (
                        direction_coord[0], -1 * (self.coordinates[1] - direction[1]), direction_coord[2])
                if abs(direction_coord[2]) > self.world.get_z_size():
                    direction_coord = (
                        direction_coord[0], direction_coord[1], -1 * (self.coordinates[2] - direction[2]))
            else:
                if abs(direction_coord[0]) > self.world.get_x_size():
                    direction_coord = (self.coordinates[0], direction_coord[1], direction_coord[2])
                if abs(direction_coord[1]) > self.world.get_y_size():
                    direction_coord = (direction_coord[0], self.coordinates[1], direction_coord[2])
                if abs(direction_coord[2]) > self.world.get_z_size():
                    direction_coord = (direction_coord[0], direction_coord[1], self.coordinates[2])
        return direction_coord

    def read_from_with(self, target, key=None):
        """
        Read the memories from the matter's memories with a given keyword

        :param target: The target matter
        :param key: A string keyword to search for the data in the memory
        :return: The matters memory; None
        """
        if key is not None:
            tmp_memory = target.read_memory_with(key)
        else:
            tmp_memory = target.read_whole_memory()

        if tmp_memory is not None \
                and not (hasattr(tmp_memory, '__len__')) or len(tmp_memory) > 0:
            if target.type == MatterType.AGENT:
                self.world.csv_round.update_metrics(agent_read=1)
                self.csv_agent_writer.write_agent(agent_read=1)
            elif target.type == MatterType.ITEM:
                self.world.csv_round.update_metrics(item_read=1)
                self.csv_agent_writer.write_agent(item_read=1)
            elif target.type == MatterType.LOCATION:
                self.world.csv_round.update_metrics(location_read=1)
                self.csv_agent_writer.write_agent(location_read=1)
            return tmp_memory
        return None

    def matter_in(self, direction):
        """
        :param direction: the direction to check if a matter is there
        :return: True: if a matter is there, False: if not
        """
        coords = get_coordinates_in_direction(self.coordinates, direction)
        return (coords in self.world.get_item_map_coordinates() or
                coords in self.world.get_agent_map_coordinates() or
                coords in self.world.get_location_map_coordinates())

    def item_in(self, direction):
        """
        :param direction: the direction to check if an item is there
        :return: True: if an item is there, False: if not
        """
        return get_coordinates_in_direction(self.coordinates, direction) in self.world.get_item_map_coordinates()

    def agent_in(self, direction):
        """
        :param direction: the direction to check if an agent is there
        :return: True: if an agent is there, False: if not
        """
        return get_coordinates_in_direction(self.coordinates, direction) in self.world.get_agent_map_coordinates()

    def location_in(self, direction):
        """
        :param direction: the direction to check if a location is there
        :return: True: if a location is there, False: if not
        """
        return get_coordinates_in_direction(self.coordinates, direction) in self.world.get_location_map_coordinates()

    def get_matter_in(self, direction):
        if get_coordinates_in_direction(self.coordinates, direction) in self.world.get_item_map_coordinates():
            return self.world.get_item_map_coordinates()[get_coordinates_in_direction(self.coordinates, direction)]
        elif get_coordinates_in_direction(self.coordinates, direction) in self.world.get_agent_map_coordinates():
            return self.world.get_agent_map_coordinates()[get_coordinates_in_direction(self.coordinates, direction)]
        elif get_coordinates_in_direction(self.coordinates, direction) in self.world.get_location_map_coordinates():
            return self.world.get_location_map_coordinates()[get_coordinates_in_direction(self.coordinates, direction)]
        else:
            return False

    def get_item_in(self, direction):
        if get_coordinates_in_direction(self.coordinates, direction) in self.world.get_item_map_coordinates():
            return self.world.get_item_map_coordinates()[get_coordinates_in_direction(self.coordinates, direction)]
        else:
            return False

    def get_agent_in(self, direction):
        if get_coordinates_in_direction(self.coordinates, direction) in self.world.get_agent_map_coordinates():
            return self.world.get_agent_map_coordinates()[get_coordinates_in_direction(self.coordinates, direction)]
        else:
            return False

    def get_location_in(self, direction):
        if get_coordinates_in_direction(self.coordinates, direction) in self.world.get_location_map_coordinates():
            return self.world.get_location_map_coordinates()[get_coordinates_in_direction(self.coordinates, direction)]
        else:
            return False

    def get_location(self):
        if self.coordinates in self.world.location_map_coordinates:
            return self.world.get_location_map_coordinates()[self.coordinates]
        else:
            return False

    def get_item(self):
        if self.coordinates in self.world.get_item_map_coordinates():
            return self.world.get_item_map_coordinates()[self.coordinates]
        else:
            return False

    def write_to_with(self, target, key=None, data=None):
        """
        Writes data with given a keyword direction on the matters memory

        :param target: The matter
        :param key: A string keyword so to order the data that is written into the memory
        :param data: The data that should be stored into the memory
        :return: True: Successful written into the memory; False: Unsuccessful
        """
        if data is not None:
            if key is None:
                wrote = target.write_memory(data)
            else:
                wrote = target.write_memory_with(key, data)
            if wrote:
                if target.type == MatterType.AGENT:
                    self.world.csv_round.update_metrics(agent_write=1)
                    self.csv_agent_writer.write_agent(agent_write=1)
                elif target.type == MatterType.ITEM:
                    self.world.csv_round.update_metrics(item_write=1)
                    self.csv_agent_writer.write_agent(item_write=1)
                elif target.type == MatterType.LOCATION:
                    self.world.csv_round.update_metrics(location_write=1)
                    self.csv_agent_writer.write_agent(location_write=1)
                return True
            else:
                return False
        else:
            return False

    def scan_for_matters_within(self, matter_type=MatterType.UNDEFINED, hop=1):
        """
        Scans for agents, items and locations on a given hop distance and all the matters within the hop distance

        :todo: If nothing then everything should be scanned

        :param matter_type: For what matter this method should scan for.
                            Can be either agents, items, locations, or all (undefined mattertype)
        :param hop: The hop distance from the actual position of the scanning agent
        :return: A list of the found matter
        """

        within_hop_list = []
        for i in range(hop + 1):
            in_list = self.scan_for_matters_in(matter_type, i)
            if in_list is not None:
                within_hop_list.extend(in_list)
        if len(within_hop_list) != 0:
            return within_hop_list
        else:
            return None

    def scan_for_matters_in(self, matter_type=MatterType.UNDEFINED, hop=1):
        """
         Scanning for agents, items, or locations on a given hop distance

         :param matter_type: For what matter this method should scan for.
                             Can be either agents, items, locations, or (default) all (undefined mattertype)
         :param hop: The hop distance from thee actual position of the scanning agent
         :return: A list of the founded matters
         """

        logging.info("Agent on %s is scanning for %s in %i hops", str(self.coordinates), matter_type, hop)

        if matter_type == MatterType.AGENT:
            scanned_list = scan_in(self.world.agent_map_coordinates, self.coordinates, hop, self.world.grid)
        elif matter_type == MatterType.ITEM:
            scanned_list = scan_in(self.world.item_map_coordinates, self.coordinates, hop, self.world.grid)
        elif matter_type == MatterType.LOCATION:
            scanned_list = scan_in(self.world.location_map_coordinates, self.coordinates, hop, self.world.grid)
        else:
            scanned_list = []
            scanned_list.extend(scan_in(self.world.agent_map_coordinates, self.coordinates, hop, self.world.grid))
            scanned_list.extend(scan_in(self.world.item_map_coordinates, self.coordinates, hop, self.world.grid))
            scanned_list.extend(scan_in(self.world.location_map_coordinates, self.coordinates, hop, self.world.grid))
        return scanned_list

    def scan_for_agents_within(self, hop=1):
        """
        Scans for agents on a given hop distance and all the matters within the hop distance

        :todo: If nothing then everything should be scanned

        :param hop: The hop distance from the actual position of the scanning agent
        :return: A list of the founded matters
        """
        return scan_within(self.world.agent_map_coordinates, self.coordinates, hop, self.world.grid)

    def scan_for_agents_in(self, hop=1):
        """
        Scanning for agents on a given hop distance

        :param hop: The hop distance from thee actual position of the scanning agent
        :return: A list of the founded matters
        """

        return scan_in(self.world.agent_map_coordinates, self.coordinates, hop, self.world.grid)

    def scan_for_items_within(self, hop=1):
        """
        Scans for items on a given hop distance and all the matters within the hop distance

        :todo: If nothing then everything should be scanned

        :param hop: The hop distance from the actual position of the scanning agent
        :return: A list of the founded matters
        """

        return scan_within(self.world.item_map_coordinates, self.coordinates, hop, self.world.grid)

    def scan_for_items_in(self, hop=1):
        """
        Scanning for items on a given hop distance

        :param hop: The hop distance from thee actual position of the scanning agent
        :return: A list of the founded matters
        """
        return scan_in(self.world.item_map_coordinates, self.coordinates, hop, self.world.grid)

    def scan_for_locations_within(self, hop=1):
        """
        Scans for locations on a given hop distance and all the matters within the hop distance

        :todo: If nothing then everything should be scanned

        :param hop: The hop distance from the actual position of the scanning agent
        :return: A list of the founded matters
        """

        return scan_within(self.world.location_map_coordinates, self.coordinates, hop, self.world.grid)

    def scan_for_locations_in(self, hop=1):
        """
        Scanning for location on a given hop distance

        :param hop: The hop distance from thee actual position of the scanning agent
        :return: A list of the founded matters
        """
        return scan_in(self.world.location_map_coordinates, self.coordinates, hop, self.world.grid)

    def take_me(self, coordinates):
        """
        The agent is getting taken by another other agent on the given coordinate

        :param coordinates, the coordinates of the agent which takes this agent
        :return: True: Successful taken; False: Cannot be taken or wrong Coordinates
        """

        if not self.__isCarried:
            if self.coordinates in self.world.agent_map_coordinates:
                del self.world.agent_map_coordinates[self.coordinates]
            self.__isCarried = True
            self.coordinates = coordinates
            if self.world.vis is not None:
                self.world.vis.agent_changed(self)
            return True
        else:
            return False

    def drop_me(self, coordinates):
        """
        The actual agent is getting dropped

        :param coordinates: the given position
        :return: None
        """
        self.coordinates = coordinates
        self.world.agent_map_coordinates[coordinates] = self
        self.__isCarried = False
        if self.world.vis is not None:
            self.world.vis.agent_changed(self)

    def create_item(self):
        """
        Creates an item on the agents actual position
        :return: New item or False
        """
        return self.create_item_on(self.coordinates)

    def create_item_in(self, direction=None):
        """
        Creates an item in a given direction
        :param direction: The direction on which the item should be created.
        :return: New item or False
        """
        if direction is not None:
            coordinates = get_coordinates_in_direction(self.coordinates, direction)
            return self.create_item_on(coordinates)
        else:
            logging.info("Not created item")
            return False

    def create_item_on(self, coordinates=None):
        """
        Creates an item either on given coordinates
        :param coordinates: the coordinates
        :return: New Item or False
        """

        logging.info("item with id %s is", self.get_id())
        if coordinates is not None:
            if self.world.grid.are_valid_coordinates(coordinates):
                logging.info("Going to create an item on position %s" % str(coordinates))
                if self.world.add_item(coordinates):
                    self.world.item_map_coordinates[coordinates].created = True
                    self.world.new_item_flag = True
                    self.csv_agent_writer.write_agent(items_created=1)
                    self.world.csv_round.update_items_num(len(self.world.get_items_list()))
                    self.world.csv_round.update_metrics(items_created=1)
                    return True
                else:
                    logging.info("Not created item on coordinates %s" % str(coordinates))
                    return False
            else:
                logging.info("Not created item on coordinates %s" % str(coordinates))
                return False

    def delete_item(self):
        """
        Deletes an item on current position
        :return: True: Deleting successful; False: Deleting unsuccessful
        """
        logging.info("Agent %s is" % self.get_id())
        logging.info("is going to delete an item on current position")
        if self.coordinates in self.world.get_item_map_coordinates():
            if self.world.remove_item_on(self.coordinates):
                self.csv_agent_writer.write_agent(items_deleted=1)
                return True
        else:
            logging.info("Could not delete item")
            return False

    def delete_item_with(self, item_id):
        """
        Deletes an item with a given item-id

        :param item_id: The id of the item that should be deleted
        :return: True: Deleting successful; False: Deleting unsuccessful
        """
        logging.info("Agent %s is" % self.get_id())
        logging.info("is going to delete an item with id %s" % str(item_id))
        if self.world.remove_item(item_id):
            self.csv_agent_writer.write_agent(items_deleted=1)
            return True
        else:
            logging.info("Could not delete item with id %s" % str(item_id))
            return False

    def delete_item_in(self, direction=None):
        """
        Deletes an item in a given direction

        :param direction: The direction on which the item should be deleted.

        :return: True: Deleting successful; False: Deleting unsuccessful
        """
        coordinates = ()
        if direction is not None:
            coordinates = get_coordinates_in_direction(self.coordinates, direction)
            logging.info("Deleting item in %s direction" % str(direction))
            if coordinates is not None:
                if self.world.remove_item_on(coordinates):
                    logging.info("Deleted item on coordinates %s" % str(coordinates))
                    self.csv_agent_writer.write_agent(items_deleted=1)
                    return True
                else:
                    logging.info("Could not delete item on coordinates %s" % str(coordinates))
                    return False
        else:
            logging.info("Could not delete item on coordinates %s" % str(coordinates))
            return False

    def delete_item_on(self, coordinates):
        """
        Deletes an item on a given x,y coordinates
,
        :param coordinates: items coordinates
        :return: True: Deleting successful; False: Deleting unsuccessful
        """
        if self.world.remove_item_on(coordinates):
            logging.info("Deleted item on coordinates %s" % str(coordinates))
            self.csv_agent_writer.write_agent(items_deleted=1)
            return True
        else:
            logging.info("Could not delete item on coordinates %s" % str(coordinates))
            return False

    def take_item_with(self, item_id):
        """
        Takes an item with a given id

        :param item_id:  The id of the item that should be taken
        :return: True: successful taken; False: unsuccessful taken
        """
        if self.carried_agent is None and self.carried_item is None:
            if item_id in self.world.item_map_id:
                self.carried_item = self.world.item_map_id[item_id]
                if self.carried_item.take():
                    logging.info("Item with id %s has been taken", str(item_id))
                    self.carried_item.coordinates = self.coordinates
                    if self.world.vis is not None:
                        self.world.vis.item_changed(self.carried_item)
                    self.world.csv_round.update_metrics(items_taken=1)
                    self.csv_agent_writer.write_agent(items_taken=1)
                    return True
                else:
                    self.carried_item = None
                    logging.info("Item with id %s could not be taken" % str(item_id))
                    return False
            else:
                logging.info("Item with id %s is not in the world" % str(item_id))
                return False
        else:

            logging.info("Item cannot taken because agent is carrying either an item or an agent already (%s, %s)"
                         % (str(self.carried_item), str(self.carried_agent)))
            return False

    def take_item_in(self, direction):
        """
        Takes an item that is in a given direction

        :param direction: The direction on which the item should be taken.
        :return: True: successful taken; False: unsuccessful taken
        """
        coordinates = get_coordinates_in_direction(self.coordinates, direction)
        return self.take_item_on(coordinates)

    def take_item_on(self, coordinates):
        """
        Takes an item on given coordinates

        :param coordinates of the item
        :return: True: successful taken; False: unsuccessful taken
        """
        if self.world.grid.are_valid_coordinates(coordinates):
            if coordinates in self.world.item_map_coordinates:
                return self.take_item_with(self.world.item_map_coordinates[coordinates].get_id())
            else:
                logging.info("There is no Item at %s" % str(coordinates))
                return False
        else:
            logging.info("invalid coordinates %s" % str(coordinates))
            return False

    def take_item(self):
        """
        Takes an item on the actual position

        :return: True: successful taken; False: unsuccessful taken
        """
        return self.take_item_on(self.coordinates)

    def drop_item(self):
        """
        Drops the taken item on the agents actual position

        :return: None
        """
        return self.drop_item_on(self.coordinates)

    def drop_item_in(self, direction):
        """
        Drops the taken item on a given direction

         :param direction: The direction on which the item should be dropped.
        """
        return self.drop_item_on(get_coordinates_in_direction(self.coordinates, direction))

    def drop_item_on(self, coordinates):
        """
        Drops the taken item on a given direction

        :param coordinates
        """
        if self.carried_item is not None:
            if self.world.grid.are_valid_coordinates(coordinates):
                if coordinates not in self.world.get_item_map_coordinates():
                    try:  # cher: insert so to overcome the AttributeError
                        self.carried_item.drop_me(coordinates)
                    except AttributeError:
                        pass
                    self.carried_item = None
                    self.world.csv_round.update_metrics(items_dropped=1)
                    self.csv_agent_writer.write_agent(items_dropped=1)
                    logging.info("Dropped item on %s coordinate", str(coordinates))
                    return True
                else:
                    logging.info("It is not possible to drop the item on that position because it is occupied")
                    return False
            else:
                logging.info("Wrong coordinates for dropping the item")
                return False
        else:
            logging.info("No item is taken for dropping")
            return False

    def create_agent(self):
        """
        Creates an agent on the agents actual position

        :return: New Agent or False
        """
        logging.info("Going to create on position %s", str(self.coordinates))
        new_agent = self.world.add_agent(self.coordinates)
        if new_agent:
            self.world.agent_map_coordinates[self.coordinates[0], self.coordinates[1]].created = True
            self.csv_agent_writer.write_agent(agents_created=1)
            self.world.csv_round.update_agent_num(len(self.world.get_agent_list()))
            self.world.csv_round.update_metrics(agents_created=1)
            return new_agent
        else:
            return False

    def create_agent_in(self, direction=None):
        """
        Creates an agent either in a given direction

        :toDo: separate the direction and coordinates and delete state

        :param direction: The direction on which the agent should be created.
        :return: New Agent or False
        """
        if direction is not None:
            coordinates = get_coordinates_in_direction(self.coordinates, direction)
            logging.info("Going to create an agent in %s on position %s", str(direction), str(coordinates))
            new_agent = self.world.add_agent(coordinates)
            if new_agent:
                self.world.agent_map_coordinates[coordinates].created = True
                logging.info("Created an agent on coordinates %s", coordinates)
                self.world.csv_round.update_agent_num(len(self.world.get_agent_list()))
                self.world.csv_round.update_metrics(agents_created=1)
                self.csv_agent_writer.write_agent(agents_created=1)
                return new_agent
            else:
                return False
        else:
            logging.info("Agent not created. invalid direction (None)")
            return False

    def create_agent_on(self, coordinates):
        """
        Creates an agent either on the given coordinates

        :toDo: separate the direction and coordinates and delete state

        :param coordinates: the coordinates
        :return: New Agent or False
        """
        if coordinates is not None:
            if self.world.grid.are_valid_coordinates(coordinates):
                logging.info("Going to create an agent on position %s" % str(coordinates))
                new_agent = self.world.add_agent(coordinates)
                if new_agent:
                    self.world.agent_map_coordinates[coordinates].created = True
                    logging.info("Created an agent on coordinates %s" % str(coordinates))
                    self.world.csv_round.update_agent_num(len(self.world.get_agent_list()))
                    self.world.csv_round.update_metrics(agents_created=1)
                    self.csv_agent_writer.write_agent(agents_created=1)
                    return new_agent
                else:
                    return False
            else:
                return False
        else:
            logging.info("Not created agent on coordinates %s" % str(coordinates))
            return False

    def delete_agent(self):
        """
        Deletes an agent on current position

        :return: True: Deleting successful; False: Deleting unsuccessful
        """
        logging.info("Agent %s is", self.get_id())
        logging.info("is going to delete an Agent on current position")
        if self.coordinates in self.world.get_agent_map_coordinates():
            if self.world.remove_agent_on(self.coordinates):
                self.csv_agent_writer.write_agent(agents_deleted=1)
                return True
        else:
            logging.info("Could not delete agent")
            return False

    def delete_agent_with(self, agent_id):
        """
        Deletes an agent with a given id

        :param agent_id: The id of the agent that should be deleted
        :return: True: Deleting successful; False: Deleting unsuccessful
        """
        logging.info("Agent %s is", self.get_id())
        logging.info("is going to delete an agent with id %s" % str(agent_id))
        if self.world.remove_agent(agent_id):
            self.csv_agent_writer.write_agent(agents_deleted=1)
            return True
        else:
            logging.info("Could not delete agent with id %s" % str(agent_id))
            return False

    def delete_agent_in(self, direction=None):
        """
        Deletes an agent either in a given direction

        :param direction: The direction on which the agent should be deleted
        :return: True: Deleting successful; False: Deleting unsuccessful
        """
        if direction is not None:
            coordinates = get_coordinates_in_direction(self.coordinates, direction)
            logging.info("Deleting Agent in %s direction" % str(direction))
            if self.world.remove_agent_on(coordinates):
                logging.info("Deleted Agent on coordinates %s" % str(coordinates))
                self.csv_agent_writer.write_agent(agents_deleted=1)
                return True
            else:
                logging.info("Could not delete Agent on coordinates %s" % str(coordinates))
                return False

    def delete_agent_on(self, coordinates=None):
        """
        Deletes an agent on a given x,y coordinates

        :param coordinates
        :return: True: Deleting successful; False: Deleting unsuccessful
        """
        if coordinates is None:
            logging.info("coordinates are 'None'...")
            return False

        if not self.world.grid.are_valid_coordinates(coordinates):
            logging.info("invalid coordinates")
            return False

        if self.world.remove_agent_on(coordinates):
            logging.info("Deleted Agent on coordinates %s" % str(coordinates))
            self.csv_agent_writer.write_agent(agents_deleted=1)
            return True
        else:
            logging.info("Could not delete agent on coordinates %s" % str(coordinates))
            return False

    def take_agent_with_id(self, agent_id):
        """
        Takes an agent with a given item id

        :param agent_id:  The id of the agent that should be taken
        :return: True: successful taken; False: unsuccessful taken
        """
        if self.carried_item is not None or self.carried_agent is not None:
            logging.info("agent %s is already carrying an agent or an item" % str(self.get_id()))
            return False

        if agent_id not in self.world.get_agent_map_id():
            logging.info("Agent with id %s is not in the world" % str(agent_id))
            return False

        self.carried_agent = self.world.agent_map_id[agent_id]
        if self.carried_agent.take_me(self.coordinates):
            logging.info("Agent with id %s  has been taken" % str(agent_id))
            self.carried_agent.coordinates = self.coordinates
            if self.world.vis is not None:
                self.world.vis.agent_changed(self.carried_agent)
            self.world.csv_round.update_metrics(agents_taken=1)
            self.csv_agent_writer.write_agent(agents_taken=1)
            return True
        else:
            self.carried_agent = None
            logging.info("Agent with id %s could not be taken" % str(agent_id))
            return False

    def take_agent_on(self, coordinates):
        """
        Takes the agent on the given coordinates if it is not taken

        :param coordinates: the agent coordinates
        :return: True: Successful taken; False: Cannot be taken or wrong Coordinates
        """

        if not self.world.grid.are_valid_coordinates(coordinates):
            logging.info("Coordinates are invalid")
            return False

        if coordinates in self.world.agent_map_coordinates:
            return self.take_agent_with_id(self.world.agent_map_coordinates[coordinates].get_id())
        else:
            logging.info("There is no agent on %s" % str(coordinates))
            return False

    def take_agent_in(self, direction):
        """
        Takes an agent that is in a given direction

        :param direction: The direction on which the agent should be taken. Options: E, SE, SW, W, NW, NE,
        :return: True: successful taken; False: unsuccessful taken
        """
        return self.take_agent_on(get_coordinates_in_direction(self.coordinates, direction))

    def take_agent(self):
        """
        Takes an agent on the actual position

        :return: True: successful taken; False: unsuccessful taken
        """
        return self.take_agent_on(self.coordinates)

    def drop_agent(self):
        """
        Drops the taken agent on the agents actual position

        :return: None
        """
        return self.drop_agent_on(self.coordinates)

    def drop_agent_in(self, direction):
        """
        Drops the agent in a given direction

         :param direction: The direction on which the agent should be dropped.
        """
        return self.drop_agent_on(get_coordinates_in_direction(self.coordinates, direction))

    def drop_agent_on(self, coordinates=None):
        """
        Drops the agent on the given coordinates

        :param coordinates:
        """
        if self.carried_agent is not None and coordinates is not None:
            if self.world.grid.are_valid_coordinates(coordinates):
                if coordinates not in self.world.agent_map_coordinates:
                    try:  # cher: insert so to overcome the AttributeError
                        self.carried_agent.drop_me(coordinates)
                    except AttributeError:
                        logging.info("Dropped agent on: Error while dropping")
                        return False
                    self.carried_agent = None
                    logging.info("Dropped agnet on %s coordinate", str(coordinates))
                    self.world.csv_round.update_metrics(agents_dropped=1)
                    self.csv_agent_writer.write_agent(agents_dropped=1)
                    return True
                else:
                    logging.info("Is not possible to drop the agent on that position because it is occupied")
                    return False
            else:
                logging.info("invalid coordinates")
        else:
            logging.info("drop_agent_on: coordinates are 'None' or not carrying an agent")
            return False

    def update_agent_coordinates(self, agent, new_coordinates):
        """
        Upadting the agent with new coordinates
        Only necessary for taking and moving agents

        :param agent: The agent item
        :param new_coordinates: new coorindates
        :return: None
        """
        if self.world.grid.are_valid_coordinates(new_coordinates):
            agent.coordinates = new_coordinates
            self.world.agent_map_coordinates[new_coordinates] = agent
            if self.world.vis is not None:
                self.world.vis.agent_changed(agent)
            return True
        else:
            return False

    def create_location(self):
        """
         Creates a location on the agents actual position

        :return: New location or False
        """

        logging.info("Going to create on position %s" % str(self.coordinates))
        new_location = self.world.add_location(self.coordinates)
        if new_location:
            self.csv_agent_writer.write_agent(location_created=1)
            self.world.csv_round.update_locations_num(len(self.world.get_location_list()))
            self.world.csv_round.update_metrics(location_created=1)
            return new_location
        else:
            return False

    def create_location_in(self, direction=None):
        """
        Creates a location either in a given direction
        :param direction: The direction on which the location should be created.
        :return: New location or False

        """
        if direction is not None:
            coordinates = get_coordinates_in_direction(self.coordinates, direction)
            logging.info("Going to create a location in %s on position %s" % (str(direction), str(coordinates)))
            new_location = self.world.add_location(coordinates)
            if new_location:
                logging.info("Created location on coordinates %s" % str(coordinates))
                self.world.csv_round.update_locations_num(len(self.world.get_location_list()))
                self.world.csv_round.update_metrics(location_created=1)
                return new_location
            else:
                return False
        else:
            logging.info("Location not created. Invalid direction (None)")
            return False

    def create_location_on(self, coordinates=None):
        """
        Creates a location either on a given x,y coordinates

        :return: New location or False

        """
        if coordinates is not None:
            if self.world.grid.are_valid_coordinates(coordinates):
                logging.info("Going to create a location on position %s", str(coordinates))
                new_location = self.world.add_location(coordinates)
                if new_location:
                    logging.info("Created location on coordinates %s", str(coordinates))
                    self.world.csv_round.update_locations_num(len(self.world.get_location_list()))
                    self.world.csv_round.update_metrics(location_created=1)
                    return new_location
            else:
                return False
        else:
            logging.info("Location not created. invalid coordinates (None)")
            return False

    def delete_location_with(self, location_id):
        """
        Deletes a location with a given location-id
        :param location_id: The id of the location that should be deleted
        :return: True: Deleting successful; False: Deleting unsuccessful
        """
        logging.info("Agent %s is going to delete location with location id %s" % (self.get_id(), location_id))
        if self.world.remove_location(location_id):
            self.csv_agent_writer.write_agent(locations_deleted=1)
            return True
        else:
            logging.info("Could not delete location with location id %s", str(location_id))
            return False

    def delete_location(self):
        """
        Deletes a location on current position

        :return: True: Deleting successful; False: Deleting unsuccessful
        """
        logging.info("Agent %s is going to delete a location on current position" % self.get_id())
        if self.coordinates in self.world.get_location_map_coordinates():
            if self.world.remove_location_on(self.coordinates):
                self.csv_agent_writer.write_agent(location_deleted=1)
                return True
        else:
            logging.info("Could not delete location")
            return False

    def delete_location_in(self, direction=None):
        """
        Deletes a location in a given direction

        :param direction: The direction on which the location should be deleted.
        :return: True: Deleting successful; False: Deleting unsuccessful
        """
        if direction is not None:
            coordinates = get_coordinates_in_direction(self.coordinates, direction)
            logging.info("Deleting Location in %s direction", str(direction))
            if self.world.remove_location_on(coordinates):
                logging.info("Deleted location with location on coordinates %s", str(coordinates))
                self.csv_agent_writer.write_agent(locations_deleted=1)
                return True
            else:
                logging.info("Could not delete location on coordinates %s", str(coordinates))
                return False
        else:
            logging.info("invalid direction %d", str(direction))

    def delete_location_on(self, coordinates=None):
        """
        Deletes a location on given coordinates

        :param coordinates: the coordinates
        :return: True: Deleting successful; False: Deleting unsuccessful
        """
        if coordinates is not None:
            if self.world.grid.are_valid_coordinates(coordinates):
                if self.world.remove_location_on(coordinates):
                    logging.info("Deleted location on coordinates %s", str(coordinates))
                    self.csv_agent_writer.write_agent(locations_deleted=1)
                    return True
                else:
                    logging.info("Could not delete location on coordinates %s", str(coordinates))
                    return False
            else:
                return False
        else:
            return False

    def set_color(self, color):

        super().set_color(color)
        if self.world.vis is not None:
            self.world.vis.agent_changed(self)



