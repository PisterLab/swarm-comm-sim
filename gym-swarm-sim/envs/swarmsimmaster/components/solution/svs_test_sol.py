import numpy as np
from communication import communication_model

eps = 10e-8
defense_max_speed = 0.1
offense_max_speed = 0.1
# offense_max_speed = 0.09
comms_model = "disk"
DISK_RANGE = 3

terminated = False

defense_clr = [0, 0, 255, 1]
offense_clr = [255, 0, 0, 1]
defense_center = [-10, 0, 0]
offense_center = [10, 0, 0]

k_max_concurrent_targets = 1
k_target_rad = 0.25
k_max_defender_kills = 3

def solution(world, stats=None):
    global terminated

    if not terminated:

        agents = world.get_agent_list()

        # add alive and kills markers
        if timestep(world) == 1:
            for a in agents:
                a.alive = True
                a.kills = 0

        # get alive attackers and defenders
        offense_drones = get_drones(world, clr=offense_clr)
        defense_drones = get_drones(world, clr=defense_clr)

        # check if defenders win
        if not offense_drones:
            terminated = True
            if (stats):
                stats.increment_wins()
        # check if attackers win
        elif not defense_drones:
            terminated = True
            if (stats):
                stats.increment_losses()
        else:
            # defense policy applied
            def_p4_intercept(world, defense_drones, offense_drones)

            # check deaths in offense after defense moves
            proximity_death_check(world, defense_drones, offense_drones, lambda d : 1 - 3*d)

            # refresh offense_drones
            offense_drones = get_drones(world, clr=offense_clr)

            # offense policy applied
            off_p3(world, defense_drones, offense_drones)

            # defender death check
            def_death_check1(world, defense_drones, offense_drones)

            oob_check(world, defense_drones, offense_drones)
    else:
        world.set_successful_end()

# kills agents that move too far away
def oob_check(world, defense_drones, offense_drones):
    sorted_offense = sorted(offense_drones,
                                key=lambda x: np.linalg.norm(np.array(x.coordinates) - np.array(defense_center)), reverse=True)
    sorted_defense = sorted(defense_drones,
                                key=lambda x: np.linalg.norm(np.array(x.coordinates) - np.array(defense_center)), reverse=True)
    for o in sorted_offense:
        dist = np.linalg.norm(np.array(o.coordinates) - np.array(defense_center))
        if (dist > 40):
            death_routine(o)
        else:
            break
    
    for d in sorted_defense:
        dist = np.linalg.norm(np.array(d.coordinates) - np.array(defense_center))
        if (dist > 40):
            death_routine(d)
        else:
            break

# offense death check
def off_death_check1(world, defense_drones, offense_drones, stats=None):
    global terminated

    # death check for offense
    for a in offense_drones:
        sorted_defense = sorted(defense_drones,
                                key=lambda x: np.linalg.norm(np.array(x.coordinates) - np.array(a.coordinates)))
        closest_defense = sorted_defense[0]
        # check if dead
        if np.linalg.norm(np.array(closest_defense.coordinates) - np.array(a.coordinates)) < 0.1:
            death_routine(a)

            ### hopefully temporary?
            closest_defense.kills += 1
            ###

        # check if attackers win:
        if np.linalg.norm(np.array(a.coordinates) - np.array(defense_center)) < 0.1:
            terminated = True

# offense death check with % chance of death
def off_death_check2(world, defense_drones, offense_drones):
    global terminated

    # death check for offense
    for a in offense_drones:
        sorted_defense = sorted(defense_drones,
                                key=lambda x: np.linalg.norm(np.array(x.coordinates) - np.array(a.coordinates)))
        closest_defense = sorted_defense[0]
        # check if dead
        if np.linalg.norm(np.array(closest_defense.coordinates) - np.array(a.coordinates)) < 0.1 and np.random.rand() > 0.8:
            death_routine(a)

            ### hopefully temporary?
            closest_defense.kills += 1
            ###

        # check if attackers win:
        if np.linalg.norm(np.array(a.coordinates) - np.array(defense_center)) < 0.1:
            terminated = True

