# Name: DiscoveryWorld API Example
# Description: This is an example of how to use the DiscoveryWorld API.  DiscoveryWorld is an interactive text-based (and, optionally, 2D) game that tests a player's ability to perform end-to-end scientific discovery. This example includes only a very simple random agent (that randomly selects actions to take).
# inclusion_criteria: You would normally use this codeblock if you'd like an agent (or human) to play/interact with one or more DiscoveryWorld games/scenarios/tasks, and would like to see an example of how to do so.
# exclusion_criteria: If you're not specifically using DiscoveryWorld, this codeblock will likely not be useful (except perhaps as a broad example of how to interface with a text-based game).
# python_version: 3.8
# pip_requirement: discoveryworld==0.0.2

from discoveryworld.DiscoveryWorldAPI import DiscoveryWorldAPI
from discoveryworld.ScenarioMaker import ScenarioMaker, SCENARIOS, SCENARIO_NAMES, SCENARIO_INFOS, SCENARIO_DIFFICULTY_OPTIONS, getInternalScenarioName

import traceback

import json
import time
import random
import copy

#LIMITED_ACTIONS = True     # Disables a small number of actions (talk, discovery feed)
LIMITED_ACTIONS = False     # Enables all actions

#
#   Helper functions
#

# def getVisibleObjectByUUID(uuid, observation):
#     # First, collect all objects
#     visibleObjectsByUUID = {}
#     for obj in observation["ui"]["inventoryObjects"]:
#         visibleObjectsByUUID[obj["uuid"]] = obj
#     for obj in observation["ui"]["accessibleEnvironmentObjects"]:
#         visibleObjectsByUUID[obj["uuid"]] = obj

#     # # Also include 'nearbyObjects'
#     # for direction in observation["ui"]["nearbyObjects"]["objects"]:
#     #     for obj in direction:
#     #         visibleObjectsByUUID[obj["uuid"]] = obj

#     # Check if the UUID is in the list
#     if uuid in visibleObjectsByUUID:
#         return visibleObjectsByUUID[uuid]
#     else:
#         return None

# # A short, single-line string, of just the immediately interactable objects
# def mkShortInteractableObjectList(observation):
#     objStrs = []
#     for obj in observation["ui"]["inventoryObjects"]:
#         name = obj["name"]
#         uuid = obj["uuid"]
#         strOut = "{\"name\": \"" + name + "\", \"uuid\": " + str(uuid) + "}"
#         objStrs.append(strOut)

#     for obj in observation["ui"]["accessibleEnvironmentObjects"]:
#         name = obj["name"]
#         uuid = obj["uuid"]
#         strOut = "{\"name\": \"" + name + "\", \"uuid\": " + str(uuid) + "}"
#         objStrs.append(strOut)

#     jsonOut = "[" + ", ".join(objStrs) + "]"
#     return jsonOut



