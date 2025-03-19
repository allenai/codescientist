import os
import json
import random
import numpy as np
from sklearn.metrics import roc_curve, auc
import matplotlib.pyplot as plt
import textworld_express as twx
from textworld_express import TextWorldExpressEnv

from experiment_common_library import Logger, llm_response, find_codeblocks
from experiment_common_library import generate_difference_scores_dict, bootstrap_resampling

# Global configuration
PILOT_MODE = "PILOT"  # Options: "MINI_PILOT", "PILOT", "FULL_EXPERIMENT"
logger = Logger()

# Configure experiment parameters based on pilot mode
def get_experiment_config():
    if PILOT_MODE == "MINI_PILOT":
        return {
            "num_episodes": 3,
            "max_steps": 10,
            "game_fold": "train"
        }
    elif PILOT_MODE == "PILOT":
        return {
            "num_episodes": 50,  # Updated from 20 to 50 per follow-on instructions
            "max_steps": 25,
            "game_fold": "train"
        }
    else:  # FULL_EXPERIMENT
        return {
            "num_episodes": 200,
            "max_steps": 50,
            "game_fold": "train"  # Would be balanced across sets in full experiment
        }

def setup_environment():
    """Initialize and configure the TextWorldExpress environment"""
    logger.logMessage("info", "Setting up TextWorldExpress environment...")
    
    env = TextWorldExpressEnv(envStepLimit=get_experiment_config()["max_steps"])
    
    # Configure simple CookingWorld environment
    game_params = "numLocations=3, numIngredients=2, numDistractorItems=2, includeDoors=0, limitInventorySize=0"
    env.load(gameName="cookingworld", gameParams=game_params)
    
    logger.logMessage("info", f"Environment setup complete with params: {game_params}")
    return env

def format_state_prediction_prompt(obs1, obs2, action):
    """Format the prompt for state prediction"""
    prompt = f"""Context:
Previous Observation 1: {obs1}
Previous Observation 2: {obs2}
Current Action: {action}

Task:
1. Predict the next observation
2. For each property that changed, rate your confidence (0-100)

Provide your response in the following format between code blocks (```):
{{
    "predicted_observation": "string",
    "confidence_scores": [
        {{"property": "string", "change": "string", "confidence": number}}
    ]
}}"""
    return prompt

def get_llm_prediction(obs1, obs2, action):
    """Get LLM prediction and confidence scores"""
    logger.logMessage("info", f"Getting LLM prediction for action: {action}")
    
    prompt = format_state_prediction_prompt(obs1, obs2, action)
    success, response = llm_response(prompt, "gpt-4o-mini", temperature=0, max_tokens=500)
    
    if not success:
        logger.logMessage("error", f"LLM call failed: {response}")
        return None, None
    
    # Extract JSON from response
    codeblocks = find_codeblocks(response)
    if not codeblocks:
        logger.logMessage("error", "No codeblocks found in LLM response")
        return None, None
        
    try:
        prediction_data = json.loads("\n".join(codeblocks[0]))
        # Normalize confidence scores to 0-1 scale
        for score in prediction_data["confidence_scores"]:
            score["confidence"] = score["confidence"] / 100.0
        logger.logMessage("debug", f"Parsed prediction data: {json.dumps(prediction_data)}")
        return prediction_data["predicted_observation"], prediction_data["confidence_scores"]
    except Exception as e:
        logger.logMessage("error", f"Failed to parse LLM response: {str(e)}")
        return None, None

def score_prediction_accuracy(predicted_obs, actual_obs):
    """Use LLM to score prediction accuracy"""
    prompt = f"""Compare the predicted observation with the actual observation and score the accuracy of each property change.

Predicted: {predicted_obs}
Actual: {actual_obs}

For each property that changed, provide an accuracy score between 0 and 1.
Respond in JSON format between code blocks (```):
{{
    "accuracy_scores": [
        {{"property": "string", "accuracy": number}}
    ]
}}"""

    success, response = llm_response(prompt, "gpt-4o-mini", temperature=0, max_tokens=500)
    
    if not success:
        logger.logMessage("error", f"LLM scoring failed: {response}")
        return None
        
    codeblocks = find_codeblocks(response)
    if not codeblocks:
        logger.logMessage("error", "No codeblocks found in LLM scoring response")
        return None
        
    try:
        accuracy_data = json.loads("\n".join(codeblocks[0]))
        logger.logMessage("debug", f"Parsed accuracy data: {json.dumps(accuracy_data)}")
        return accuracy_data["accuracy_scores"]
    except Exception as e:
        logger.logMessage("error", f"Failed to parse accuracy scores: {str(e)}")
        return None

def calculate_correlation(confidences, accuracies):
    """Calculate correlation between confidence and accuracy scores with error checking"""
    if not confidences or not accuracies:
        logger.logMessage("warning", "Empty confidence or accuracy arrays")
        return None
        
    if len(confidences) != len(accuracies):
        logger.logMessage("error", "Confidence and accuracy arrays have different lengths")
        return None
    
    if len(confidences) < 2:
        logger.logMessage("warning", "Not enough data points to calculate correlation")
        return None
        
    # Check for valid data
    if not all(isinstance(x, (int, float)) for x in confidences + accuracies):
        logger.logMessage("error", "Non-numeric values found in confidence or accuracy scores")
        return None
        
    # Check for zero variance
    if len(set(confidences)) == 1 or len(set(accuracies)) == 1:
        logger.logMessage("warning", "Zero variance in confidence or accuracy scores")
        return None
        
    try:
        correlation = np.corrcoef(confidences, accuracies)[0, 1]
        if np.isnan(correlation):
            logger.logMessage("warning", "Correlation calculation resulted in NaN")
            return None
        logger.logMessage("debug", f"Correlation calculation successful: {correlation}")
        return correlation
    except Exception as e:
        logger.logMessage("error", f"Error calculating correlation: {str(e)}")
        return None