def proximity_death_check(world, defense_drones, offense_drones, chance_func):
    global terminated

    # death check for offense
    for a in offense_drones:
        _, near_defense = get_local_agents(world, a, offense_drones, defense_drones)
        
        # check if dead
        for d in near_defense:
            distance = np.linalg.norm(np.array(d.coordinates) - np.array(a.coordinates))
            if np.random.rand() < chance_func(distance):
                death_routine(a)
                ### hopefully temporary?
                d.kills += 1
                ###
                break

    # check if attackers win:
        if np.linalg.norm(np.array(a.coordinates) - np.array(defense_center)) < 0.1:
            terminated = True
    return

# defense death check 1: defenders die after eliminating `n` attackers
def def_death_check1(world, defense_drones, offense_drones):
    for a in defense_drones:
        if (a.kills) >= k_max_defender_kills:
            death_routine(a)

def off_p0(world, defense_drones, offense_drones):
    for a in offense_drones:
        move_toward(a, (0, 10, 0))

# off policy 1: go to center directly
def off_p1(world, defense_drones, offense_drones):
    for a in offense_drones:
        move_toward(a, defense_center)

# off policy 2: hand craft
def off_p2(world, defense_drones, offense_drones):
    leaders = []
    total_leaders = min(len(offense_drones), 20)

    for a in offense_drones:
        if hasattr(a, "leader"):
            leaders.append(a)

    for i in range(total_leaders - len(leaders)):
        for a in offense_drones:
            if not hasattr(a, "leader") and not hasattr(a, "sneaker"):
                leaders.append(a)
                a.leader = True
                break

    for leader in leaders:
        move_toward(leader, (0, -100, 0))

    for i, a in enumerate(offense_drones):
        if not hasattr(a, "leader"):
            move_toward(a, defense_center)

def off_p3(world, defense_drones, offense_drones):
    """Offense Policy 3: Dodges defense drones by moving orthongonally when within a certain range of said drone type."""
    # Tunable Parameters
    dodge_dist = 4
    dive_dist = 4
    crit_dist = 1
    crit_locked_on = 1
    dodge_angle = lambda x: min(90, max(80, 3 * 90 / x))
    # dodge_angle = lambda x: 90

    # Other variables
    obj_vec = np.array(defense_center)

    for a in offense_drones:
        a_vec = np.array(a.coordinates)
        obj_dist = np.linalg.norm(obj_vec - a_vec)
        sorted_defense = sorted(defense_drones, key=lambda a: np.linalg.norm(np.array(a.coordinates) - a_vec))
        closest_def_vec = np.array(sorted_defense[0].coordinates)

        # if close enough to objective or at least closer to objective than closest defense drone, move toward objective
        if obj_dist < dive_dist or obj_dist < np.linalg.norm(obj_vec - closest_def_vec):
            move_toward(a, defense_center)
        # if there are more than CRIT_LOCKED_ON defense drones within a CRIT_DIST distance, start moving away
        elif num_in_range(a, sorted_defense, crit_dist) >= crit_locked_on:
            move_toward(a, 2 * a_vec - closest_def_vec)
        # if the closest defending drone is within the DODGE_DIST distance, move orthogonally
        elif np.linalg.norm(closest_def_vec - a_vec) <= dodge_dist:
            move_toward(a, a_vec + dodge_vec(a, sorted_defense, dodge_angle(obj_dist)))
        # by default, move towards objective
        else:
            move_toward(a, defense_center)

#######
def dodge_vec(agent, sorted_agents, angle=90):
        """Returns a vector to dodge towards.

        :param agent: the agent to move
        :param sorted_agents: the sorted list of agents to dodge
        :param angle: the angle at which to dodge
        :return: a numpy vector in 3D
        """
        u = np.array(sorted_agents[0].coordinates) - np.array(agent.coordinates)
        u = u / np.linalg.norm(u)
        v = np.array(defense_center)
        w = v - (v @ u) * u
        w = w / np.linalg.norm(w)
        return 10 * (np.sin(angle*np.pi/180) * w + np.cos(angle*np.pi/180) * u)


def num_in_range(agent, agent_list, range):
        """Returns the number of agents within a range (inclusive) of a given agent.

        :param agent: the agent to check around
        :param agent_list: the agents to check for
        :return: (int)
        """
        num = 0
        for a in agent_list:
            if np.linalg.norm(np.array(agent.coordinates) - np.array(a.coordinates)) <= range:
                num += 1
        return num
