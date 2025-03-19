# Name: ScienceWorld API Example
# Description: This is an example of how to use the ScienceWorld API.  ScienceWorld is an interactive text-based game that tests a player's knowledge of elementary science. This example includes only a very simple random agent (that randomly selects actions to take).
# inclusion_criteria: You would normally use this codeblock if you'd like an agent (or human) to play/interact with one or more ScienceWorld games/scenarios/tasks, and would like to see an example of how to do so.
# exclusion_criteria: If you're not specifically using ScienceWorld, this codeblock will likely not be useful (except perhaps as a broad example of how to interface with a text-based game).
# python_version: 3.8
# pip_requirement: scienceworld


from scienceworld import ScienceWorldEnv        # Main import for ScienceWorld
import random                                   # For the random agent

# Example function that runs a random agent baseline on the ScienceWorld environment.
# Expected 'args' dictionary keys:
# Task Setup:
#   'task_num': The task number to run (0-29)
#   'simplification_str': CSV string. Possible allowed simplifications: 'easy' (all simplifications applied -- a common setting), or (piecewise) 'teleportAction,selfWateringFlowerPots,openContainers,openDoors,noElectricalAction'. An empty list means no simplifications.
#   'num_episodes': Number of episodes to run.
#   'env_step_limit': Maximum number of steps to run per episode in the environment.  This is typically a number like 100.
# Logging:
#   'output_path_prefix': Path to save the output files for later analysis.  This should be a prefix (e.g. "mylogprefix-"), as the function will append the task number to the end of the file name.
#   'max_episode_per_file': Maximum number of episodes to save per file.  This is typically a number like 100 (larger numbers will mean larger files).
# Rarely used:
#   'jar_path': Path to the ScienceWorld jar file.  Leave blank for the default (this is the normal case)
#   'env_seed': Seed for the environment.  Leave blank for a random seed.