#
#   Random agent, that randomly selects one valid action to take at each step.
#
def randomAgent(api, numSteps:int = 10, seed:int = None, debug:bool = False):

    # Step 1: Seed the random number generator (that selects the random actions).
    r = random.Random()
    if (seed == None):
        # No seed provided -- use the current time (in integer form) as a seed
        intTime = int(time.time())
        r.seed(intTime)
        print("Random Agent Seed: " + str(intTime))
    else:
        # Seed provided -- use it.
        r.seed(seed)
        print("Random Agent Seed: " + str(seed))

    # Step 2: Record the time we started running the agent, so we can keep track of how long a run takes.
    startTime = time.time()

    ## DEBUG: There is only one agent in the environment (and if there were multiple agents, each would be attached to it's own "ui").  This shows how to display that.
    uis = api.ui
    print("Number of agents: " + str(len(uis)))
    firstAgent = uis[0]
    #print(firstAgent)
    #print(firstAgent.currentAgent)


    # Step 3: Run the random agent for `numSteps` steps in the environment
    for i in range(numSteps):
        # Step 3A: Show a message to the user indicating the step number
        print("\n\n")
        print("-----------------------------------------------------------")
        print("Step " + str(i) + " of " + str(numSteps))
        print("-----------------------------------------------------------")
        print("")

        # Step 3B: Get an observation from the environment (typically, this is the agent's view of the world, that it (or a player) use to decide what action to take next)
        observation = api.getAgentObservation(agentIdx=0)
        # Observation dictionary structure:
        # errors (list): any errors. If there are no errors, this list is empty.
        # vision (dict): the agent's (2D, image) vision, which includes two base64 encoded images under the keys `base64_no_grid`, and `base64_with_grid`. NOTE: THESE STRINGS ARE HUGE. Remove them from the observation if you provide the `observation` string to (e.g.) an LLM agent.
        # ui (dict): the user interface, which contains the following keys:
        #   accessibleEnvironmentObjects (list): a list (of dictionaries) representing objects in the environment that are directly in front of the the agent, that it can interact with without moving. Each object dictionary contains keys: `name`, `description`, `uuid`
        #   nearbyObjects (dictionary): Lists nearby objects in the environment (i.e. within a few tiles) that the agent can "see". Keys: `distance` (int representing how far the farthest object is), `objects` (dictionary, keys are `north`, `east`, `south`, `west`, `north-east`, `north-west`, `south-east`, `south-west`, `same_location`. Each key has a list of objects, represented as dictionaries, with keys `name`, `description`, `uuid`, and `distance` (distance from agent))
        #   agentLocation (dict): a dictionary representing the agent's location. Contains the following keys: x (int), y (int), "faceDirection" (north/east/south/west), "directions_you_can_move" (list), "directions_blocked" (list)
        #   dialog_box (dict): a dictionary with a single boolean key ("is_in_dialog") representing whether the agent is in dialog or not.
        #   discoveryFeed (dict): keys: 'description', 'posts' (list of dictionaries, each with keys: `author`, `content`, `postID`, `step`, `type`)
        #   extended_action_message (string): a message about the last action taken, if that message was particularly long.  Rarely used.
        #   inventoryObjects (list): a list (of dictionaries) representing objects in the agent's inventory. Each object dictionary contains keys: `name`, `description`, `uuid`
        #   lastActionMessage (string): a message about the last action taken
        #   nearbyAgents (dictionary): Lists the recent actions of nearby agents.
        #   taskProgress (list): A list of dictionaries of active tasks, though this is usually a single active task.  Each dictionary contains keys: `taskName`, `description` (a natural language description of the task suitable for providing agents/users), `completed` (whether successfully or not), and `completedSuccessfully`.
        #   world_steps (int): the number of world steps that have passed since the start of the scenario.

        # Print the observation
        if (debug == True):
            print(json.dumps(observation, indent=4, sort_keys=True))

        # Print the observation
        if (debug == True):
            print(json.dumps(observation, indent=4, sort_keys=True))

        # Step 3C: Get task progress
        taskScorecard = api.getTaskScorecard()
        if (debug == True):
            # DiscoveryWorld supports showing a detailed scorecard, that describes specific milestones that an agent generally achieves towards making a discovery.  Note that this scorecard contains oracle knowledge, and should never be provided to the agent.
            print("Task Scorecard: ")
            print(json.dumps(taskScorecard, indent=4, sort_keys=True))
        else:
            # Just show the normalized score
            print("Task Score (normalized): " + str(taskScorecard[0]["scoreNormalized"]))


        # Step 3D: Take an action.  Note, because this is a random agent, the action is randomly selected rather than conditioned on the observation (or any internal state based on past interactions).
        # NOTE: There are two main types of actions: Dialog actions (which are a special case), and normal actions.
        # First, we'll check if the agent is engaged in dialog (therefore requiring a dialog action).
        if (api.isAgentInDialog(agentIdx=0)):
            # Agent is in dialog.  The dialog is in pre-defined dialog trees, so action (i.e. dialog) that we select must be one of the dialog options from the current location in the dialog tree.
            dialog = observation["ui"]["dialog_box"]  # Get the dialog

            # DEBUG: Show the dialog tree
            print("Agent is in dialog")
            print(json.dumps(dialog, indent=4, sort_keys=True))

            #promptDialogStr = "The expected response format is JSON, in between code brackets (```), as a dictionary with a single key: `chosen_dialog_option_int`.  The value should be an integer, corresponding to the dialog option you would like to select. You can write prose before the JSON code block, if that helps you think.\n"
            # They keys in `dialog` are: `dialogIn` (the text from the NPC the agent is talking to), `dialogOptions` (a dictionary, keys: option string to select, value: what to say)
            possibleOptions = dialog["dialogOptions"].keys()
            # Randomly select one option
            chosenOption = r.choice(list(possibleOptions))

            # NOTE: The option keys are provided as strings, for some reason. Try to convert the option to an integer
            try:
                chosenOptionInt = int(chosenOption)
            except:
                chosenOptionInt = random.randint(1, len(possibleOptions)+1)

            # Format the dialog action
            dialogActionJSONOut = {
                "chosen_dialog_option_int": chosenOptionInt
            }

            # Send the dialog action
            actionSuccess = api.performAgentAction(agentIdx=0, actionJSON=dialogActionJSONOut)
            print("actionSuccess: " + str(actionSuccess))

        else:
            # Normal action.  All non-dialog actions look like this.
            # Normal actions tend to take the form of an action verb (e.g. move, pickup, drop, open, close, etc.) and zero, one, or two arguments (e.g. the object to move, the object to pickup, the object to drop, etc.)

            # Get the list of objects that's accessible to the agent (which might serve as arguments to an action verb).  The list of accessible objects is provided in the observation.
            # Note: While the arguments are often objects, sometimes they are other things (e.g. directions, numbers, etc., as specified below)
            accessibleObjects = observation["ui"]["inventoryObjects"] + observation["ui"]["accessibleEnvironmentObjects"]

            # Get a dictionary of all possible actions
            # The keys of the dictionary represent the action name.
            # The 'args' field of a given key represents what arguments must be populated (with objects)
            possibleActions = api.listKnownActions(limited=LIMITED_ACTIONS)     # If LIMITED_ACTIONS is True, then the "talk <to another character>" and "discovery feed" actions will not be included in the action space.