#######

# def policy 1: go to closest attacker to center
def def_p1(world, defense_drones, offense_drones):
    sorted_offense = sorted(offense_drones,
                            key=lambda x: np.linalg.norm(np.array(x.coordinates) - np.array(defense_center)))
    for a in defense_drones:
        closest_offense = sorted_offense[0]
        move_toward(a, closest_offense.coordinates)

# def policy 2: go to the closest non-targeted attacker from center
# if all targeted, go to the closest attacker from center
def def_p2(world, defense_drones, offense_drones):
    sorted_offense = sorted(offense_drones,
                            key=lambda x: np.linalg.norm(np.array(x.coordinates) - np.array(defense_center)))
    sorted_offense_cpy = sorted_offense.copy()

    for a in defense_drones:
        if sorted_offense_cpy:
            closest_offense = sorted_offense_cpy.pop(0)
        else:
            closest_offense = sorted_offense[0]
        move_toward(a, closest_offense.coordinates)

# def policy 3: go to the closest guy from YOU that is non-targeted
# if all targeted, go to the closest attacker from center
def def_p3(world, defense_drones, offense_drones):
    targetted = []

    for a in defense_drones:
        self_sorted_offense = sorted(offense_drones, key=lambda x: np.linalg.norm(
            np.array(x.coordinates) - np.array(a.coordinates)))

        flag = False
        for x in self_sorted_offense:
            if x.coordinates not in targetted:
                flag = True
                targetted.append(x.coordinates)
                move_toward(a, x.coordinates)
                break
        if not flag:
            sorted_offense = sorted(offense_drones,
                                    key=lambda x: np.linalg.norm(np.array(x.coordinates) - np.array(defense_center)))
            closest_offense = sorted_offense[0]
            move_toward(a, closest_offense.coordinates)

# def policy 3.5: go to the closest guy from YOU that is *reachable*,
# with at most `n` other defenders targeting
# if all targeted, go to the closest attacker from center
def def_p3point5(world, defense_drones, offense_drones):
    targetted = {}

    for a in defense_drones:
        self_dist = np.linalg.norm(np.array(a.coordinates) - np.array(defense_center))
        self_sorted_offense = sorted(offense_drones, key=lambda x: np.linalg.norm(
            np.array(x.coordinates) - np.array(a.coordinates)))

        flag = False
        for x in self_sorted_offense:
            off_dist = np.linalg.norm(np.array(x.coordinates) - np.array(defense_center))
            if (targetted.setdefault(x.coordinates, 0) <= k_max_concurrent_targets-1) and off_dist >= self_dist - k_target_rad:
                flag = True
                targetted[x.coordinates] += 1
                move_toward(a, x.coordinates)
                break
        if not flag:
            sorted_offense = sorted(offense_drones,
                                    key=lambda x: np.linalg.norm(np.array(x.coordinates) - np.array(defense_center)))
            closest_offense = sorted_offense[0]
            move_toward(a, closest_offense.coordinates)


def def_p3point5_intercept(world, defense_drones, offense_drones):
    targetted = {}

    for defense in defense_drones:
        self_sorted_offense = sorted(offense_drones, key=lambda x: np.linalg.norm(
            np.array(x.coordinates) - np.array(defense.coordinates)))

        flag = False
        for offense in self_sorted_offense:
            lookahead = get_intercept(offense, defense)
            if (targetted.setdefault(offense.coordinates, 0) <= k_max_concurrent_targets-1) and lookahead is not None \
                    and np.linalg.norm(np.array(lookahead) - np.array(defense_center)) > k_target_rad:
                flag = True
                targetted[offense.coordinates] += 1
                move_toward(defense, lookahead)
                break
        if not flag:
            sorted_offense = sorted(offense_drones,
                                    key=lambda x: np.linalg.norm(np.array(x.coordinates) - np.array(defense_center)))
            closest_offense = sorted_offense[0]
            move_toward(defense, closest_offense.coordinates)

