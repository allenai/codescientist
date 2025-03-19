import os
import json
import time
import random
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from scipy import stats
matplotlib.use('Agg')  # Required for headless environments

from textworld_express import TextWorldExpressEnv
from experiment_common_library import Logger, llm_response, find_codeblocks
from experiment_common_library import generate_difference_scores_dict, bootstrap_resampling

# Global logger
logger = Logger()

# Global experiment mode
PILOT_MODE = 'PILOT'  # Options: 'MINI_PILOT', 'PILOT', 'FULL_EXPERIMENT'

# Configure experiment parameters based on pilot mode
def get_experiment_params():
    if PILOT_MODE == 'MINI_PILOT':
        return {'num_games': 2, 'actions_per_game': 5}
    elif PILOT_MODE == 'PILOT':
        return {'num_games': 50, 'actions_per_game': 10}  # Changed from 5 to 50 games
    else:  # FULL_EXPERIMENT
        return {'num_games': 20, 'actions_per_game': 25}

class ConfidencePredictor:
    def __init__(self):
        self.env = TextWorldExpressEnv()
        self.results = []
        
    def initialize_environment(self):
        """Initialize the CookingWorld environment with simplified parameters"""
        logger.logMessage("info", "Initializing CookingWorld environment...")
        
        # Set fixed random seed
        random.seed(42)
        np.random.seed(42)
        
        # Initialize with simplified parameters
        game_params = "numLocations=3, numIngredients=2, numDistractorItems=2, includeDoors=0"
        self.env.load(gameName="cookingworld", gameParams=game_params)
        logger.logMessage("info", f"Environment initialized with params: {game_params}")

    def collect_action_data(self, num_games, actions_per_game):
        """Collect action data from multiple game episodes"""
        logger.logMessage("info", f"Starting data collection: {num_games} games, {actions_per_game} actions per game")
        
        collected_data = []
        
        for game_id in range(num_games):
            logger.logMessage("info", f"Starting game {game_id + 1}/{num_games}")
            
            # Initialize new game
            obs, infos = self.env.reset(gameFold="train", generateGoldPath=False, seed=None)
            logger.logMessage("debug", f"Game {game_id} initial observation: {obs}")
            
            for step in range(actions_per_game):
                # Store pre-action state
                valid_actions = infos['validActions']
                if not valid_actions:
                    logger.logMessage("warning", f"No valid actions available at step {step}")
                    break
                    
                # Sample random action
                action = random.choice(valid_actions)
                
                # Store pre-action state
                pre_action_state = {
                    'observation': infos['observation'],
                    'inventory': infos['inventory'],
                    'valid_actions': valid_actions
                }
                
                # Execute action
                obs, _, _, infos = self.env.step(action)
                
                # Store the data point
                data_point = {
                    'game_id': game_id,
                    'step': step,
                    'pre_action_state': pre_action_state,
                    'action': action,
                    'post_action_observation': obs
                }
                collected_data.append(data_point)
                
                logger.logMessage("debug", f"Game {game_id}, Step {step}: Action '{action}' executed")
                logger.logMessage("debug", f"Resulting observation: {obs}")
                
        logger.logMessage("info", f"Data collection complete. Collected {len(collected_data)} action samples")
        return collected_data

    def get_llm_prediction(self, observation, inventory, action):
        """Query LLM for action prediction and confidence"""
        prompt = f"Given the following game state in a text-based cooking game:\n\nObservation: {observation}\nInventory: {inventory}\nProposed Action: {action}\n\nPredict whether this action will succeed or fail, and provide your confidence.\n\nProvide your response in JSON format between code blocks (```), with these keys:\n- success: true/false (whether you think the action will succeed)\n- confidence: (0.0-1.0) how confident you are in your prediction\n- rationale: (brief explanation for your prediction)"
        
        logger.logMessage("debug", f"Sending prediction prompt to LLM:\n{prompt}")
        
        success, response = llm_response(prompt, "gpt-4o-mini", temperature=0)
        
        if not success:
            logger.logMessage("error", f"LLM call failed: {response}")
            return None
            
        logger.logMessage("debug", f"Raw LLM response:\n{response}")
            
        # Extract JSON from response
        codeblocks = find_codeblocks(response)
        if not codeblocks:
            logger.logMessage("error", "No codeblocks found in LLM response")
            return None
            
        try:
            prediction = json.loads("\n".join(codeblocks[0]))
            logger.logMessage("debug", f"Parsed prediction: {json.dumps(prediction, indent=2)}")
            return prediction
        except json.JSONDecodeError as e:
            logger.logMessage("error", f"Failed to parse LLM response as JSON: {str(e)}")
            return None

    def determine_action_success(self, action, observation):
        """Use LLM to determine if action succeeded"""
        prompt = f"Did the following action succeed or fail? Respond with only 'success' or 'failure'.\n\nAction: {action}\nResult: {observation}"
        
        logger.logMessage("debug", f"Sending success determination prompt to LLM:\n{prompt}")
        
        success, response = llm_response(prompt, "gpt-4o-mini", temperature=0)
        
        if not success:
            logger.logMessage("error", f"LLM success determination failed: {response}")
            return None
            
        response = response.strip().lower()
        logger.logMessage("debug", f"Success determination response: {response}")
        
        if response not in ["success", "failure"]:
            logger.logMessage("error", f"Invalid success determination response: {response}")
            return None
            
        return response == "success"

    def generate_baseline_predictions(self, num_predictions):
        """Generate baseline predictions using different strategies"""
        return {
            'random_prediction': [random.choice([True, False]) for _ in range(num_predictions)],
            'random_confidence': [random.random() for _ in range(num_predictions)],
            'constant_confidence': [0.5 for _ in range(num_predictions)]
        }

    def calculate_metrics(self, predictions, actual_outcomes, confidences=None, game_ids=None):
        """Calculate prediction metrics"""
        if not predictions or not actual_outcomes:
            logger.logMessage("error", "Empty predictions or outcomes list")
            return 0.0, None
            
        accuracy = sum(p == a for p, a in zip(predictions, actual_outcomes)) / len(predictions)
        logger.logMessage("info", f"Overall accuracy: {accuracy:.3f} (from {len(predictions)} predictions)")
        
        # Calculate per-game accuracy if game IDs are provided
        if game_ids is not None:
            unique_games = sorted(list(set(game_ids)))
            for game_id in unique_games:
                game_predictions = [p for i, p in enumerate(predictions) if game_ids[i] == game_id]
                game_outcomes = [o for i, o in enumerate(actual_outcomes) if game_ids[i] == game_id]
                game_accuracy = sum(p == a for p, a in zip(game_predictions, game_outcomes)) / len(game_predictions)
                logger.logMessage("info", f"Game {game_id} accuracy: {game_accuracy:.3f} (from {len(game_predictions)} predictions)")
        
        # Calculate confidence correlation if confidences are provided
        correlation = None
        if confidences is not None:
            binary_outcomes = [1 if p == a else 0 for p, a in zip(predictions, actual_outcomes)]
            correlation, p_value = stats.pearsonr(confidences, binary_outcomes)
            logger.logMessage("info", f"Confidence-accuracy correlation: {correlation:.3f} (p={p_value:.3f})")
            
        return accuracy, correlation

    def plot_confidence_vs_accuracy(self, confidences, accuracies, filename):
        """Generate scatter plot of confidence vs accuracy"""
        if not confidences or not accuracies:
            logger.logMessage("error", "Empty confidences or accuracies list, skipping plot")
            return
            
        plt.figure(figsize=(10, 6))
        plt.scatter(confidences, accuracies, alpha=0.5)
        plt.xlabel('Confidence')
        plt.ylabel('Accuracy')
        plt.title('Confidence vs Accuracy')
        plt.savefig(os.path.join('to_save', filename))
        plt.close()
        logger.logMessage("info", f"Generated confidence vs accuracy plot: {filename}")

    def plot_average_confidence(self, correct_confidences, incorrect_confidences, filename):
        """Generate bar plot of average confidence for correct/incorrect predictions"""
        if not correct_confidences and not incorrect_confidences:
            logger.logMessage("error", "Empty confidence lists, skipping plot")
            return
            
        plt.figure(figsize=(8, 6))
        means = []
        if correct_confidences:
            means.append(np.mean(correct_confidences))
        if incorrect_confidences:
            means.append(np.mean(incorrect_confidences))
            
        plt.bar(['Correct', 'Incorrect'][:len(means)], means)
        plt.ylabel('Average Confidence')
        plt.title('Average Confidence by Prediction Outcome')
        plt.savefig(os.path.join('to_save', filename))
        plt.close()
        logger.logMessage("info", f"Generated average confidence plot: {filename}")

    def run_experiment(self):
        """Main experiment execution"""
        logger.logMessage("info", f"Starting experiment in {PILOT_MODE} mode")
        
        # Create to_save directory if it doesn't exist
        os.makedirs('to_save', exist_ok=True)
        
        # Get experiment parameters
        params = get_experiment_params()
        
        # Initialize environment
        self.initialize_environment()
        
        # Collect action data
        action_data = self.collect_action_data(params['num_games'], params['actions_per_game'])
        
        # Process each action
        for data_point in action_data:
            # Get LLM prediction
            prediction = self.get_llm_prediction(
                data_point['pre_action_state']['observation'],
                data_point['pre_action_state']['inventory'],
                data_point['action']
            )
            
            if prediction is None:
                continue
                
            # Determine actual outcome
            actual_outcome = self.determine_action_success(
                data_point['action'],
                data_point['post_action_observation']
            )
            
            if actual_outcome is None:
                continue
                
            # Generate baseline predictions
            baselines = self.generate_baseline_predictions(1)
            
            # Store results
            result = {
                'game_id': data_point['game_id'],
                'step': data_point['step'],
                'pre_action_observation': data_point['pre_action_state']['observation'],
                'action': data_point['action'],
                'post_action_observation': data_point['post_action_observation'],
                'llm_prediction': prediction['success'],
                'llm_confidence': prediction['confidence'],
                'llm_rationale': prediction['rationale'],
                'actual_outcome': actual_outcome,
                'baseline_random_prediction': baselines['random_prediction'][0],
                'baseline_random_confidence': baselines['random_confidence'][0],
                'baseline_constant_confidence': baselines['constant_confidence'][0]
            }
            
            self.results.append(result)
            logger.logMessage("debug", f"Processed result: {json.dumps(result, indent=2)}")
        
        # Save results
        with open('results.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        
        # Calculate metrics
        llm_predictions = [r['llm_prediction'] for r in self.results]
        actual_outcomes = [r['actual_outcome'] for r in self.results]
        llm_confidences = [r['llm_confidence'] for r in self.results]
        game_ids = [r['game_id'] for r in self.results]
        
        llm_accuracy, confidence_correlation = self.calculate_metrics(
            llm_predictions, actual_outcomes, llm_confidences, game_ids
        )
        
        # Generate plots
        self.plot_confidence_vs_accuracy(
            llm_confidences,
            [1 if p == a else 0 for p, a in zip(llm_predictions, actual_outcomes)],
            'confidence_vs_accuracy.pdf'
        )
        
        # Separate confidences for correct/incorrect predictions
        correct_confidences = [conf for conf, pred, act in zip(llm_confidences, llm_predictions, actual_outcomes) if pred == act]
        incorrect_confidences = [conf for conf, pred, act in zip(llm_confidences, llm_predictions, actual_outcomes) if pred != act]
        
        self.plot_average_confidence(correct_confidences, incorrect_confidences, 'average_confidence.pdf')
        
        # Statistical analysis
        experimental_data = [{'experimental': 1 if p == a else 0, 'baseline': 0.5} 
                           for p, a in zip(llm_predictions, actual_outcomes)]
        
        difference_scores, mean_baseline, mean_experimental = generate_difference_scores_dict(
            experimental_data, 'baseline', 'experimental'
        )
        
        bootstrap_results = bootstrap_resampling(
            difference_scores, mean_baseline, mean_experimental
        )
        
        logger.logMessage("info", f"Experiment complete. Results saved to results.json")
        logger.logMessage("info", f"LLM Accuracy: {llm_accuracy}")
        logger.logMessage("info", f"Confidence-Accuracy Correlation: {confidence_correlation}")
        logger.logMessage("info", f"Statistical Analysis Results:\n{json.dumps(bootstrap_results, indent=2)}")

def main():
    predictor = ConfidencePredictor()
    predictor.run_experiment()

if __name__ == "__main__":
    main()