# NOTE: Below is a list of possible actions, with descriptions of what they do.  This is provided for reference, and is not used in the code.  This is generally returned by `api.listKnownActions()`.
# def getActionDescriptions(limited:bool = False):
#     actionDescriptions = {
#         ActionType.PICKUP.name:         {"args": ["arg1"], "desc": "pick up an object (arg1)"},
#         ActionType.DROP.name:           {"args": ["arg1"], "desc": "drop an object (arg1)"},
#         ActionType.PUT.name:            {"args": ["arg1", "arg2"], "desc": "put an object (arg1) in/on another object (arg2), or give an object (arg1) to another agent (arg2)"},
#         ActionType.OPEN.name:           {"args": ["arg1"], "desc": "open an object (arg1)"},
#         ActionType.CLOSE.name:          {"args": ["arg1"], "desc": "close an object (arg1)"},
#         ActionType.ACTIVATE.name:       {"args": ["arg1"], "desc": "activate an object (arg1)"},
#         ActionType.DEACTIVATE.name:     {"args": ["arg1"], "desc": "deactivate an object (arg1)"},
#         ActionType.TALK.name:           {"args": ["arg1"], "desc": "talk to another agent (arg1)"},
#         ActionType.EAT.name:            {"args": ["arg1"], "desc": "eat an object (arg1)"},
#         ActionType.READ.name:           {"args": ["arg1"], "desc": "read an object (arg1)"},
#         ActionType.USE.name:            {"args": ["arg1", "arg2"], "desc": "use an object (arg1), e.g. a thermometer, on another object (arg2), e.g. water."},

#         ActionType.MOVE_DIRECTION.name:     {"args": ["arg1"], "desc": "move in a specific direction (arg1), which is one of 'north', 'east', 'south', or 'west'."},
#         ActionType.ROTATE_DIRECTION.name:   {"args": ["arg1"], "desc": "rotate to face a specific direction (arg1), which is one of 'north', 'east', 'south', or 'west'."},
#         ActionType.TELEPORT_TO_LOCATION.name:   {"args": ["arg1"], "desc": "teleport to a specific location (arg1), by name. A list of valid teleport locations is provided elsewhere."},
#         ActionType.TELEPORT_TO_OBJECT.name:     {"args": ["arg1"], "desc": "teleport beside a specific object (arg1). 'arg1' should be the UUID of the object to teleport to."},

