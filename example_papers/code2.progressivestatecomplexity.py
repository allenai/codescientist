import os
import json
import random
import numpy as np
import matplotlib.pyplot as plt
import textworld_express as twx
from textworld_express import TextWorldExpressEnv

from experiment_common_library import Logger, llm_response, bootstrap_resampling, generate_difference_scores_parallel_arrays

# Global configuration
PILOT_MODE = "PILOT"  # Options: "MINI_PILOT", "PILOT", "FULL_EXPERIMENT"
LLM_MODEL = "gpt-4o-mini"

# Create global logger
logger = Logger()

class StateComplexityLevel:
    BOOLEAN = "boolean"
    NUMERICAL = "numerical"
    RELATIONAL = "relational"
    FULL = "full"

class ExperimentConfig:
    def __init__(self, pilot_mode):
        self.pilot_mode = pilot_mode
        if pilot_mode == "MINI_PILOT":
            self.num_episodes = 2
            self.max_steps = 10
            self.complexity_levels = [StateComplexityLevel.BOOLEAN, StateComplexityLevel.FULL]
            self.train_seeds = [1, 2]
            self.dev_seeds = []
            self.test_seeds = []
        elif pilot_mode == "PILOT":
            self.num_episodes = 25  # Modified from 10 to 25
            self.max_steps = 25
            self.complexity_levels = [StateComplexityLevel.BOOLEAN, StateComplexityLevel.NUMERICAL, 
                                    StateComplexityLevel.RELATIONAL, StateComplexityLevel.FULL]
            self.train_seeds = list(range(1, 14))  # Adjusted for 25 episodes (1-13)
            self.dev_seeds = list(range(1, 14))    # Adjusted for 25 episodes (1-13)
            self.test_seeds = []
        else:  # FULL_EXPERIMENT
            self.num_episodes = 100
            self.max_steps = 50
            self.complexity_levels = [StateComplexityLevel.BOOLEAN, StateComplexityLevel.NUMERICAL, 
                                    StateComplexityLevel.RELATIONAL, StateComplexityLevel.FULL]
            self.train_seeds = list(range(1, 51))
            self.dev_seeds = list(range(1, 26))
            self.test_seeds = list(range(1, 26))

def validate_state(state, complexity_level):
    """Validate that a state contains the expected fields for its complexity level"""
    if state is None:
        logger.logMessage("error", f"State is None in validate_state")
        return False
        
    expected_keys = {
        StateComplexityLevel.BOOLEAN: {'has_cookbook', 'in_kitchen', 'fridge_open', 'stove_on', 'holding_ingredient'},
        StateComplexityLevel.NUMERICAL: {'has_cookbook', 'in_kitchen', 'fridge_open', 'stove_on', 'holding_ingredient',
                                       'inventory_count', 'valid_actions_count'},
        StateComplexityLevel.RELATIONAL: {'has_cookbook', 'in_kitchen', 'fridge_open', 'stove_on', 'holding_ingredient',
                                        'inventory_count', 'valid_actions_count', 'locations'},
        StateComplexityLevel.FULL: {'has_cookbook', 'in_kitchen', 'fridge_open', 'stove_on', 'holding_ingredient',
                                   'inventory_count', 'valid_actions_count', 'locations', 'full_observation', 
                                   'full_inventory', 'full_look'}
    }
    
    if complexity_level not in expected_keys:
        logger.logMessage("error", f"Unknown complexity level: {complexity_level}")
        return False
        
    state_keys = set(state.keys())
    missing_keys = expected_keys[complexity_level] - state_keys
    if missing_keys:
        logger.logMessage("error", f"State missing required keys for {complexity_level}: {missing_keys}")
        return False
        
    return True

