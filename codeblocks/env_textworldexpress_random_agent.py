# Name: TextWorldExpress API Example
# Description: This is an example of how to use the TextWorldExpress API.  TextWorldExpress is a simulator for interactive text-based games, that reimplements a limited subset of existing games that run very quickly (CookingWorld, TextWorld Common Sense, Coin Collector, plus MapReader, Arithmetic, and Sorting).  Several of the games (CookingWorld, TextWorld Common Sense, Coin Collector, and Mapreader) share a common environment generator, to help control for e.g. navigational complexity across these tasks.  All environments are parametrically generated based on a provided seed (with different seeds assigned to train/dev/test sets). This example includes only a very simple random agent (that randomly selects actions to take).
# inclusion_criteria: You would normally use this codeblock if you'd like an agent (or human) to play/interact with one or more games/scenarios/tasks provided with TextWorldExpress, and would like to see an example of how to do so.
# exclusion_criteria: If you're not specifically using TextWorldExpress, this codeblock will likely not be useful (except perhaps as a broad example of how to interface with a text-based game).
# python_version: 3.8
# pip_requirement: textworld-express==1.0.4

import time
import random
import argparse
import json

import textworld_express as twx
from textworld_express import TextWorldExpressEnv

# Available games and game parameters:
# ['cookingworld', 'twc', 'coin', 'mapreader', 'arithmetic', 'sorting']

# CookingWorld (`cookingworld`):
# numLocations       (1-11): The number of locations in the environment (default=11)
# numIngredients     (1-5):  The number of ingredients to use in generating the random recipe (default=3)
# numDistractorItems (0-10): The number of distractor ingredients (not used in the recipe) in the environment (default=10)
# includeDoors       (0 or 1): Whether rooms have doors that need to be opened (default=1)
# limitInventorySize (0 or 1): Whether the size of the inventory is limited (default=1)

# TextWorld Common Sense (`twc`):
# numLocations       (1-3):  The number of locations in the environment (default=3)
# numItemsToPutAway  (1-10): The number of items to put away in the environment (default=4)
# includeDoors       (0 or 1): Whether rooms have doors that need to be opened (default=0)
# limitInventorySize (0 or 1): Whether the size of the inventory is limited (default=0)

# Coin Collector (`coin`):
# numLocations       (1-11): The number of locations in the environment (default=11)
# numDistractorItems (0-10): The number of distractor (i.e. non-coin) items in the environment (default=0)
# includeDoors       (0 or 1): Whether rooms have doors that need to be opened (default=1)
# limitInventorySize (0 or 1): Whether the size of the inventory is limited (default=1)

# Map Reader (`mapreader`):
# numLocations                  (1-50): The number of locations in the environment (default=15)
# maxDistanceApart              (1-8):  The maximum distance between the starting location and target location, measured in room locations (default=4)
# maxDistractorItemsPerLocation (0-3):  The maximum number of distractor (i.e. non-coin) items per location (default=3)
# includeDoors                  (0 or 1): Whether rooms have doors that need to be opened (default=0)
# limitInventorySize            (0 or 1): Whether the size of the inventory is limited (default=0)

# Arithmetic (`arithmetic`):
# This environment has no tweakable parameters yet.

# Sorting (`sorting`):
# This environment has no tweakable parameters yet.


totalTime = 0
totalSteps = 0

