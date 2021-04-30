import numpy as np
import random
defense_clr = [0, 0, 255, 1]
offense_clr = [255, 0, 0, 1]
defense_center = [-10, 0, 0]
offense_center = [10, 0, 0]

def scenario(world):
    defense_size = 30
    offense_size = 90

    world.add_location(tuple(defense_center), [0, 0, 255, 1])

    # spawn defense agents
    for _ in range(defense_size):
        spawn = list(circle_spawn(defense_size)) + [0]
        spawn = np.array(spawn) + np.array(defense_center)
        world.add_agent(tuple(spawn), color= defense_clr)

    # spawn offense agents
    for _ in range(offense_size):
        spawn = list(circle_spawn(offense_size)) + [0]
        spawn = np.array(spawn) + np.array(offense_center)
        world.add_agent(tuple(spawn), color= offense_clr)

def circle_spawn(swarm_size):
    density = 0.22
    t = 2 * np.pi * np.random.random()
    u = np.random.random() + np.random.random()
    r = 2 - u if u > 1 else u
    radius =  pow(swarm_size / (density * np.pi), 0.5)
    return np.array([r * np.cos(t) * radius, r * np.sin(t) * radius])