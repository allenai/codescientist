import os
import json
import time
import random
import re
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

from experiment_common_library import Logger, llm_response

# Create global logger
logger = Logger()

# Experiment settings
PILOT_MODE = "FULL_EXPERIMENT"  # Options: "MINI_PILOT", "PILOT", "FULL_EXPERIMENT"

# Configure experiment parameters based on pilot mode
def get_experiment_params():
    if PILOT_MODE == "MINI_PILOT":
        return {
            "num_games": 2,
            "generations_per_game": 1
        }
    elif PILOT_MODE == "PILOT":
        return {
            "num_games": 5,
            "generations_per_game": 3
        }
    else:  # FULL_EXPERIMENT
        return {
            "num_games": 20,  # Updated to 20 games as per follow-on requirements
            "generations_per_game": 3
        }

# Game generation prompts
SINGLE_STAGE_PROMPT = '''Create a simple text adventure game as a Python class with the following specifications:

1. 3x3 grid world with player starting at (1,1)
2. 2-3 items randomly placed
3. Required mechanics:
   - Movement: north/south/east/west methods
   - Inventory: take/drop methods
   - Scoring: +1 per collected item
   - Win condition: collect all items

Format the response as a complete Python class. Example structure:

class TextGame:
    def __init__(self):
        # Initialize grid, player position, items, inventory, score
        pass
    
    def move_north(self):
        # Move player north if possible
        pass
    
    # Include other required methods
'''

TWO_STAGE_PROMPT_1 = '''Create the first stage of a text adventure game as a Python class with the following specifications:

1. 3x3 grid world with player starting at (1,1)
2. 2-3 items randomly placed
3. Required mechanics for this stage:
   - Movement: north/south/east/west methods
   - Inventory: take/drop methods

Format the response as a complete Python class. Example structure:

class TextGame:
    def __init__(self):
        # Initialize grid, player position, items, inventory
        pass
    
    def move_north(self):
        # Move player north if possible
        pass
    
    # Include other required methods
'''

TWO_STAGE_PROMPT_2 = '''Add scoring and win condition mechanics to the following game class:
{game_code}

Add:
1. Scoring: +1 per collected item
2. Win condition: collect all items

Modify the class to include these features while preserving existing functionality.
'''

def evaluate_game_code(code):
    """Evaluate generated game code for required mechanics and syntax."""
    logger.logMessage("info", "Evaluating game code...")
    
    # Initialize evaluation results
    evaluation = {
        "execution_success": False,
        "num_syntax_errors": 0,
        "mechanics_complete": False,
        "mechanics": {
            "movement": False,
            "inventory": False,
            "scoring": False,
            "win": False
        }
    }
    
    # Check for required mechanics using regex
    movement_pattern = r"def move_(north|south|east|west)"
    inventory_pattern = r"def (take|drop)"
    scoring_pattern = r"score\s*[=+]"
    win_pattern = r"(win|victory|game_over|check_win)"
    
    evaluation["mechanics"]["movement"] = bool(re.search(movement_pattern, code))
    evaluation["mechanics"]["inventory"] = bool(re.search(inventory_pattern, code))
    evaluation["mechanics"]["scoring"] = bool(re.search(scoring_pattern, code))
    evaluation["mechanics"]["win"] = bool(re.search(win_pattern, code))
    
    # Check if all mechanics are present
    evaluation["mechanics_complete"] = all(evaluation["mechanics"].values())
    
    # Try to execute the code to check for syntax errors
    try:
        compile(code, '<string>', 'exec')
        evaluation["execution_success"] = True
        evaluation["num_syntax_errors"] = 0
    except SyntaxError as e:
        evaluation["num_syntax_errors"] = 1
        logger.logMessage("error", f"Syntax error in game code: {str(e)}")
    
    logger.logMessage("info", f"Evaluation results: {json.dumps(evaluation, indent=2)}")
    return evaluation

def generate_single_stage_game():
    """Generate a complete game using single-stage approach."""
    logger.logMessage("info", "Generating single-stage game...")
    
    start_time = time.time()
    success, response = llm_response(SINGLE_STAGE_PROMPT, "gpt-4o-mini", temperature=0.7, max_tokens=1000)
    generation_time = time.time() - start_time
    
    if not success:
        logger.logMessage("error", f"Failed to generate single-stage game: {response}")
        return None, None, generation_time
    
    # Extract code from response
    code_blocks = re.findall(r'```python\n(.*?)```', response, re.DOTALL)
    if not code_blocks:
        code_blocks = re.findall(r'```\n(.*?)```', response, re.DOTALL)
    
    if not code_blocks:
        logger.logMessage("error", "No code block found in response")
        return None, None, generation_time
    
    game_code = code_blocks[0].strip()
    evaluation = evaluate_game_code(game_code)
    
    return game_code, evaluation, generation_time