# def policy 4: half the drones follow def policy 3.5 as usual
# other half only attack drones within `radius` of the center (following def policy 3.5)
def def_p4(world, defense_drones, offense_drones):
    # Tweakable parameters
    def_radius = 3
    ###

    patrollers = []
    targetted = {}

    for i in range(len(defense_drones)//2):
        patrollers.append(defense_drones[i])
    
    near_offense = list(filter(lambda x: (np.linalg.norm(np.array(x.coordinates) - np.array(defense_center))) < def_radius, offense_drones))
    far_offense = list(filter(lambda x: (np.linalg.norm(np.array(x.coordinates) - np.array(defense_center))) >= def_radius, offense_drones))
    
    for a in patrollers:
        sorted_near_offense = sorted(near_offense, key=lambda x: np.linalg.norm(
            np.array(x.coordinates) - np.array(a.coordinates)))

        flag = False
        for x in sorted_near_offense:
            if (targetted.setdefault(x.coordinates, 0) <= k_max_concurrent_targets-1) and np.linalg.norm(np.array(x.coordinates) - np.array(defense_center)) >= np.linalg.norm(np.array(a.coordinates) - np.array(defense_center)) - k_target_rad:
                flag = True
                targetted[x.coordinates] += 1
                move_toward(a, x.coordinates)
                break
        if not flag:
            if (a.coordinates[0] <= defense_center[0]):
                move_toward(a, [defense_center[0] + 1, a.coordinates[1], a.coordinates[2]])
            else:
                move_threshold(a, defense_center, 0, 1)

    if (far_offense):
        def_p3point5(world, defense_drones[len(patrollers):], far_offense)
    else:
        def_p3point5(world, defense_drones[len(patrollers):], near_offense)

# def policy 4: half the drones follow def policy 3.5 as usual
# other half only attack drones within `radius` of the center (following def policy 3.5)
def def_p4_intercept(world, defense_drones, offense_drones):
    # Tweakable parameters
    def_radius = 3
    ###

    patrollers = []
    targetted = {}

    for i in range(len(defense_drones)//2):
        patrollers.append(defense_drones[i])

    near_offense = list(filter(lambda x: (np.linalg.norm(np.array(x.coordinates) - np.array(defense_center))) < def_radius, offense_drones))
    far_offense = list(filter(lambda x: (np.linalg.norm(np.array(x.coordinates) - np.array(defense_center))) >= def_radius, offense_drones))

    for patroller in patrollers:
        sorted_near_offense = sorted(near_offense, key=lambda x: np.linalg.norm(
            np.array(x.coordinates) - np.array(patroller.coordinates)))

        flag = False
        for offense in sorted_near_offense:
            lookahead = get_intercept(offense, patroller)
            if (targetted.setdefault(offense.coordinates, 0) <= k_max_concurrent_targets-1) and lookahead is not None \
                    and np.linalg.norm(np.array(lookahead) - np.array(defense_center)) > k_target_rad:
                flag = True
                targetted[offense.coordinates] += 1
                move_toward(patroller, lookahead)
                break
        if not flag:
            if patroller.coordinates[0] <= defense_center[0]:
                move_toward(patroller, [defense_center[0] + 1, patroller.coordinates[1], patroller.coordinates[2]])
            else:
                move_threshold(patroller, defense_center, 0, 1)

    if far_offense:
        def_p3point5_intercept(world, defense_drones[len(patrollers):], far_offense)
    else:
        def_p3point5_intercept(world, defense_drones[len(patrollers):], near_offense)

def get_drones(world, clr):
    lst = []
    for a in world.get_agent_list():
        if a.color == clr and a.alive:
            lst.append(a)
    return lst

def death_routine(a):
    a.alive = False
    a.update_agent_coordinates(a, (100, 100, 0))

####################################################
# move agent toward target
def move_toward(agent, target, thres=0.001):
    vec = np.array(target) - np.array(agent.coordinates)
    if np.linalg.norm(vec) > thres:
        agent.move_to(speed_limit(vec, agent))
        return True
    return False

def in_range(actual, target, threshold):
    return abs(actual - target) <= threshold


# anticipate moving drone's location and calculate intercept loc TODO scale by speed
# NOTE: current implementation only works if same speed
def get_intercept(offense, defense, deadband=0.0001):
    """
    :param offense: offense drone to target
    :param defense: defense drone targeting offense
    :param deadband: threshold for ignoring value
    :return: intercept location
    """
    if in_range(offense.get_velocities()[0], 0, deadband) and in_range(offense.get_velocities()[1], 0, deadband):
        return offense.coordinates

    # m2(y - b) = m1(x - a)
    x_coeff_offense = offense.get_velocities()[1]
    y_coeff_offense = offense.get_velocities()[0]

    x_coeff_intersect = offense.coordinates[0] - defense.coordinates[0]
    y_coeff_intersect = - (offense.coordinates[1] - defense.coordinates[1])

    if in_range(y_coeff_intersect/x_coeff_intersect, y_coeff_offense/x_coeff_offense, deadband):
        return None

    c_intersect = np.array([[(offense.coordinates[0] + defense.coordinates[0]) / 2],
                            [(offense.coordinates[1] + defense.coordinates[1]) / 2]], dtype="float")

    dep1 = y_coeff_offense * offense.coordinates[1] - x_coeff_offense * offense.coordinates[0]
    dep2 = y_coeff_intersect * c_intersect[1][0] - x_coeff_intersect * c_intersect[0][0]

    mat_coeff = np.array([[-x_coeff_offense, y_coeff_offense], [-x_coeff_intersect, y_coeff_intersect]], dtype="float")
    mat_dep = np.array([[dep1], [dep2]], dtype="float")

    # calculate intercept between equidistant line and offense vel vector
    ret = np.linalg.solve(mat_coeff, mat_dep)

    # check if solution lies in +dt
    if (np.sign(offense.get_velocities()[0]) == np.sign(ret[0] - offense.coordinates[0])
            and np.sign(offense.get_velocities()[1]) == np.sign(ret[1] - offense.coordinates[1])):
        return tuple([ret[0][0], ret[1][0], 0])
    return None

# enforce speed limit
def speed_limit(speed_vec, agent):
    speed = np.linalg.norm(speed_vec)

    if agent.color == defense_clr:
        max_speed = defense_max_speed
    else:
        max_speed = offense_max_speed

    if speed > max_speed:
        return speed_vec / (speed + eps) * max_speed
    return speed_vec


# helper for timestep
def timestep(world):
    return world.get_actual_round()

##############################################
# random jittering
def jitter(agent):
    target = (np.random.random(size=3) - 0.5) * 10
    target[2] = 0
    target += agent.coordinates
    move_toward(agent, target)


# move agent within [min_dist, max_dist] from target, where target = [x, y, z]
def move_threshold(agent, target, min_dist, max_dist):
    n_vec = np.array(agent.coordinates) - target
    n_dist = np.linalg.norm(n_vec)

    if n_dist > max_dist:
        nn_target = n_vec / (n_dist + eps) * max_dist + target
        return move_toward(agent, nn_target)

    if n_dist < min_dist:
        nn_target = n_vec / (n_dist + eps) * min_dist + target
        return move_toward(agent, nn_target)

    return False

# move agent within [min_dist, max_dist] from x, y
def move_threshold_xy(agent, x, y, min_dist, max_dist):
    target = np.array([x, y, 0])
    return move_threshold(agent, target, min_dist, max_dist)

# move agent to within [min_dist, max_dist] from agent2
def move_threshold_agent(agent, agent2, min_dist, max_dist):
    target = agent2.coordinates
    return move_threshold(agent, target, min_dist, max_dist)

# returns lists of offense and defense drones "visible" to the agent
def get_local_agents(world, agent, offense_drones, defense_drones, disk_range=DISK_RANGE):
    local_offense = []
    local_defense = []

    x2, y2 = agent.coordinates[0], agent.coordinates[1]
    for o in offense_drones:
        x1, y1 = o.coordinates[0], o.coordinates[1]
        dist, comm_range = communication_model(x1, y1, x2, y2, comms_model=comms_model, DISK_RANGE_M = disk_range)
        if (comm_range):
            local_offense.append(o)
    for d in defense_drones:
        x1, y1 = d.coordinates[0], d.coordinates[1]
        dist, comm_range = communication_model(x1, y1, x2, y2, comms_model=comms_model, DISK_RANGE_M = disk_range)
        if (comm_range):
            local_defense.append(d)
    
    return local_offense, local_defense