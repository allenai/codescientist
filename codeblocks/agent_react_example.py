# Name: ReAct Agent Example
# Description: This is an example of a ReAct agent (which has separate `think` and `act` steps), tailored to cases with specific action spaces (like text games)
# inclusion_criteria: You would normally use this codeblock if you'd like to implement a ReAct (i.e. reasoning-then-act, or alternatively think-then-act) agent, or an agent derived from that concept.
# exclusion_criteria: If you're not implementing an agent, this codeblock is unlikely to be useful.
# python_version: >=3.8

# NOTE: You will need to connect this to (a) an environment/game/simulation/etc, and (b) an LLM library.

import json


#
#   Placeholders
#

# Placeholder: Simulator, game, or other interactive environment
class Simulator:
    # Constructor
    def __init__(self):
        pass

    # Initialize the simulator
    def initialize(self):
        pass

    # Get the task description
    def get_task_description(self):
        return "This is a placeholder task description."

    # Get the current observation
    def get_observation(self):
        return "This is a placeholder observation."

    # Get the action space
    def get_action_space(self):
        return ["Go north", "Go south", "Go east", "Go west", "Pick up item", "Drop item", "Use item", "Look around", "Quit"]

    # Take an action
    def take_action(self, action:str):
        pass

    # Get the score
    def get_score(self):
        return 0

    # Check if the game/simulation is completed
    def is_completed(self):
        return False

    # Check if the game/simulation was won
    def was_won(self):
        return False


# Placeholder: Get an LLM response
def get_llm_response(prompt:str, model:str, max_tokens:int, temperature:float, jsonResponse:bool=False):
    if (jsonResponse == False):
        # Expect a string out
        return "This is a placeholder response."
    else:
        # Expect a JSON object out
        return {
            "example key": "example value"
        }



#
#   ReAct Agent Example
#

# A single step of a ReAct agent.
# NOTE: This implementation has the 'think' and 'act' in separate LLM calls, though most implementations usually combine these into a single call that generates both 'think' and 'act'.
def react_agent_one_step(task_description:str, current_observation:str, history:list, num_past_steps_to_show:int=5, action_space:list=None):

    # Step 1: Assemble the parts of the prompt that are common to the "think" and "act" steps.
    promptCommon = "You are an agent in a text-based game.  You have the following task: \n"
    promptCommon += "```\n" + task_description + "\n```\n"
    # Show the current observation
    promptCommon += "This is what you currently see: \n"
    promptCommon += "```\n" + current_observation + "\n```\n"
    # IMPORTANT: Show the observation history (to give context), but only out to some maximum number of steps, so the prompt doesn't get too long/exceed the context length.
    # WHY IMPORTANT: If you don't show the history, then the agent doesn't know what it's done in the past, and generally gets stuck in loops/doing the same thing (or, actions that don't matter).
    promptCommon += "You have seen the following observations: \n"
    promptCommon += "```\n"
    for i in range(max(0, len(history)-num_past_steps_to_show), len(history)):
        promptCommon += "Step " + str(history[i]["step_idx"]) + ":\n"
        promptCommon += "Observation: " + str(history[i]["observation"]) + "\n"
        promptCommon += "Think: " + str(history[i]["think"]) + "\n"
        promptCommon += "Action: " + str(history[i]["action"]) + "\n"
        promptCommon += "\n"
    promptCommon += "```\n"

    # Show the action space
    promptCommon += "As an agent, you can take the following actions:\n"
    promptCommon += "```\n"
    promptCommon += str(action_space) + "\n"
    promptCommon += "```\n"


    # Step 2: Get the agent's "think" response
    promptThink = promptCommon
    promptThink += "Please think about what you should do next.  Your response will be used to help determine your next action.\n"
    # Get the agent's "think" response
    thinkResponse = get_llm_response(prompt = promptThink, model="gpt-4o-mini", max_tokens=300, temperature=0.0) # This is a placeholder function; replace with your own LLM function

    # Step 3: Get the agent's "act" response
    promptAct = promptCommon
    promptAct += "Reflecting on your current state, you recently had the following thought: \n"
    promptAct += "```\n" + str(thinkResponse) + "\n```\n"
    promptAct += "Please choose an action from the list above to take, based on your thoughts.  Your response should be a JSON dictionary, with a single key ('action_str'), that contains the full action as it should be provided to the simulator. For example:\n"
    promptAct += "```json\n"
    promptAct += "{\n"
    promptAct += "    \"action_str\": \"Go north\"\n"
    promptAct += "}\n"
    promptAct += "```\n"
    promptAct += "Note that action parsers generally require actions to look EXACTLY as expected, and are unable to handle even minor variations, inserted words, etc.\n"
    promptAct += "Please provide your response below, between JSON code blocks.\n"
    # Get the agent's "act" response
    actResponse = get_llm_response(prompt = promptAct, model="gpt-4o-mini", max_tokens=300, temperature=0.0, jsonResponse=True) # This is a placeholder function; replace with your own LLM function

    action = None
    if ("action_str" in actResponse):
        # Check that the action is the correct type (str)
        if (isinstance(actResponse["action_str"], str)):
            action = actResponse["action_str"]

    # Step 4: Add the step to the history
    add_step_to_history(current_observation, thinkResponse, action, len(history), history)

    # Step 5: Return the action
    return action