def save_results(results_data):
    """Save results to results.json"""
    try:
        with open("results.json", "w") as f:
            json.dump(results_data, f, indent=4)
        logger.logMessage("info", "Results saved to results.json")
        return True
    except Exception as e:
        logger.logMessage("error", f"Failed to save results: {str(e)}")
        return False

def generate_plots(episode_data):
    """Generate visualization plots"""
    logger.logMessage("info", "Generating visualization plots...")
    
    # Create to_save directory if it doesn't exist
    if not os.path.exists("to_save"):
        os.makedirs("to_save")
    
    # Extract confidence and accuracy scores
    confidences = []
    accuracies = []
    for episode in episode_data:
        for step in episode["steps"]:
            for conf_score in step["confidence_scores"]:
                for acc_score in step["accuracy_scores"]:
                    if conf_score["property"] == acc_score["property"]:
                        confidences.append(conf_score["confidence"])
                        accuracies.append(acc_score["accuracy"])
    
    if not confidences or not accuracies:
        logger.logMessage("warning", "No confidence-accuracy pairs found for plotting")
        return
    
    logger.logMessage("debug", f"Number of data points for plotting: {len(confidences)}")
    
    # Scatter plot
    plt.figure(figsize=(10, 6))
    plt.scatter(confidences, accuracies, alpha=0.5)
    plt.xlabel("Confidence")
    plt.ylabel("Accuracy")
    plt.title("LLM Confidence vs Accuracy")
    plt.savefig("to_save/confidence_accuracy_scatter.pdf")
    plt.close()
    
    # ROC curve
    try:
        fpr, tpr, _ = roc_curve([1 if a >= 0.5 else 0 for a in accuracies], confidences)
        roc_auc = auc(fpr, tpr)
        
        plt.figure(figsize=(10, 6))
        plt.plot(fpr, tpr, label=f'ROC curve (AUC = {roc_auc:.2f})')
        plt.plot([0, 1], [0, 1], 'k--')
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROC Curve for Confidence Threshold')
        plt.legend(loc="lower right")
        plt.savefig("to_save/roc_curve.pdf")
        plt.close()
    except Exception as e:
        logger.logMessage("error", f"Error generating ROC curve: {str(e)}")

def run_experiment():
    """Main experiment execution"""
    logger.logMessage("info", f"Starting experiment in {PILOT_MODE} mode")
    
    config = get_experiment_config()
    env = setup_environment()
    
    # Store all episode data
    all_episode_data = []
    
    # Run episodes
    for episode_idx in range(config["num_episodes"]):
        logger.logMessage("info", f"Starting episode {episode_idx + 1}/{config['num_episodes']}")
        
        episode_data = {"episode_idx": episode_idx, "steps": []}
        obs, infos = env.reset(gameFold=config["game_fold"], generateGoldPath=False)
        
        # Store last two observations for context
        obs_history = [obs, obs]
        
        for step_idx in range(config["max_steps"]):
            # Get valid actions and choose one randomly
            valid_actions = infos["validActions"]
            action = random.choice(valid_actions)
            
            # Get LLM prediction before taking action
            predicted_obs, confidence_scores = get_llm_prediction(obs_history[-2], obs_history[-1], action)
            
            if predicted_obs is None:
                logger.logMessage("error", f"Failed to get prediction for step {step_idx}, skipping step")
                continue
                
            # Take action in environment
            obs, _, _, infos = env.step(action)
            
            # Score prediction accuracy
            accuracy_scores = score_prediction_accuracy(predicted_obs, obs)
            
            if accuracy_scores is None:
                logger.logMessage("error", f"Failed to score prediction accuracy for step {step_idx}, skipping step")
                continue
            
            # Store step data
            step_data = {
                "step_idx": step_idx,
                "action": action,
                "predicted_obs": predicted_obs,
                "actual_obs": obs,
                "confidence_scores": confidence_scores,
                "accuracy_scores": accuracy_scores
            }
            episode_data["steps"].append(step_data)
            
            # Update observation history
            obs_history = obs_history[1:] + [obs]
            
            if infos["done"]:
                break
        
        all_episode_data.append(episode_data)
        
        # Calculate episode-level statistics
        episode_confidences = []
        episode_accuracies = []
        for step in episode_data["steps"]:
            for conf_score in step["confidence_scores"]:
                for acc_score in step["accuracy_scores"]:
                    if conf_score["property"] == acc_score["property"]:
                        episode_confidences.append(conf_score["confidence"])
                        episode_accuracies.append(acc_score["accuracy"])
        
        correlation = calculate_correlation(episode_confidences, episode_accuracies)
        if correlation is not None:
            logger.logMessage("info", f"Episode {episode_idx} confidence-accuracy correlation: {correlation:.3f}")
        logger.logMessage("debug", f"Episode {episode_idx} data points: {len(episode_confidences)}")
    
    # Generate visualizations
    generate_plots(all_episode_data)
    
    # Save results
    results = {
        "pilot_mode": PILOT_MODE,
        "config": config,
        "episode_data": all_episode_data
    }
    save_success = save_results(results)
    
    if not save_success:
        logger.logMessage("error", "Failed to save results")
    else:
        logger.logMessage("info", "Experiment completed successfully")

if __name__ == "__main__":
    try:
        run_experiment()
    except Exception as e:
        logger.logMessage("error", f"Experiment failed with error: {str(e)}")
        raise