# An example of a random agent that randomly picks actions in a given game in TextWorldExpress
def randomModel(args):
    global totalTime, totalSteps
    """ Example random agent -- randomly picks an action at each step. """
    exitCommands = ["quit", "exit"]

    # Step 1: Get the game name and number of episodes to run
    gameName = args['game_name']
    numEpisodes = args['num_episodes']

    # Step 1A: Keep track of the agent's final scores, and number of games completed successfully
    finalScores = []
    gamesWon = []

    # Step 2: Initialize the TextWorldExpress game environment
    env = TextWorldExpressEnv(envStepLimit=args['max_steps'])
    gameNames = env.getGameNames()  # Get the list of supported games, e.g. ['cookingworld', 'twc', 'coin', 'mapreader', 'arithmetic', 'sorting']
    print("Supported Game Names: " + str(gameNames))

    # Step 3: Load the task
    gameFold = "train"  # "train", "dev", or "test"
    gameSeed = None     # `None` for a random parametric variation within the requested train/dev/test set, or a specific seed for a specific parametric task variation.
                        # NOTE: If specifying specific seeds, *MUST* use `getValidSeedsTrain()`, `getValidSeedsDev()`, and `getValidSeedsTest()` to get the valid seeds for each set. DO NOT JUST PICK SEED NUMBERS (e.g. 1, 2, 3), THEY MAY NOT BE VALID FOR THE SPECIFIC TRAIN/DEV/TEST SET! Get valid seeds from these functions!
    gameParams = ""     # A string representing game-specific initialization parameters. e.g. "numLocations=5, numIngredients=3, numDistractorItems=0, includeDoors=0, limitInventorySize=0", as described above.  Leaving blank uses default parameters.
    generateGoldPath = args['gold_paths']       # Whether or not to generate a gold path/trajectory that describes a sequence of actions that solve the task.
    # Load the task (note, both `gameName` and `gameParams` are required, even if `gameParams` is an empty string)
    env.load(gameName=gameName, gameParams=gameParams)

    time.sleep(2)

    print("Starting to run " + str(numEpisodes) + " episodes...")
    # REQUIRED: Get the seeds for the appropriate set
    validGameSeeds = env.getValidSeedsTrain() if (gameFold == "train") else (env.getValidSeedsDev() if (gameFold == "dev") else env.getValidSeedsTest())
    random.shuffle(validGameSeeds)  # Randomly shuffle the seeds, since neighbouring seeds can have similar environment properties.

    # Step 4: Start running some number of full episodes
    for episodeIdx in range(0, numEpisodes):
        startTime = time.process_time()     # Keep track of the start time for this episode

        # Step 4A: Verbose output mode
        if (args['verbose'] == True):
            print("")
            print("Episode " + str(episodeIdx))
            print("Generation properties:\n" + str(json.dumps(env.getGenerationProperties(), indent=4)) )

        # Step 4B: Initialize a random task variation in this set.
        # NOTE: `gameFold`, `generateGoldPath`, and `gameSeed` are REQUIRED parameters for `env.reset()`. `gameSeed` can be `None` for a random parametric variation within the requested train/dev/test set, or a specific seed for a specific parametric task variation.
        seed_this_episode = validGameSeeds[episodeIdx % len(validGameSeeds)]    # Get a seed for this episode.
        obs, infos = env.reset(gameFold=gameFold, generateGoldPath=generateGoldPath, seed=seed_this_episode)    # NOTE: The seeds for train/dev/test sets are different.  You should only use verified good seeds (from `getValidSeedsTrain()`, `getValidSeedsDev()`, `getValidSeedsTest()`) for each set.
        # Example of the `observation` and `infos` objects:
        # obs (string): The observation/reply from the environment simulator based on the last action provided from the user (starts off assuming the first action was `look around`).  See below for examples.
        # infos (dict) = {
        #     "lastActionStr": "look around",  # The last action string that was taken.  NOTE: THIS KEY IS NOT PRESENT IN THE `INFOS` RETURNED FROM ENV.RESET()
        #     "observation": "You are in the kitchen. In one part of the room you see a stove. There is also an oven. You also see a fridge that is closed. ...",  # The observation/reply from the environment simulator based on the last action provided from the user (starts off assuming the first action was `look around`)
        #     "look": "You are in the kitchen. In one part of the room you see a stove. There is also an oven. You also see a fridge that is closed. In another part of the room you see ...",  # String describing what the environment would return if the player said `look around` (i.e. a description of the current room).
        #     "inventory": "Inventory (maximum capacity is 5 items): \n  Your inventory is currently empty.\n",     # String describing the player's current inventory
        #     "validActions": [         # List of valid actions
        #         "inventory",
        #         "open door to north",
        #         "examine kitchen cupboard",
        #         "read cookbook",
        #         "move south",
        #         "examine fridge",
        #         "open fridge",
        #         "look around",
        #         "examine dishwasher",
        #         "move north",
        #         ...
        #     ],
        #     "scoreRaw": 0.0,          # The raw score from the game
        #     "score": 0.0,             # The normalized score
        #     "tasksuccess": false,     # Whether the task has been completed successfully
        #     "taskfailure": false,     # Whether the task has failed
        #     "reward": 0,              # The reward for the last action
        #     "done": false,            # Whether the episode is done (i.e. meeting a success/failure condition, exceeding the maximum number of steps, etc.)
        #     "numMoves": 0,            # The current number of moves
        #     "taskDescription": "You are hungry! Let's cook a delicious meal. Check the cookbook in the kitchen for the recipe. Once done, enjoy your meal!"  # The task description
        # }
        #print(obs)
        #print(json.dumps(infos, indent=4))

        # Show the task description to the user
        print("Task Description: " + infos['taskDescription'])

        # Step 4C: Gold action sequence: If the task was generated with a gold action sequence, this function will return a list of actions that solve the task.  If not, the list will have 1 element (noting the error that the gold path wasn't generated)
        # This is, e.g., a way of generating training data from the "training set" of tasks. This is obviously oracle knowledge that should be hidden from an agent outside of training on the training set.
        # This is also not used for the random agent.
        if (gameFold == "train" and generateGoldPath == True):
            # NOTE: env.reset() must be called before this (i.e. the environment is loaded/reset and ready to go) for it to be valid.
            goldSequence = env.getGoldActionSequence()  # e.g. ['look around', 'take cookbook', ...]
            print("Gold action sequence: " + str(goldSequence))


        # Step 5: Start taking actions
        curIter = 0
        # Loop until the episode is done, or we reach the maximum number of steps per episode
        for stepIdx in range(0, args['max_steps']):

            # Step 5A: Select a random action from the list of valid actions.  TextWorldExpress provides a list of valid actions for the current state, and rather than being templates (e.g. `take OBJ`, `open OBJ`), they are complete action strings (e.g. `take apple`, `open fridge`)
            validActions = infos['validActions']            # Get the valid actions for this step
            randomAction = random.choice(validActions)      # Randomly pick one

            # Verbose output mode
            if (args['verbose'] == True):
                print("Step " + str(stepIdx))
                print("Observation: " + str(obs))
                print("Next random action: " + str(randomAction))

            # Step 5B: Take the action.  This sends the action string (`randomAction`) to the environment simulator, and gets the next observation/info in response to that.
            # NOTE: Because this is a random agent that doesn't condition what action it chooses on the observation/environment state, we just disregard this.
            obs, _, _, infos = env.step(randomAction)
            current_score = infos['score']
            print("Current Score: " + str(current_score))

            # Step 5C: Increment the number of steps.
            curIter += 1

            # Step 5D: Check if the game is done
            if (infos['done'] == True):
                break

        # Step 6: Check the game score, and whether the game was won
        finalScores.append(infos['score'])
        if (infos['tasksuccess'] == True):
            gamesWon.append(1)
        else:
            gamesWon.append(0)

        # Step 7: Keep track of timing
        deltaTime = time.process_time() - startTime
        totalTime += deltaTime
        totalSteps += curIter

        # If in verbose mode, print a string representing the run history.
        if (args['verbose'] == True):
            print("History:")
            print(env.getRunHistory())
            # env.getRunHistory() is a logging function with the following format:
            # {
            #   'properties': self.getGenerationProperties(),
            #   'finalScore': finalScore,
            #   'numSteps': len(self.runHistory),
            #   'history': self.runHistory,         # A list of dictionaries, each representing one step in the episode.  The dictionary is identical to the `infos` object returned from `env.step()`
            # }

    # Step 8: Print the final scores
    print("Final Scores: " + str(finalScores))
    print("Games Won: " + str(gamesWon))

    # Start packing the output
    packedOut = {
        'gameName': gameName,
        'numEpisodes': numEpisodes,
        'maxSteps': args['max_steps'],
        'generationProperties': env.getGenerationProperties(),
        'finalScores': finalScores,
        'gamesWon': gamesWon,
        'avgFinalScore': None,
        'propGamesWon': None,
    }

    # Calculate the average final score and proportion of games won
    if (len(finalScores) >= 0):
        # Average final score
        avgFinalScore = sum(finalScores) / len(finalScores)
        print("Average Final Score: " + str(avgFinalScore))
        packedOut["avgFinalScore"] = avgFinalScore

        # Calculate proportion of games completed successfully
        propGamesWon = sum(gamesWon) / len(gamesWon)
        print("Proportion of Games Won: " + str(propGamesWon))
        packedOut["propGamesWon"] = propGamesWon

    # Return
    print("Completed.")
    return packedOut