def compare_states(predicted_state, actual_state, complexity_level):
    """Compare predicted and actual states, return accuracy metrics"""
    if not validate_state(predicted_state, complexity_level) or not validate_state(actual_state, complexity_level):
        logger.logMessage("error", f"Cannot compare states: invalid state structure for complexity level {complexity_level}")
        return 0.0
        
    # Get the keys to compare based on complexity level
    keys_to_compare = {
        StateComplexityLevel.BOOLEAN: ['has_cookbook', 'in_kitchen', 'fridge_open', 'stove_on', 'holding_ingredient'],
        StateComplexityLevel.NUMERICAL: ['has_cookbook', 'in_kitchen', 'fridge_open', 'stove_on', 'holding_ingredient',
                                       'inventory_count', 'valid_actions_count'],
        StateComplexityLevel.RELATIONAL: ['has_cookbook', 'in_kitchen', 'fridge_open', 'stove_on', 'holding_ingredient',
                                        'inventory_count', 'valid_actions_count', 'locations'],
        StateComplexityLevel.FULL: ['has_cookbook', 'in_kitchen', 'fridge_open', 'stove_on', 'holding_ingredient',
                                   'inventory_count', 'valid_actions_count', 'locations', 'full_observation', 
                                   'full_inventory', 'full_look']
    }[complexity_level]
    
    correct_predictions = 0
    total_comparisons = 0
    
    # Log comparison details
    logger.logMessage("debug", f"Comparing states for complexity level {complexity_level}")
    logger.logMessage("debug", "Predicted state: " + json.dumps(predicted_state, indent=2))
    logger.logMessage("debug", "Actual state: " + json.dumps(actual_state, indent=2))
    
    for key in keys_to_compare:
        if key not in predicted_state or key not in actual_state:
            logger.logMessage("error", f"Missing key {key} in state comparison")
            continue
            
        if isinstance(predicted_state[key], dict) and isinstance(actual_state[key], dict):
            # For dictionaries (like locations), compare each sub-key
            pred_dict = predicted_state[key]
            actual_dict = actual_state[key]
            all_keys = set(pred_dict.keys()) | set(actual_dict.keys())
            for sub_key in all_keys:
                total_comparisons += 1
                if sub_key in pred_dict and sub_key in actual_dict:
                    if pred_dict[sub_key] == actual_dict[sub_key]:
                        correct_predictions += 1
                logger.logMessage("debug", f"Dict comparison - {key}.{sub_key}:")
                logger.logMessage("debug", f"  Predicted: {pred_dict.get(sub_key, 'MISSING')}")
                logger.logMessage("debug", f"  Actual: {actual_dict.get(sub_key, 'MISSING')}")
        else:
            # For simple values, direct comparison
            total_comparisons += 1
            if predicted_state[key] == actual_state[key]:
                correct_predictions += 1
            logger.logMessage("debug", f"Value comparison - {key}:")
            logger.logMessage("debug", f"  Predicted: {predicted_state[key]}")
            logger.logMessage("debug", f"  Actual: {actual_state[key]}")
                
    if total_comparisons == 0:
        logger.logMessage("error", "No valid comparisons made")
        return 0.0
        
    accuracy = correct_predictions / total_comparisons
    logger.logMessage("debug", f"Final accuracy: {accuracy} ({correct_predictions}/{total_comparisons})")
    return accuracy

def extract_state_representation(env, obs, infos, complexity_level):
    """Extract state representation at different complexity levels"""
    state = {}
    
    try:
        # Get valid actions to help understand state
        valid_actions = infos['validActions']
        
        if complexity_level == StateComplexityLevel.BOOLEAN:
            # Extract boolean states from observation text
            state['has_cookbook'] = 'cookbook' in infos['inventory'].lower()
            state['in_kitchen'] = 'kitchen' in infos['look'].lower()
            state['fridge_open'] = 'fridge that is open' in infos['look'].lower() or 'open fridge' in infos['look'].lower()
            state['stove_on'] = 'stove that is turned on' in infos['look'].lower()
            state['holding_ingredient'] = any(word in infos['inventory'].lower() for word in ['flour', 'sugar', 'egg', 'milk', 'potato', 'pepper', 'apple'])
            
        elif complexity_level == StateComplexityLevel.NUMERICAL:
            # Include boolean states plus numerical properties
            state.update(extract_state_representation(env, obs, infos, StateComplexityLevel.BOOLEAN))
            # Add numerical properties
            state['inventory_count'] = len([line for line in infos['inventory'].split('\n') if line.strip() and 'empty' not in line.lower()])
            state['valid_actions_count'] = len(valid_actions)
            
        elif complexity_level == StateComplexityLevel.RELATIONAL:
            # Include numerical states plus relationships
            state.update(extract_state_representation(env, obs, infos, StateComplexityLevel.NUMERICAL))
            # Add relationships
            state['locations'] = {}
            for action in valid_actions:
                if 'take' in action:
                    item = action.replace('take ', '')
                    state['locations'][item] = 'reachable'
                elif 'put' in action:
                    item = action.split(' in ')[0].replace('put ', '')
                    container = action.split(' in ')[1]
                    state['locations'][item] = f'can_put_in_{container}'
                    
        else:  # FULL
            # Include everything from relational plus full state
            state.update(extract_state_representation(env, obs, infos, StateComplexityLevel.RELATIONAL))
            # Add full observation and inventory
            state['full_observation'] = obs
            state['full_inventory'] = infos['inventory']
            state['full_look'] = infos['look']
            
        # Validate the extracted state
        if not validate_state(state, complexity_level):
            logger.logMessage("error", f"Invalid state extracted for {complexity_level}")
            return None
            
    except Exception as e:
        logger.logMessage("error", f"Error extracting state representation: {str(e)}")
        return None
        
    return state