#         ActionType.DISCOVERY_FEED_GET_UPDATES.name:     {"args": [], "desc": "read the latest status updates on discovery feed"},
#         ActionType.DISCOVERY_FEED_GET_POST_BY_ID.name:  {"args": ["arg1"], "desc": "read a specific post on discovery feed (arg1). 'arg1' should be the integer ID of the post."},
#     }

            # Randomly pick an action to take from the list of actions
            actionName = r.choice(list(possibleActions.keys()))

            # Check what arguments are required for this action
            actionArgs = possibleActions[actionName]["args"]

            # Assemble the action JSON
            actionJSONOut = {
                "action": actionName,
                "arg1": None,
                "arg2": None
            }

            # Pick random objects for the two action arguments
            for arg in actionArgs:
                # Pick a random object from the list of accessible objects
                obj = r.choice(accessibleObjects)
                # Set the argument (NOTE: Arguments are populated by specifying the UUID of a given object)
                actionJSONOut[arg] = obj["uuid"]

            ## Handle special case actions that take arguments **other than object UUIDs** (such as directions, locations, etc.)
            ## Note that being in a dialog is handled separately as a special case (above).
            if (actionName == "MOVE_DIRECTION"):
                # Move action: pick a random direction from a list of known directions
                direction = r.choice(["north", "east", "south", "west"])
                actionJSONOut["arg1"] = direction

            elif (actionName == "ROTATE_DIRECTION"):
                # Rotate agent to face a given direction: pick a random direction from a list of known directions
                direction = r.choice(["north", "east", "south", "west"])
                actionJSONOut["arg1"] = direction

            elif (actionName == "TELEPORT_TO_LOCATION"):
                # Teleport agent to a specific location: Each scenario generally comes with a list of known locations the agent can teleport to.
                teleportLocations = api.listTeleportLocationsDict() # Get the list of teleport locations
                teleportLocations = list(teleportLocations.keys())  # Get the keys (i.e. the names of the locations, like "kitchen", "lab", etc., that are valid for this scenario)
                print("Teleport Locations:")        # Debug: Display the list of teleport locations
                print(str(teleportLocations))

                # Pick a random location
                location = r.choice(teleportLocations)
                actionJSONOut["arg1"] = location

            elif (actionName == "DISCOVERY_FEED_GET_POST_BY_ID"):
                # Randomly pick the ID of a DiscoveryFeed post to display.  Note that the random agent, unable to read observations, will not do anything with this information anyway.
                postID = r.randint(1, 100)
                actionJSONOut["arg1"] = postID

            else:
                # This should never happen.
                pass

            # Show the action that we've assembled
            print("Random action: " + json.dumps(actionJSONOut))

            # Perform the action
            result = api.performAgentAction(agentIdx=0, actionJSON=actionJSONOut)
            print("Result: " + str(result))
            if ("success" in result):
                print("ActionSuccess: " + str(result["success"]))

        # Step 3E: Perform the world tick.  This must happen at the end of each step, after each agent has taken an action.  This updates the world state.
        api.tick()



    # Step 4: Calculate elapsed time of this run.
    deltaTime = time.time() - startTime
    print("Elapsed time: " + str(deltaTime) + " seconds for " + str(numSteps) + " steps.")
    print("Average time per step: " + str(deltaTime / numSteps) + " seconds.")
    print("Average steps per second: " + str(numSteps / deltaTime) + " steps per second.")