# The main ReAct agent loop
def react_agent_multiple_steps(simulator, max_steps:int=10, debugMode:bool=False):
    # Initialize the simulator
    simulator.initialize()      # This is a placeholder function; replace with your own simulator initialization function, for a particular task/setup.

    # Get the task description
    task_description = simulator.get_task_description()    # This is a placeholder function; replace with your own simulator task description function


    # Initialize the history
    history = []

    # Keep track of the number of action generation errors
    num_errors = 0
    num_consecutive_errors = 0

    # Run the agent for a fixed number of steps
    for step_idx in range(max_steps):
        print("At Step: " + str(step_idx))

        # Get the current observation
        current_observation = simulator.get_observation()    # This is a placeholder function; replace with your own simulator observation function
        if (debugMode):
            print("Current Observation: " + current_observation)

        # Get the current actions
        action_space = simulator.get_action_space()          # This is a placeholder function; replace with your own simulator action space function.  e.g. ["Go north", "Go south", "Go east", "Go west", "Pick up item", "Drop item", "Use item", "Look around", "Quit"]
                                                             # NOTE: Sometimes the action space is a list of templates (e.g. "go <direction>", "pick up <item>", etc.), and the agent needs to fill in the blanks based on the observation.  Or, it may be provided both `action templates` and `objects`.

        # Run the agent for one step
        action = react_agent_one_step("This is a placeholder task description.", current_observation, history, num_past_steps_to_show=5, action_space=action_space)

        if (debugMode):
            print("Action: " + str(action))

        # Take the action in the simulator
        if (action is not None):
            simulator.take_action(action)                   # This is a placeholder function; replace with your own simulator action function. NOTE, some action functions are a combined `step` function that takes an action as input, and returns the next observation as output.  That's OK, you just need to get the initial observation (before any actions have occurred) for the first ReAct step.
            num_consecutive_errors = 0
        else:
            num_errors += 1
            num_consecutive_errors += 1

        # Get score  (NOTE, this could optionally be stored in the history, to plot score vs time)
        score = simulator.get_score()
        if (debugMode):
            print("Score: " + str(score))

        # Check for termination
        if (simulator.is_completed()):
            print("The game/simulation has been completed.")
            break

        # Check for too many errors
        MAX_CONSECUTIVE_ERRORS = 3
        if (num_consecutive_errors >= MAX_CONSECUTIVE_ERRORS):
            print("The agent has made too many consecutive errors (" + str(MAX_CONSECUTIVE_ERRORS) + ").  Stopping.")
            break


    # When we reach here, the agent has completed the loop, either by (a) reaching the maximum number of steps, (b) the game/simulation completing some finishing condition (like win/loss), or (c) the agent making too many errors.
    # Return the score
    score = simulator.get_score()                        # This is a placeholder function; replace with your own simulator score function
    is_completed = simulator.is_completed()               # This is a placeholder function; replace with your own simulator completion check function
    was_won = simulator.was_won()                         # This is a placeholder function; replace with your own simulator win check function

    packedOut = {
        "history": history,
        "score": score,
        "is_completed": is_completed,
        "was_won": was_won
    }

    return packedOut




# Append a step to the history
def add_step_to_history(observation:str, think:str, action:str, step_idx:int, history:list):
    history.append({
        "step_idx": step_idx,
        "observation": observation,     # What the agent observed in the environment
        "think": think,                 # What the agent "thought" in the ReAct "think" step
        "action": action                # What action the agent chose
    })


# Example of using the react agent
def example1():
    # Create an instance of the simulator
    example_simulator = Simulator()

    # Run the ReAct agent for a fixed number of steps
    results = react_agent_multiple_steps(simulator=example_simulator, max_steps=10, debugMode=True)

    # Print the results
    print("-----------------------------------")
    print("Results:")
    print("Score: " + str(results["score"]))
    print("Is Completed: " + str(results["is_completed"]))
    print("Was Won: " + str(results["was_won"]))
    print("History:")
    for step in results["history"]:
        print("Step " + str(step["step_idx"]) + ":")
        print("Observation: " + str(step["observation"]))
        print("Think: " + str(step["think"]))
        print("Action: " + str(step["action"]))
        print("")




# Example main function
if __name__ == "__main__":
    example1()