def format_state_for_llm(state, complexity_level):
    """Format state dictionary into a string for LLM prompt"""
    return json.dumps(state, indent=2)

def generate_llm_prompt(current_state, action, complexity_level):
    """Generate prompt for LLM to predict next state"""
    prompt = "You are a world-class simulator for a cooking game environment. Given the current state and action, predict the next state.\n\n"
    prompt += "Current State:\n"
    prompt += "```\n"
    prompt += format_state_for_llm(current_state, complexity_level)
    prompt += "\n```\n\n"
    prompt += "Action taken: " + action + "\n\n"
    prompt += "IMPORTANT: You must respond with ONLY a valid JSON object between triple backticks (```). The JSON object must have the exact same structure as the input state, with no additional or missing fields.\n"
    prompt += "Example format of your response:\n"
    prompt += "```\n"
    prompt += format_state_for_llm(current_state, complexity_level)  # Show the exact structure expected
    prompt += "\n```\n"
    prompt += "Your response must be a single JSON object between triple backticks, with no additional text or explanation.\n"
    return prompt

def run_episode(env, config, complexity_level, seed):
    """Run a single episode with specified complexity level"""
    logger.logMessage("info", f"Starting episode with seed {seed} at complexity level {complexity_level}")
    
    # Initialize episode
    obs, infos = env.reset(gameFold="train", generateGoldPath=False, seed=seed)
    
    episode_accuracies = []
    
    for step in range(config.max_steps):
        # Get current state
        current_state = extract_state_representation(env, obs, infos, complexity_level)
        if current_state is None:
            logger.logMessage("error", f"Failed to extract current state at step {step}")
            continue
            
        # Select random action
        valid_actions = infos['validActions']
        if not valid_actions:
            logger.logMessage("warning", f"No valid actions available at step {step}")
            break
        action = random.choice(valid_actions)
        
        # Take action and get next state
        next_obs, _, _, next_infos = env.step(action)
        actual_next_state = extract_state_representation(env, next_obs, next_infos, complexity_level)
        if actual_next_state is None:
            logger.logMessage("error", f"Failed to extract next state at step {step}")
            continue
        
        # Get LLM prediction
        prompt = generate_llm_prompt(current_state, action, complexity_level)
        success, llm_response_text = llm_response(prompt, LLM_MODEL, temperature=0, max_tokens=1000)
        
        if not success:
            logger.logMessage("error", f"LLM call failed: {llm_response_text}")
            continue
            
        # Log the full LLM response for debugging
        logger.logMessage("debug", f"LLM Response for step {step}:\n{llm_response_text}")
            
        # Extract prediction from LLM response
        try:
            # Find the JSON response between ```
            response_lines = llm_response_text.split('\n')
            json_lines = []
            in_json = False
            for line in response_lines:
                if line.strip() == '```':
                    in_json = not in_json
                    continue
                if in_json:
                    json_lines.append(line)
            
            if not json_lines:
                logger.logMessage("error", "No JSON found in LLM response")
                continue
                
            json_str = '\n'.join(json_lines)
            logger.logMessage("debug", f"Extracted JSON:\n{json_str}")
            
            predicted_next_state = json.loads(json_str)
                
        except json.JSONDecodeError as e:
            logger.logMessage("error", f"Failed to parse LLM response as JSON: {str(e)}")
            continue
            
        # Compare prediction to actual
        accuracy = compare_states(predicted_next_state, actual_next_state, complexity_level)
        episode_accuracies.append(accuracy)
            
        # Log detailed comparison
        logger.logMessage("debug", f"Step {step} comparison:")
        logger.logMessage("debug", f"Action: {action}")
        logger.logMessage("debug", f"Predicted state: {json.dumps(predicted_next_state, indent=2)}")
        logger.logMessage("debug", f"Actual state: {json.dumps(actual_next_state, indent=2)}")
        logger.logMessage("debug", f"Accuracy: {accuracy}")
        
        # Update for next step
        obs, infos = next_obs, next_infos
        
    return episode_accuracies