#
#   The main entry point to initializing the DiscoveryWorld API, setting it to a particular environment, then running the Random agent in that environment.
#
def runRandomAgent(scenarioName:str, difficultyStr:str, seed:int=0, numSteps:int=10, exportVideo:bool=False, threadId:int=1, debug:bool=False):
    # Step 1: Load the scenario
    api = DiscoveryWorldAPI(threadID=threadId)
    success = api.loadScenario(scenarioName = scenarioName, difficultyStr = difficultyStr, randomSeed = seed, numUserAgents = 1)
    if (success == False):
        print("Error: Could not load scenario '" + scenarioName + "' with difficulty '" + difficultyStr + "'.")
        return None

    # Step 2: Keep track of the time
    startTime = time.time()

    # Step 3: Run the random agent
    logFileSuffix = "." + scenarioName + "-" + difficultyStr + "-s" + str(seed) + "-thread" + str(api.THREAD_ID)        # Log file suffix, for keeping track of the run
    # Step 3A: Run the random agent
    randomAgent(api, numSteps=numSteps, debug=debug)
    # Step 3B: Calculate elapsed time of this run.
    deltaTime = time.time() - startTime
    print("Elapsed time: " + str(deltaTime) + " seconds for " + str(numSteps) + " steps.")
    stepsPerSecond = numSteps / deltaTime

    # Step 4: Get the final scorecard, which provides detailed scoring information about how far the agent progressed in the task.
    finalScorecard = api.getTaskScorecard()
    print("Final scorecard: ")
    print(json.dumps(finalScorecard, indent=4, sort_keys=True))

    # Here's an example of what a scorecard looks like (this is just a cartoon example, but the keys are the same):
    # THE SCORECARD IS ENTIRELY ORACLE KNOWLEDGE, THE AGENT SHOULD NEVER KNOW ANY OF THIS KNOWLEDGE -- IT'S JUST FOR EVALUATION PURPOSES AFTER A RUN.
    # YOU SHOULD NEVER USE THE KNOWLEDGE IN THE SCORECARD TO DESIGN AN AGENT -- IT'S ORACLE KNOWLEDGE!
    # [
    #     {
    #         "completed": false,               # Is the task completed?
    #         "completedSuccessfully": false,   # Was the task completed successfully? This is the "Task Completion" score (True = 1, False = 0)
    #         "criticalHypotheses": [           # The critical hypotheses are the main idea the agent must discover to complete the task.
    #             "If the onion seeds are planted in a pot with soil and watered at least every 10 steps for 50 steps, they will grow successfully."
    #         ],
    #         "criticalQuestions": [            # The critical questions are used to evalutate an agent's "Explanatory Discovery Knowledge".  The agent's knowledge is searched to answer these questions.  The proportion of these questions that are answered correctly is the "Explanatory Discovery Knowledge" score.
    #             "Does it clearly state that the onion seeds must be in soil to grow?",
    #             "Does it clearly state that the onion seeds must be watered, either qualitatively (i.e. 'frequently'), or quantitatively (i.e. 'every N steps', where N<=10) to grow?",
    #         ],
    #         "maxScore": 12,                   # Procedure score: The maximum possible (non-normalized) procedure score for this task.
    #         "score": 1,                       # Procedure score: The agent's current (non-normalized) procedure score for this task.
    #         "scoreCard": [                    # Procedure score: The components of the procedure score.  Each component is a milestone that the agent might cannonically achieve to make a discovery.
    #             {
    #                 "associatedNotes": "The shovel has been in the agent's (UUID: 12345) inventory",  # Notes associated with scoring this milestone
    #                 "associatedUUIDs": [12345],                                           # Object UUIDs in DiscoveryWorld that are associated with the current score for this milestone (e.g. the specific shovel that was in the inventory)
    #                 "completed": false,                                                   # Has this milestone been completed?
    #                 "description": "The shovel has been in the agent's inventory",        # A description of this procedure milestone
    #                 "maxScore": 1,                                                        # Maximum possible score for this milestone
    #                 "name": "Take shovel",                                                # The name of this milestone
    #                 "score": 1                                                            # The agent's current score for this milestone
    #             },
    #             {
    #                 "associatedNotes": "The onion seeds are in the agent's inventory",
    #                 "associatedUUIDs": [67890],
    #                 "completed": false,
    #                 "description": "The onion seeds are in the agent's inventory",
    #                 "maxScore": 1,
    #                 "name": "Take onion seeds",
    #                 "score": 1
    #             },
    #             {
    #                 "associatedNotes": "",
    #                 "associatedUUIDs": [],
    #                 "completed": false,
    #                 "description": "The soil has been prepared",
    #                 "maxScore": 1,
    #                 "name": "Prepare soil",
    #                 "score": 0
    #             },
    #             {
    #                 "associatedNotes": "",
    #                 "associatedUUIDs": [],
    #                 "completed": false,
    #                 "description": "At least 2 onion seeds have been planted in soil",
    #                 "maxScore": 2,        # Maxscore is 2, one for each seed being planted
    #                 "name": "Plant seeds in soil",
    #                 "score": 0
    #             },
    #             {
    #                 "associatedNotes": "",
    #                 "associatedUUIDs": [],
    #                 "completed": false,
    #                 "description": "The seeds have been watered at least 3 times",
    #                 "maxScore": 3,        # Maxscore is 3, one for each watering
    #                 "name": "Water seeds",
    #                 "score": 0
    #             }
    #         ],
    #         "scoreNormalized": 0.0,       # Procedure score: The normalized Procedure Score for this task.
    #         "taskDescription": "You have been tasked with planting onions in your garden. You need to prepare the soil, plant the onion seeds, water them, and ensure they are properly covered. The task will finish when the seeds have grown.",
    #         "taskName": "PlantOnionsTask"
    #     }
    # ]


    # Step 5: Get the final scores from this run
    taskName = finalScorecard[0]["taskName"]

    # Procedure score
    procedureScoreNormalized = finalScorecard[0]["scoreNormalized"]
    # Task completion score
    taskCompletionScore = 0
    if (finalScorecard[0]["completedSuccessfully"] == True):
        taskCompletionScore = 1
    # Explanatory Discovery Knowledge Score
    # While the random agent doesn't have a knowledge base, the Explanatory Discovery Knowledge score is evaluated by checking if the agent's knowledge base contains the critical questions and answers.
    # We'll show an example here, but the random agent doesn't have a knowledge base, so it will always score 0.
    explanatoryDiscoveryKnowledgeScore = 0
    exampleKnowledgeBase = [
        "The shovel is near the large tree",
        "There is a black cat near the flower pot",
        "The onion seeds must be in soil to grow.",
        "A farmer named Sally will help you find the seeds you need."
    ]
    # There's an example knowledge scorer script in the DiscoveryWorld folder, that isn't part of the API.  It uses a call to GPT-4o to evaluate the agent's knowledge base against the critical questions.  This costs money and requires an external API call, so it's commented out here in case it's not used.
    # The input to the knowledge scorer is a single string representing the agent's entire knowledge.
    knowledgeBaseStr = json.dumps(exampleKnowledgeBase, indent=4)
    # from knowledgeScorer import KnowledgeScorer
    # knowledgeScorer = KnowledgeScorer()
    # knowledgeEvaluation = knowledgeScorer.evaluateKnowledge(scenarioName = scenarioName, difficultyStr = difficultyStr, seed = seed, knowledgeToEvaluateStr=knowledgeBaseStr)
    # print("Explanatory Discovery Knowledge Evaluation:")
    # print(json.dumps(evaluation, indent=4, sort_keys=True))
    # knowledgeEvaluationScoreNormalized = None
    #    knowledgeEvaluationError = 0
    #    if (knowledgeEvaluation != None):
    #        knowledgeEvaluationScoreNormalized = knowledgeEvaluation[0]["evaluation_totalscore"]
    #    if (knowledgeEvaluationScoreNormalized == None):
    #        print("ERROR: No knowledge evaluation score found!")
    #        knowledgeEvaluationScoreNormalized = 0
    #        knowledgeEvaluationError = 1
    # print("Explanatory Discovery Knowledge Score: " + str(knowledgeEvaluationScoreNormalized))

    print("Final normalized Procedure score for task '" + taskName + "': " + str(procedureScoreNormalized))
    print("Task completion score for task '" + taskName + "': " + str(taskCompletionScore))

    print("Number of steps: " + str(api.getStepCounter()))
    print("Steps per second: " + str(stepsPerSecond))

    # Step 6: Create a video from the random agent.  Since DiscoveryWorld is also a 2D environment, it's possible to create videos of the agent's actions, which are often desirable (for users to see, debugging, etc.)
    if (exportVideo == True):
        filenameOut = "output_random_agent." + logFileSuffix + ".mp4"
        api.createAgentVideo(agentIdx=0, filenameOut=filenameOut)

    # Step 7: Return the final scores from this run of the agent
    completed = 0
    if (finalScorecard[0]["completed"] == True):
        completed = 1
    completedSuccessfully = 0
    if (finalScorecard[0]["completedSuccessfully"] == True):
        completedSuccessfully = 1

    # Step 7A: Pack the results into a dictionary
    out = {
        "agentName": "RandomAgent",
        "finalNormalizedScore": finalNormalizedScore,
        "completed": completed,
        "completedSuccessfully": completedSuccessfully,
        "stepsPerSecond": stepsPerSecond,
    }
    return out