def generate_two_stage_game():
    """Generate a game using two-stage approach."""
    logger.logMessage("info", "Generating two-stage game...")
    
    # Stage 1: Basic mechanics
    start_time = time.time()
    success, response1 = llm_response(TWO_STAGE_PROMPT_1, "gpt-4o-mini", temperature=0.7, max_tokens=1000)
    
    if not success:
        logger.logMessage("error", f"Failed to generate first stage: {response1}")
        return None, None, time.time() - start_time
    
    # Extract code from first stage
    code_blocks = re.findall(r'```python\n(.*?)```', response1, re.DOTALL)
    if not code_blocks:
        code_blocks = re.findall(r'```\n(.*?)```', response1, re.DOTALL)
    
    if not code_blocks:
        logger.logMessage("error", "No code block found in first stage response")
        return None, None, time.time() - start_time
    
    stage1_code = code_blocks[0].strip()
    
    # Stage 2: Add scoring and win conditions
    stage2_prompt = TWO_STAGE_PROMPT_2.format(game_code=stage1_code)
    success, response2 = llm_response(stage2_prompt, "gpt-4o-mini", temperature=0.7, max_tokens=1000)
    generation_time = time.time() - start_time
    
    if not success:
        logger.logMessage("error", f"Failed to generate second stage: {response2}")
        return None, None, generation_time
    
    # Extract code from second stage
    code_blocks = re.findall(r'```python\n(.*?)```', response2, re.DOTALL)
    if not code_blocks:
        code_blocks = re.findall(r'```\n(.*?)```', response2, re.DOTALL)
    
    if not code_blocks:
        logger.logMessage("error", "No code block found in second stage response")
        return None, None, generation_time
    
    final_code = code_blocks[0].strip()
    evaluation = evaluate_game_code(final_code)
    
    return final_code, evaluation, generation_time

def save_results(results):
    """Save results to JSON file."""
    with open('results.json', 'w') as f:
        json.dump(results, f, indent=2)

def create_plots(results_df):
    """Create comparison plots between single-stage and two-stage approaches."""
    plt.style.use('seaborn-v0_8')  # Updated to use non-deprecated style
    
    # Create plots directory
    os.makedirs('to_save', exist_ok=True)
    
    # Success Rate Plot
    plt.figure(figsize=(10, 6))
    success_rates = results_df.groupby('generation_method')['execution_success'].mean()
    success_rates.plot(kind='bar')
    plt.title('Success Rate by Generation Method')
    plt.ylabel('Success Rate')
    plt.tight_layout()
    plt.savefig('to_save/success_rates.pdf')
    plt.close()
    
    # Mechanics Completion Plot
    plt.figure(figsize=(10, 6))
    mechanics_rates = results_df.groupby('generation_method')['mechanics_complete'].mean()
    mechanics_rates.plot(kind='bar')
    plt.title('Mechanics Completion Rate by Generation Method')
    plt.ylabel('Completion Rate')
    plt.tight_layout()
    plt.savefig('to_save/mechanics_rates.pdf')
    plt.close()
    
    # Generation Time Plot
    plt.figure(figsize=(10, 6))
    results_df.boxplot(column='generation_time_sec', by='generation_method')
    plt.title('Generation Time by Method')
    plt.suptitle('')  # Remove automatic suptitle
    plt.ylabel('Time (seconds)')
    plt.tight_layout()
    plt.savefig('to_save/generation_times.pdf')
    plt.close()

def main():
    logger.logMessage("info", f"Starting experiment in {PILOT_MODE} mode")
    
    # Get experiment parameters
    params = get_experiment_params()
    logger.logMessage("info", f"Experiment parameters: {json.dumps(params, indent=2)}")
    
    # Initialize results storage
    results = []
    
    # Run experiment
    for game_id in range(params["num_games"]):
        logger.logMessage("info", f"Generating game {game_id + 1}/{params['num_games']}")
        
        for generation in range(params["generations_per_game"]):
            # Single-stage generation
            single_code, single_eval, single_time = generate_single_stage_game()
            if single_eval:
                results.append({
                    "game_id": f"game_{game_id}_{generation}",
                    "generation_method": "single-stage",
                    "execution_success": single_eval["execution_success"],
                    "num_syntax_errors": single_eval["num_syntax_errors"],
                    "mechanics_complete": single_eval["mechanics_complete"],
                    "generation_time_sec": single_time
                })
            
            # Two-stage generation
            two_stage_code, two_stage_eval, two_stage_time = generate_two_stage_game()
            if two_stage_eval:
                results.append({
                    "game_id": f"game_{game_id}_{generation}",
                    "generation_method": "two-stage",
                    "execution_success": two_stage_eval["execution_success"],
                    "num_syntax_errors": two_stage_eval["num_syntax_errors"],
                    "mechanics_complete": two_stage_eval["mechanics_complete"],
                    "generation_time_sec": two_stage_time
                })
            
            # Save intermediate results
            save_results(results)
    
    # Convert results to DataFrame for analysis
    results_df = pd.DataFrame(results)
    
    # Calculate summary statistics
    summary_stats = {
        "single_stage": {
            "success_rate": results_df[results_df["generation_method"] == "single-stage"]["execution_success"].mean(),
            "mechanics_complete_rate": results_df[results_df["generation_method"] == "single-stage"]["mechanics_complete"].mean(),
            "avg_generation_time": results_df[results_df["generation_method"] == "single-stage"]["generation_time_sec"].mean()
        },
        "two_stage": {
            "success_rate": results_df[results_df["generation_method"] == "two-stage"]["execution_success"].mean(),
            "mechanics_complete_rate": results_df[results_df["generation_method"] == "two-stage"]["mechanics_complete"].mean(),
            "avg_generation_time": results_df[results_df["generation_method"] == "two-stage"]["generation_time_sec"].mean()
        }
    }
    
    # Log summary statistics
    logger.logMessage("info", f"Summary statistics: {json.dumps(summary_stats, indent=2)}")
    
    # Create plots
    create_plots(results_df)
    
    # Save final results
    save_results({
        "raw_results": results,
        "summary_stats": summary_stats
    })
    
    logger.logMessage("info", "Experiment completed successfully")

if __name__ == "__main__":
    main()