def run_experiment(config):
    """Run the full experiment"""
    logger.logMessage("info", f"Starting experiment in {config.pilot_mode} mode")
    
    # Initialize environment
    env = TextWorldExpressEnv(envStepLimit=config.max_steps)
    env.load(gameName="cookingworld", gameParams="")
    
    # Store results for each complexity level
    results = {level: [] for level in config.complexity_levels}
    
    # Run episodes for each complexity level
    for complexity_level in config.complexity_levels:
        logger.logMessage("info", f"Testing complexity level: {complexity_level}")
        
        for seed in config.train_seeds:
            episode_accuracies = run_episode(env, config, complexity_level, seed)
            if episode_accuracies:  # Only add if we got valid accuracies
                results[complexity_level].extend(episode_accuracies)
            
    return results

def analyze_results(results, config):
    """Analyze experimental results"""
    logger.logMessage("info", "Analyzing results")
    
    analysis = {
        "pilot_mode": config.pilot_mode,
        "complexity_levels": config.complexity_levels,
        "mean_accuracies": {},
        "statistical_tests": [],
        "raw_accuracies": results
    }
    
    # Calculate mean accuracies
    for level in results:
        if results[level]:
            mean_accuracy = np.mean(results[level])
            analysis["mean_accuracies"][level] = mean_accuracy
            logger.logMessage("info", f"Mean accuracy for {level}: {mean_accuracy}")
            
    # Perform statistical comparisons between levels
    if len(config.complexity_levels) > 1:
        for i, level1 in enumerate(config.complexity_levels[:-1]):
            for level2 in config.complexity_levels[i+1:]:
                if results[level1] and results[level2]:  # Only compare if both have data
                    # Log the data being compared
                    logger.logMessage("debug", f"Comparing {level1} vs {level2}:")
                    logger.logMessage("debug", f"  {level1} scores: {results[level1]}")
                    logger.logMessage("debug", f"  {level2} scores: {results[level2]}")
                    
                    # Ensure arrays are equal length for comparison
                    min_len = min(len(results[level1]), len(results[level2]))
                    scores1 = results[level1][:min_len]
                    scores2 = results[level2][:min_len]
                    
                    # Note: We treat the more complex state as experimental and simpler state as baseline
                    difference_scores, mean1, mean2 = generate_difference_scores_parallel_arrays(
                        scores1, scores2  # simpler state is baseline
                    )
                    stats = bootstrap_resampling(difference_scores, mean1, mean2)
                    analysis["statistical_tests"].append({
                        "level1": level1,
                        "level2": level2,
                        "stats": stats
                    })
                    logger.logMessage("info", f"Statistical comparison {level1} vs {level2}:\n{json.dumps(stats, indent=2)}")
    
    return analysis

def generate_plots(analysis):
    """Generate visualization plots"""
    logger.logMessage("info", "Generating plots")
    
    # Only create plots if we have data
    if not analysis["mean_accuracies"]:
        logger.logMessage("warning", "No data available for plotting")
        return
    
    # Create accuracy by complexity plot
    plt.figure(figsize=(10, 6))
    levels = list(analysis["mean_accuracies"].keys())
    accuracies = [analysis["mean_accuracies"][level] for level in levels]
    
    plt.plot(range(len(levels)), accuracies, 'bo-')
    plt.xticks(range(len(levels)), levels, rotation=45)
    plt.ylabel('Mean Accuracy')
    plt.xlabel('Complexity Level')
    plt.title('Accuracy by State Complexity Level')
    plt.tight_layout()
    
    # Save plot
    if not os.path.exists('to_save'):
        os.makedirs('to_save')
    plt.savefig('to_save/accuracy_by_complexity.pdf')
    plt.close()

def save_results(analysis):
    """Save results to JSON file"""
    try:
        with open('results.json', 'w') as f:
            json.dump(analysis, f, indent=4)
        logger.logMessage("info", "Results saved successfully to results.json")
    except Exception as e:
        logger.logMessage("error", f"Error saving results to file: {str(e)}")

def main():
    # Initialize configuration based on pilot mode
    config = ExperimentConfig(PILOT_MODE)
    
    # Run experiment
    results = run_experiment(config)
    
    # Analyze results
    analysis = analyze_results(results, config)
    
    # Generate plots
    generate_plots(analysis)
    
    # Save results
    save_results(analysis)
    
    logger.logMessage("info", "Experiment completed successfully")

if __name__ == "__main__":
    main()