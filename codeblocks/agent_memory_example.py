# Name: Memory Agent Example
# Description: This is an example of augmenting an LLM agent architecture with a memory.
# inclusion_criteria: You would normally use this codeblock if you'd like to implement an agent that keeps some kind of extracted or abstracted memory of its past, that it can use to help make future decisions.
# exclusion_criteria: If you're not implementing an agent, or not implementing an agent that needs to remember things, this codeblock is unlikely to be useful.
# python_version: >=3.8

# NOTE: You will need to connect this to (a) an environment/game/simulation/etc, and (b) an LLM library.

import json
from copy import deepcopy

#
#   Placeholders
#

# Placeholder: Agent Memory
class AgentMemory:
    # Constructor
    def __init__(self):
        self.memory = {}

    # Add a memory
    def add_memory(self, key:str, value:str):
        self.memory[key] = value

    # Get a memory
    def get_memory(self, key:str):
        if (key in self.memory):
            return self.memory[key]
        return None

    # Get all memories (can be used to export as JSON, for logging/debugging/etc., to verify that memories are being stored/updated correctly)
    def get_all_memories(self):
        return self.memory

    # Clear a specific memory
    def clear_memory(self, key:str):
        if (key in self.memory):
            del self.memory[key]

    # Clear all memories
    def clear_all_memories(self):
        self.memory = {}

    # Show all memories
    def memories_to_prompt(self):
        prompt = "Your memories:\n"
        prompt += "```\n"
        for key in self.memory:
            prompt += key + ": " + str(self.memory[key]) + "\n"
        prompt += "```\n"
        return prompt

    # Clone
    def clone(self):
        newMemory = AgentMemory()
        newMemory.memory = deepcopy(self.memory)
        return newMemory



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
#   Memory Agent Example
#

def make_common_prompt(task_description:str, current_observation:str, history:list, num_past_steps_to_show:int=5, action_space:list=None, memory:AgentMemory=None):
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
        promptCommon += "Action: " + str(history[i]["action"]) + "\n"
        promptCommon += "\n"
    promptCommon += "```\n"

    # Show the memory (this is critical for memory agents)
    if (memory is not None):
        promptCommon += "You have the following memories:\n"
        promptCommon += "```\n"
        if (len(memory.get_all_memories()) == 0):
            promptCommon += "No memories yet.\n"
        else:
            promptCommon += json.dumps(memory.get_all_memories(), indent=2) + "\n"
        promptCommon += "```\n"

    # Show the action space
    promptCommon += "As an agent, you can take the following actions:\n"
    promptCommon += "```\n"
    promptCommon += str(action_space) + "\n"
    promptCommon += "```\n"

    return promptCommon