#
#   Main
#
if __name__ == "__main__":
    print("Initializing DiscoveryWorld API... ")

    # Step 1: Randomly generate a thread ID, in case one isn't specified.  NOTE: Each concurrently running DiscoveryWorld instance needs a unique thread ID, or the threads can crash into each other.
    # Random seed based on the current time
    rThread = random.Random()
    rThread.seed(int(time.time()))
    randomThreadId = rThread.randint(1, 10000000)

    # Parameter settings:
    # Scenarios (CASE SENSITIVE): Tutorial, Combinatorial Chemistry, Archaeology Dating, Plant Nutrients, Reactor Lab, Lost in Translation, Space Sick, Proteomics, It's (not) Rocket Science!, Small Skills: Dialog Test, Small Skills: Pick and Place Test, Small Skills: Pick and Give Test, Small Skills: Instrument Measurement Test, Small Skills: Doors Test, Small Skills: Doors with Keys Test, Small Skills: Navigation in a House Test, Small Skills: Search Test, Small Skills: Discovery Feed Test, Small Skills: Moving Agents Test    # Step 2: Parse command line arguments
    # Difficulties (CASE SENSITIVE): "Easy", "Normal", "Challenge" (for main discovery scenarios), "Normal" (for tutorial or small skill scenarios)
    # Seeds: 1,2,3,4,5
    # Number of steps: Usually small for debugging (e.g. 5-10).  "Easy" discovery scenarios/small skills usually allow up to 100 steps.  "Normal" and "Challenge" Discovery scenarios may allow 1000+ steps (but this affects cost, so be careful).
    import argparse
    parser = argparse.ArgumentParser(description="Play DiscoveryWorld using Random Baseline Agent.")
    parser.add_argument('--scenario', choices=SCENARIO_NAMES, default=None)  # The scenario name (e.g. "Combinatorial Chemistry", )
    parser.add_argument('--difficulty', choices=SCENARIO_DIFFICULTY_OPTIONS.values(), default=None)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--numSteps', type=int, default=100)
    parser.add_argument('--runall', action='store_true', help='Run all scenarios with random agent')
    parser.add_argument('--video', action='store_true', help='Export video of agent actions')
    parser.add_argument('--threadId', type=int, default=randomThreadId)

    args = parser.parse_args()
    print("Using Thread ID: " + str(args.threadId))
    print("This can be specified with the '--threadId' argument.")
    time.sleep(1)

    # Step 3: Get a timestamp (useful for adding to log files/etc.)
    import datetime
    now = datetime.datetime.now()
    dateStr = now.strftime("%Y-%m-%d_%H-%M-%S")

    # Step 4: Check what mode to run the environment in.
    stepsPerSecond = []
    if (args.runall == True):

        # Run all scenarios. Note, this is VERY EXPENSIVE/can take a long time.
        scores = {}
        completed = {}
        completedSuccessfully = {}
        # For every scenario in this benchmark
        for scenarioName in SCENARIO_NAMES:
            # Get the valid difficulty settings and random seeds for this scenario
            validDifficulties = SCENARIO_INFOS[scenarioName]["difficulty"]
            validSeeds = SCENARIO_INFOS[scenarioName]["variations"]
            validSeeds = [int(x)-1 for x in validSeeds]     # -1 to convert from 1-indexed to 0-indexed

            # For every valid difficulty for this scenario
            for difficulty in validDifficulties:
                # For every valid random seed (i.e. parametric variation of this task) for this scenario
                for seed in validSeeds:
                    # Run the random agent for this scenario/difficulty/seed(parametric variation)
                    print("Running scenario: " + scenarioName + " with difficulty " + difficulty)

                    # The random agent has a habbit of finding difficult-to-find bugs.  If it crashes, just restart.
                    attempts = 0
                    MAX_ATTEMPTS = 10
                    done = False
                    while (done == False) and (attempts < MAX_ATTEMPTS):
                        try:
                            # Run the random agent for this scenario/difficulty
                            result = runRandomAgent(scenarioName=scenarioName, difficultyStr=difficulty, seed=seed, numSteps=args.numSteps, exportVideo=False, threadId = args.threadId, debug=False)
                            done = True

                            # Record the results
                            finalScore = result["finalNormalizedScore"]
                            stepsPerSecond.append(result["stepsPerSecond"])
                            completed1 = result["completed"]
                            completedSuccessfully1 = result["completedSuccessfully"]

                            scoreKey = scenarioName + "-" + difficulty
                            if (scoreKey not in scores):
                                scores[scoreKey] = []
                                completed[scoreKey] = []
                                completedSuccessfully[scoreKey] = []

                            scores[scoreKey].append(finalScore)
                            completed[scoreKey].append(completed1)
                            completedSuccessfully[scoreKey].append(completedSuccessfully1)

                        # Handle keyboard exception, or killing the process
                        except KeyboardInterrupt:
                            print("Keyboard interrupt.")
                            exit(1)
                        except:
                            print("Error: Random agent crashed.  Restarting.")
                            attempts += 1


            # Calculate average scores
            scoresAvg = {}
            for key in scores:
                scoreList = scores[key]
                # Remove any Nones from the list
                scoreList = [x for x in scoreList if x != None]
                averageScore = None
                if (len(scoreList) > 0):
                    averageScore = sum(scoreList) / len(scoreList)
                scoresAvg[key + "-avg"] = averageScore
                scoresAvg[key + "-raw"] = scoreList

            # Completed average scores
            completedAvg = {}
            for key in completed:
                completedList = completed[key]
                completedList = [x for x in completedList if x != None]
                completedAvg[key + "-avg"] = sum(completedList) / len(completedList)
                completedAvg[key + "-raw"] = completedList

            # Completed Successfully average scores
            completedSuccessfullyAvg = {}
            for key in completedSuccessfully:
                completedSuccessfullyList = completedSuccessfully[key]
                completedSuccessfullyList = [x for x in completedSuccessfullyList if x != None]
                completedSuccessfullyAvg[key + "-avg"] = sum(completedSuccessfullyList) / len(completedSuccessfullyList)
                completedSuccessfullyAvg[key + "-raw"] = completedSuccessfullyList

            print("Final scores: ")
            packed = {
                "numSteps": args.numSteps,
                "scores_raw": scores,
                "scores_avg": scoresAvg,
                "completed_raw": completed,
                "completed_avg": completedAvg,
                "completedSuccessfully_raw": completedSuccessfully,
                "completedSuccessfully_avg": completedSuccessfullyAvg,
            }
            print(json.dumps(packed, indent=4, sort_keys=True))

            # Save to file with a verbose filename
            # Add date/time
            filenameOut = "output_random_agent-allscenarios-numSteps" + str(args.numSteps) + "-thread" + str(args.threadId) + "." + dateStr + ".json"
            with open(filenameOut, "w") as f:
                json.dump(packed, f, indent=4, sort_keys=True)



    else:
        # Run a single scenario. This is much more common.
        # Check the scenario and difficulty
        if (args.scenario == None):
            print("Error: Must specify a scenario (or use --runall to run all scenarios).")
            print("Available scenarios: " + str(SCENARIO_NAMES))
            exit()
        if (args.difficulty == None):
            print("Error: Must specify a difficulty.")
            print("Available difficulties: " + str(SCENARIO_DIFFICULTY_OPTIONS))
            exit()

        # Get the internal scenario name (this is because, for example, "scenario"="Combinatorial Chemistry" and "difficulty"="easy" translates internally to the `combinatorial_chemistry_easy` scenario.)
        internalScenarioName = getInternalScenarioName(args.scenario, args.difficulty)
        if (internalScenarioName == None):
            print("Error: Could not find internal scenario name for scenario '" + args.scenario + "' and difficulty '" + args.difficulty + "'.")
            print("Available scenarios: " + str(SCENARIO_NAMES))
            print("Available difficulties: " + str(SCENARIO_DIFFICULTY_OPTIONS))
            exit()

        exportVideo = args.video
        # Run the random agent for this scenario/difficulty
        finalScores = runRandomAgent(scenarioName=args.scenario, difficultyStr=args.difficulty, seed=args.seed, numSteps=args.numSteps, exportVideo=exportVideo, threadId=args.threadId, debug=False)
        # Populate additional information into the final scores, so we can reconstruct the run settings later if needed (e.g. for more specific follow-on analyses)
        finalScores["scenario"] = args.scenario
        finalScores["difficulty"] = args.difficulty
        finalScores["numSteps"] = args.numSteps
        finalScores["seed"] = args.seed
        finalScores["threadId"] = args.threadId

        # Print the final scores to the user console
        print("Final scores: ")
        print(json.dumps(finalScores, indent=4, sort_keys=True))
        # Important: Save the final scores to a file, so we can analyze/reanalyze them later.
        filenameOut = "output_random_agent." + args.scenario + "-" + args.difficulty + "-s" + str(args.seed) + "-thread" + str(args.threadId) + "." + dateStr + ".json"
        print("Writing " + filenameOut + "...")
        with open(filenameOut, "w") as f:
            json.dump(finalScores, f, indent=4, sort_keys=True)

        # Mark the run as completed.
        print("Completed...")