#
#   Parse command line arguments
#
def parse_args():
    desc = "Run a model that chooses random actions until successfully reaching the goal."
    parser = argparse.ArgumentParser(desc)
    #parser.add_argument("--jar_path", type=str,
    #                    help="Path to the TextWorldExpress jar file. Default: use builtin.")   # Almost never required
    parser.add_argument("--game-name", type=str, choices=twx.GAME_NAMES, default=twx.GAME_NAMES[0],
                        help="Specify the game to play. Default: %(default)s")
    parser.add_argument("--game-fold", type=str, choices=['train', 'dev', 'test'], default='train',
                        help="Specify the game set to use (train, dev, test). Default: %(default)s")
    parser.add_argument("--max-steps", type=int, default=50,
                        help="Maximum number of steps per episode. Default: %(default)s")
    parser.add_argument("--num-episodes", type=int, default=100,
                        help="Number of episodes to play. Default: %(default)s")
    parser.add_argument("--seed", type=int,
                        help="Seed the random generator used for sampling random actions.")
    #parser.add_argument("--game-params", type=str, default="",
    #                    help="Specify game parameters in a comma-delmited list, e.g. 'numLocations=5, includeDoors=1'.")
    parser.add_argument("--gold-paths", action='store_true', help="Generate gold paths for each game episode.")
    parser.set_defaults(gold_paths=False)
    parser.add_argument("--verbose", action='store_true', help="Verbose output.")
    parser.set_defaults(verbose=False)

    args = parser.parse_args()
    params = vars(args)
    return params


def main():
    print("TextWorldExpress 1.0 API Examples - Random Agent")

    # Parse command line arguments
    args = parse_args()
    random.seed(args["seed"])

    # Run the random agent
    results = randomModel(args)

    print("Results:")
    print(json.dumps(results, indent=4))

    rate = totalSteps / totalTime

    print("")
    print("----------------------------------------------------")
    print(" Performance Summary")
    print("----------------------------------------------------")
    print("Total episodes    : " + str(args['num_episodes']))
    print("Total steps       : " + str(totalSteps))
    print("Total time        : " + str(totalTime) + " seconds")
    print("Rate              : " + str(rate) + " steps per second")
    print("----------------------------------------------------")
    print("Average Final Score: " + str(results['avgFinalScore']))
    print("Proportion of Game Episodes Won: " + str(results['propGamesWon']))
    print("----------------------------------------------------")

if __name__ == "__main__":
    main()