def randomModel(args):
    """ Example random agent -- randomly picks an action at each step. """
    exitCommands = ["quit", "exit"]

    taskIdx = args['task_num']
    simplificationStr = args['simplification_str']
    numEpisodes = args['num_episodes']

    # Keep track of the agent's final scores
    finalScores = []

    # Initialize environment
    env = ScienceWorldEnv("", args['jar_path'], envStepLimit=args['env_step_limit'])

    # This returns a list of all the task names.
    taskNames = env.get_task_names()
    print("Task Names: " + str(taskNames))  # Task Names: ['boil', 'change-the-state-of-matter-of', 'chemistry-mix', 'chemistry-mix-paint-secondary-color', 'chemistry-mix-paint-tertiary-color', 'find-animal', 'find-living-thing', 'find-non-living-thing', 'find-plant', 'freeze', 'grow-fruit', 'grow-plant', 'identify-life-stages-1', 'identify-life-stages-2', 'inclined-plane-determine-angle', 'inclined-plane-friction-named-surfaces', 'inclined-plane-friction-unnamed-surfaces', 'lifespan-longest-lived', 'lifespan-longest-lived-then-shortest-lived', 'lifespan-shortest-lived', 'measure-melting-point-known-substance', 'measure-melting-point-unknown-substance', 'melt', 'mendelian-genetics-known-plant', 'mendelian-genetics-unknown-plant', 'power-component', 'power-component-renewable-vs-nonrenewable-energy', 'test-conductivity', 'test-conductivity-of-unknown-substances', 'use-thermometer']

    # Choose task
    taskName = taskNames[taskIdx]  # Load the task by name (i.e. conver the taskIdx to a name)
    # Load the task, we we have access to some extra accessors e.g. get_random_variation_train()
    env.load(taskName, 0, "")
    maxVariations = env.get_max_variations(taskName)
    print("Starting Task " + str(taskIdx) + ": " + taskName)

    # Choose parametric variation of the task to run.  This is different from the task number, as each task has many parametric variations.  Typically we run a different variation per episode.  Different parametric variation indices are assigned to train/dev/test sets for each task.
    # IMPORTANT: You MUST initialize and `load` a specific task (as above) before you can access the variations for that task.  Otherwise you'll crash with an error (`java.lang.IllegalArgumentException: requirement failed: size=0 and step=0, but both must be positive`).
    availableVariations = []
    variationSet = args.get('variation_set', None)
    if (variationSet is None) or (variationSet == "train"):
        availableVariations = env.get_variations_train()    # Train
    elif (variationSet == "dev"):
        availableVariations = env.get_variations_dev()
    elif (variationSet == "test"):
        availableVariations = env.get_variations_test()
    else:
        print("ERROR: Unknown variation set: " + str(variationSet))
        exit(1)

    # Start running episodes
    for episodeIdx in range(0, numEpisodes):
        # Pick a random parametric variation of this task
        randVariationIdx = random.choice(availableVariations)   # Randomly pick one variation
        # Load the environment
        env.load(taskName, randVariationIdx, simplificationStr)
        # Reset the environment.  This MUST be called before starting a new episode, or errors will occur.  It must also be called before any of the information below (actions, objects, task description, etc.) is valid -- otherwise it will be (possibly silently) errorful.
        initialObs, initialDict = env.reset()

        # Example accessors for different kinds of information available from ScienceWorld.
        print("Possible actions: " + str(env.get_possible_actions()))   # (list) of strings, of the form "activate OBJ", "close OBJ", "use OBJ on OBJ", etc. (with "OBJ" being a placeholder for an object)
        print("Possible objects: " + str(env.get_possible_objects()))   # (list) of strings, of the form "apple", "door", "key", etc.
        templates, lut = env.get_possible_action_object_combinations()
        print("Possible action/object combinations: " + str(templates)) # (list) of dictionaries, with keys: 'action', 'template_id', 'obj_ids', and 'type_ids'.  Generated automatically through cross-product of all action templates * all objects -- many (most?) will not be valid actions. Examples: `[{'action': 'pour axe in wood', 'template_id': 10, 'obj_ids': [17538, 17535], 'type_ids': [32, 168]}, {'action': 'move fountain to wood', 'template_id': 9, 'obj_ids': [17541, 17535], 'type_ids': [80, 168]}, ...]`
        print("Object IDX to Object Referent LUT: " + str(lut)) # (dictionary) of object IDX to object referent.  Examples: `{'17205': 'kitchen', '17421': 'greenhouse', '17523': 'outside', '17526': 'air', '17529': 'ground', '17532': 'fire pit', '17535': 'wood', '17538': 'axe', '17541': 'fountain', ...}
        print("Task Name: " + taskName)     # Name of the current task.
        print("Task Variation: " + str(randVariationIdx) + " / " + str(maxVariations))
        print("Task Description: " + str(env.get_task_description()))       # Description of the task. This is normally presented to the user/agent at the start of the task, to tell them what to do.
        print("look: " + str(env.look()))   # This provides the "observation" for the user or agent -- what they see in the environment.  This is a string.
        print("inventory: " + str(env.inventory()))  # This provides the "inventory" for the user or agent -- what they are carrying.  This is a string.

        # Score for this episode
        score = 0.0
        isCompleted = False
        curIter = 0

        # Run one episode until we reach a stopping condition (including exceeding the maximum steps)
        userInputStr = "look around"        # First action
        while (userInputStr not in exitCommands) and (isCompleted is False):
            print("----------------------------------------------------------------")
            print("Step: " + str(curIter))

            # Send the requested action to the environment (userInputStr), and get the response.
            # Response is a tuple: observation (what the agent/user now sees), reward (the reward for the action), isCompleted (True if the episode is over), info (a dictionary of extra information).
            observation, reward, isCompleted, info = env.step(userInputStr)
            # SCORING: IMPORTANT (!)
            next_score = info['score']   # The ScienceWorld normalized score (0-1, with 1 signifying complete) is part of the 'info' dictionary.
            if (next_score < 0):
                # IMPORTANT: Taking a failng action turns the score negative (usually to -100).  This is a signal that the agent has taken an action that fails the task. The task should end after this.
                print("The agent has taken an action that fails the task.")
                isCompleted = True
                break
            else:
                score = next_score  # IMPORTANT: If the score is not negative, then the score is valid -- update the score.

            print("\n>>> " + observation)               #
            print("Reward: " + str(reward))
            print("Score: " + str(score))
            print("isCompleted: " + str(isCompleted))

            # The environment will make isCompleted `True` when a stop condition
            # has happened, or the maximum number of steps is reached.
            if (isCompleted):
                break

            # Randomly select the next action

            # Any action (valid or not).  Random baselines usually restrict to using only valid actions.
            # templates, lut = env.get_possible_action_object_combinations()
            # print("Possible action/object combinations: " + str(templates))
            # print("Object IDX to Object Referent LUT: " + str(lut))
            # randomTemplate = random.choice( templates )
            # print("Next random action: " + str(randomTemplate))
            # userInputStr = randomTemplate["action"]

            # Only valid actions
            validActions = env.get_valid_action_object_combinations_with_templates()
            randomAction = random.choice(validActions)
            print("Next random action: " + str(randomAction))
            userInputStr = randomAction["action"]

            print(list(lut.keys())[-1])

            # Sanitize input
            userInputStr = userInputStr.lower().strip()
            print("Choosing random action: " + str(userInputStr))

            # Keep track of the number of commands sent to the environment in this episode
            curIter += 1

        # Show the goal progress string.  (NOTE, this is oracle knowledge and this information should never be available to the agent -- only to the experimenter, to evaluate progress.)
        # This string is a table, that shows a list of subgoals, and whether or not each one has been completed.
        print("Goal Progress:")
        print(env.get_goal_progress())

        # Episode finished -- Record the final score
        finalScores.append(score)   # Record the final score. IMPORTANT: Should not record the negative scores (which are a signal of task failure), but rather the last score before a negative score.

        # Report progress of model
        print("Final score: " + str(score))
        print("isCompleted: " + str(isCompleted))

        # Save history -- and when we reach maxPerFile, export them to file
        filenameOutPrefix = args['output_path_prefix'] + str(taskIdx)
        env.store_run_history(episodeIdx, notes={'text': 'my notes here'})
        env.save_run_histories_buffer_if_full(filenameOutPrefix, max_per_file=args['max_episode_per_file'])

    # Episodes are finished -- manually save any last histories still in the buffer
    env.save_run_histories_buffer_if_full(filenameOutPrefix, max_per_file=args['max_episode_per_file'], force_save=True)

    # Show final episode scores to user
    # Clip negative scores to 0 for average calculation
    avg = sum([x for x in finalScores if x >= 0]) / len(finalScores)
    print("")
    print("---------------------------------------------------------------------")
    print(" Summary (Random Agent)")
    print(" Task " + str(taskIdx) + ": " + taskName)
    print(" Simplifications: " + str(simplificationStr))
    print("---------------------------------------------------------------------")
    print(" Episode scores: " + str(finalScores))
    print(" Average episode score: " + str(avg))
    print("---------------------------------------------------------------------")
    print("")

    print("Completed.")

    # Return the final scoring information
    packedResults = {}
    packedResults['task_name'] = taskName
    packedResults['task_idx'] = taskIdx
    packedResults['simplification_str'] = simplificationStr
    packedResults['num_episodes'] = numEpisodes
    packedResults['max_steps'] = args['env_step_limit']
    packedResults['final_scores'] = finalScores
    packedResults['average_score'] = avg
    return packedResults



# Example of a call to a main function
if __name__ == '__main__':
    # Populate example arguments
    args = {}
    args['task_num'] = 0
    args['simplification_str'] = "easy"
    args['num_episodes'] = 10
    args['env_step_limit'] = 100
    args['output_path_prefix'] = "mylogprefix-"
    args['max_episode_per_file'] = 100
    args['jar_path'] = ""
    args['env_seed'] = 0
    args['variation_set'] = "train"

    # Call the random model
    results = randomModel(args)

    # Do something with the results
    print("Results: ")
    print(results)