# A single step of a memory agent
# NOTE: This implementation has a 'memory' reflection step (to add/update memories), then an 'act' step (to pick an action to take).
# This is a very vanilla memory agent -- you can add more steps, more complexity, or mix with other agent types, as desired.
def memory_agent_one_step(task_description:str, current_observation:str, history:list, num_past_steps_to_show:int=5, action_space:list=None, memory:AgentMemory=None):

    # Step 1: Reflect on the history and current observation, and add/update/modify memories
    promptMemory = make_common_prompt(task_description, current_observation, history, num_past_steps_to_show, action_space, memory)
    # Add the memory-specific prompt.  The purpose of this is to show the agent how it can add/update/modify memories.
    # NOTE: Sometimes memories are free-form, and sometimes they are structured (e.g. a dictionary with keys/values).
    # For example, CLIN uses a causal-themed typed memory (X always/sometimes/never causes Y), that is abstracted over entire episodes, instead of step-by-step.
    # Similarly, Hypothesizer (DiscoveryWorld) uses a science-themed typed memory (including hypotheses and measurements), that is updated after each step.
    promptMemory += "This is a memory reflection step. You should think about what actions you've taken, what things you've observed, and what you might want to remember for the future to help accomplish your task.\n"
    promptMemory += "You now have the opportunity to write yourself memories, which you can use to help guide your future actions.\n"
    promptMemory += "Your memories should be in the form of a JSON dictionary. For example:\n"
    promptMemory += "```json\n"
    promptMemory += "{\n"
    promptMemory += "    \"key\": \"value\"\n"
    promptMemory += "}\n"
    promptMemory += "```\n"
    promptMemory += "Where `key` is the key for the memory, and `value` can be any value, including a string, number, list, or dictionary.\n"
    promptMemory += "Adding memories: To add a new memory, provide a new key-value pair.\n"
    promptMemory += "Memory updates: If you want to update a memory, simply provide the same key with a new value, and the old value will be overwritten.\n"
    promptMemory += "Multiple adds/updates: To add and/or update multiple memories, simply provide multiple key-value pairs in the JSON dictionary.\n"
    promptMemory += "For example:\n"
    promptMemory += "```json\n"
    promptMemory += "{\n"
    promptMemory += "    \"existing_key_1\": {\"action\": \"...\", \"effect\": \"...\"}, # An update to an existing key\n"
    promptMemory += "    \"new_key_1\": \"value\", # A new key, for a new memory\n"
    promptMemory += "}\n"
    promptMemory += "```\n"
    promptMemory += "Please provide your response below, between JSON code blocks.\n"

    # Get the agent's "memory" response
    memoryResponse = get_llm_response(prompt = promptMemory, model="gpt-4o-mini", max_tokens=1000, temperature=0.0, jsonResponse=True) # This is a placeholder function; replace with your own LLM function
    if (isinstance(memoryResponse, dict)):
        # Update the memory
        for key in memoryResponse:
            memory.add_memory(key, memoryResponse[key])

    # Step 2: Have the agent choose an action
    promptAct = make_common_prompt(task_description, current_observation, history, num_past_steps_to_show, action_space, memory)
    promptAct += "Please choose an action from the list above to take.  Your response should be a JSON dictionary, with a single key ('action_str'), that contains the full action as it should be provided to the simulator. For example:\n"
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
    add_step_to_history(current_observation, memory, action, len(history), history)

    # Step 5: Return the action
    return action


# The main memory agent loop
def memory_agent_multiple_steps(simulator, max_steps:int=10, debugMode:bool=False):
    # Initialize the simulator
    simulator.initialize()      # This is a placeholder function; replace with your own simulator initialization function, for a particular task/setup/episode.

    # Get the task description
    task_description = simulator.get_task_description()    # This is a placeholder function; replace with your own simulator task description function

    # Initialize the history
    history = []
    # Initialize a new memory (for agents whose memory resets each episode).
    # If you want memory to persist across episodes, you can initialize it outside the loop (but should be attentive of e.g. adding memories from test episodes to training episodes, etc.)
    # If you have train/test episodes, you may want to keep a static copy of the memory (after training), and just `clone` it for each test episode (so it can still be modified within the test episode, but its changes will not persist across test episodes.)
    agent_memory = AgentMemory()

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
        action = memory_agent_one_step(task_description, current_observation, history, num_past_steps_to_show=5, action_space=action_space, memory=agent_memory)

        if (debugMode):
            print("Action: " + str(action))

        # Take the action in the simulator
        if (action is not None):
            simulator.take_action(action)                   # This is a placeholder function; replace with your own simulator action function. NOTE, some action functions are a combined `step` function that takes an action as input, and returns the next observation as output.  That's OK, you just need to get the initial observation (before any actions have occurred) for the first agent step.
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
    is_completed = simulator.is_completed()              # This is a placeholder function; replace with your own simulator completion check function
    was_won = simulator.was_won()                        # This is a placeholder function; replace with your own simulator win check function

    packedOut = {
        "history": history,
        "score": score,
        "is_completed": is_completed,
        "was_won": was_won
    }

    return packedOut




# Append a step to the history
def add_step_to_history(observation:str, memory:AgentMemory, action:str, step_idx:int, history:list):
    from copy import deepcopy
    history.append({
        "step_idx": step_idx,
        "observation": observation,     # What the agent observed in the environment
        "memory": memory.clone(),       # The agent's memory at this step
        "action": action                # What action the agent chose
    })


# Example of using the memory agent
def example1():
    # Create an instance of the simulator
    example_simulator = Simulator()

    # Run the memory agent for a fixed number of steps
    results = memory_agent_multiple_steps(simulator=example_simulator, max_steps=10, debugMode=True)

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
        print("Memory: " + json.dumps(step["memory"].get_all_memories(), indent=2))
        print("Action: " + str(step["action"]))
        print("")



# Example main function
if __name__ == "__main__":
    example1()