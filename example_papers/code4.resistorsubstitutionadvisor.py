import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import json
import time
import os
from typing import List, Dict, Tuple
import math
from itertools import combinations_with_replacement
from experiment_common_library import Logger, llm_response

# Global configuration
PILOT_MODE = 'PILOT'  # Changed to PILOT mode
logger = Logger()

# Create to_save directory if it doesn't exist
os.makedirs('to_save', exist_ok=True)

class ResistorSeries:
    def __init__(self):
        # E12 series base values
        self.E12 = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82]
        # E24 series adds intermediate values
        self.E24 = [10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30, 33, 36, 39, 43, 47, 51, 56, 62, 68, 75, 82, 91]
        
        # Generate full series with multipliers
        self.full_E12 = self._generate_full_series(self.E12)
        self.full_E24 = self._generate_full_series(self.E24)
        
    def _generate_full_series(self, base_values: List[int]) -> List[float]:
        full_series = []
        for n in range(6):  # 10^0 to 10^5
            multiplier = 10 ** n
            full_series.extend([x * multiplier for x in base_values])
        return sorted(full_series)

def calculate_parallel_resistance(r1: float, r2: float) -> float:
    return (r1 * r2) / (r1 + r2)

def calculate_series_resistance(r1: float, r2: float) -> float:
    return r1 + r2

def calculate_total_resistance(components: List[float], connections: List[str]) -> float:
    if len(components) == 1:
        return components[0]
    
    current_value = components[0]
    for i in range(1, len(components)):
        if connections[i-1] == 'series':
            current_value = calculate_series_resistance(current_value, components[i])
        else:  # parallel
            current_value = calculate_parallel_resistance(current_value, components[i])
    return current_value

def calculate_percent_error(target: float, actual: float) -> float:
    return abs((actual - target) / target) * 100

class BaselineSimple:
    def __init__(self, available_values: List[float]):
        self.available_values = available_values
    
    def find_closest_single(self, target: float) -> Dict:
        closest = min(self.available_values, key=lambda x: abs(x - target))
        return {
            'components': [closest],
            'connections': [],
            'actual_resistance': closest
        }
    
    def find_closest_series(self, target: float) -> Dict:
        best_error = float('inf')
        best_result = None
        
        for r1 in self.available_values:
            for r2 in self.available_values:
                total = r1 + r2
                error = abs(total - target)
                if error < best_error:
                    best_error = error
                    best_result = {
                        'components': [r1, r2],
                        'connections': ['series'],
                        'actual_resistance': total
                    }
        
        # Compare with single resistor solution
        single = self.find_closest_single(target)
        if abs(single['actual_resistance'] - target) < best_error:
            return single
            
        return best_result

class BaselineMathematical:
    def __init__(self, available_values: List[float], max_components: int):
        self.available_values = available_values
        self.max_components = max_components
    
    def find_optimal_combination(self, target: float) -> Dict:
        best_error = float('inf')
        best_result = None
        
        # Try different numbers of components
        for n in range(1, self.max_components + 1):
            # Get all possible combinations of n resistors
            for combo in combinations_with_replacement(self.available_values, n):
                # Try different connection patterns
                connection_patterns = self._generate_connection_patterns(n)
                for pattern in connection_patterns:
                    total = calculate_total_resistance(list(combo), pattern)
                    error = abs(total - target)
                    
                    if error < best_error:
                        best_error = error
                        best_result = {
                            'components': list(combo),
                            'connections': pattern,
                            'actual_resistance': total
                        }
        
        return best_result
    
    def _generate_connection_patterns(self, n: int) -> List[List[str]]:
        if n <= 1:
            return [[]]
        patterns = []
        for i in range(2 ** (n-1)):
            pattern = []
            for j in range(n-1):
                if (i >> j) & 1:
                    pattern.append('parallel')
                else:
                    pattern.append('series')
            patterns.append(pattern)
        return patterns

class LLMAdvisor:
    def __init__(self, available_values: List[float], max_components: int):
        self.available_values = available_values
        self.max_components = max_components
    
    def get_suggestion(self, target: float) -> Dict:
        # Enhanced prompt with better guidance about magnitude and parallel combinations
        prompt = f"Given a target resistance of {target} ohms, suggest combinations of up to {self.max_components} standard resistors from the following series ({[float(x) for x in self.available_values]}) connected in series and/or parallel to approximate this value.\n\n"
        prompt += "IMPORTANT GUIDELINES:\n"
        prompt += f"1. Choose resistors with values close to the target order of magnitude:\n"
        prompt += f"   - For target {target} ohms, focus on values between {target/10} and {target*10} ohms\n"
        prompt += "   - AVOID using unnecessarily large resistors\n\n"
        prompt += "2. Connection types and formulas:\n"
        prompt += "   - Series: Total = R1 + R2\n"
        prompt += "   - Parallel: Total = 1 / (1/R1 + 1/R2)\n"
        prompt += "   Note: Parallel combinations always result in a total less than the smallest component\n\n"
        prompt += "3. Examples for different magnitudes:\n"
        prompt += '   Target = 150 ohms:\n'
        prompt += '   {"components": [100, 47], "connections": ["series"]}  # 147 ohms\n'
        prompt += '   {"components": [220, 470], "connections": ["parallel"]}  # 151 ohms\n\n'
        prompt += '   Target = 1000 ohms:\n'
        prompt += '   {"components": [680, 330], "connections": ["series"]}  # 1010 ohms\n\n'
        prompt += "Your response must be a valid JSON object with exactly this format:\n"
        prompt += "{\n"
        prompt += '    "components": [value1, value2],  # List of resistance values\n'
        prompt += '    "connections": ["series"]        # List of connection types between adjacent components\n'
        prompt += "}\n\n"
        prompt += "Place your JSON response between triple backticks (```). Do not include any other text."

        logger.logMessage("info", f"Sending prompt to LLM for target resistance: {target} ohms")
        logger.logMessage("debug", f"Full prompt: {prompt}")
        
        success, response = llm_response(prompt, "gpt-4o-mini", temperature=0, max_tokens=200)
        
        if not success:
            logger.logMessage("error", f"LLM call failed: {response}")
            return None
            
        logger.logMessage("debug", f"Raw LLM response: {response}")
        
        try:
            # Extract JSON from response using codeblocks
            from experiment_common_library import find_codeblocks
            codeblocks = find_codeblocks(response)
            
            if not codeblocks:
                logger.logMessage("error", "No codeblocks found in LLM response")
                return None
                
            # Join the lines and remove any comments
            json_str = '\n'.join(codeblocks[0])
            json_str = '\n'.join([line.split('#')[0].strip() for line in json_str.split('\n')])
            
            # Validate JSON structure
            suggestion = json.loads(json_str)
            logger.logMessage("debug", f"Parsed suggestion: {suggestion}")
            
            # Validate the suggestion structure
            if not isinstance(suggestion, dict):
                logger.logMessage("error", "LLM response is not a dictionary")
                return None
                
            if 'components' not in suggestion or 'connections' not in suggestion:
                logger.logMessage("error", "Missing required keys in LLM response")
                return None
                
            if not isinstance(suggestion['components'], list) or not isinstance(suggestion['connections'], list):
                logger.logMessage("error", "Components or connections is not a list")
                return None
                
            if len(suggestion['components']) > 1 and len(suggestion['connections']) != len(suggestion['components']) - 1:
                logger.logMessage("error", "Invalid number of connections for components")
                return None
                
            # Calculate actual resistance
            actual_resistance = calculate_total_resistance(
                suggestion['components'],
                suggestion['connections']
            )
            
            suggestion['actual_resistance'] = actual_resistance
            return suggestion
            
        except Exception as e:
            logger.logMessage("error", f"Error processing LLM response: {str(e)}")
            return None

def plot_results(df: pd.DataFrame, pilot_mode: str):
    plt.style.use('seaborn-v0_8')
    
    # Error distribution by method
    plt.figure(figsize=(10, 6))
    for method in df['method'].unique():
        method_data = df[df['method'] == method]['percent_error']
        # Filter out infinite values
        method_data = method_data[~np.isinf(method_data)]
        if len(method_data) > 0:  # Only plot if we have valid data
            sns.histplot(data=method_data, bins=30, alpha=0.5, label=method)
    plt.xlabel('Percent Error')
    plt.ylabel('Count')
    plt.title('Error Distribution by Method')
    plt.legend()
    plt.savefig('to_save/error_distribution.pdf')
    plt.close()
    
    # Success rate vs tolerance level
    tolerances = [1, 5, 10]
    success_rates = []
    for method in df['method'].unique():
        rates = []
        method_data = df[df['method'] == method]
        for tol in tolerances:
            col = f'within_{tol}_percent'
            if col in method_data.columns:
                rate = (method_data[col].mean() * 100)
                rates.append(float(rate))
        if len(rates) == len(tolerances):  # Only add if we have all tolerance levels
            success_rates.append({'method': method, 'rates': rates})
    
    if success_rates:  # Only plot if we have valid data
        plt.figure(figsize=(10, 6))
        for data in success_rates:
            plt.plot(tolerances, data['rates'], marker='o', label=data['method'])
        plt.xlabel('Tolerance (%)')
        plt.ylabel('Success Rate (%)')
        plt.title('Success Rate vs Tolerance Level')
        plt.legend()
        plt.savefig('to_save/success_rates.pdf')
        plt.close()

def perform_statistical_analysis(df: pd.DataFrame):
    try:
        from experiment_common_library import generate_difference_scores_dict, bootstrap_resampling
        
        # Prepare data for bootstrap analysis
        methods = sorted(df['method'].unique())
        baseline_method = 'Simple'
        
        logger.logMessage("info", f"Performing statistical analysis comparing methods: {methods}")
        
        for experimental_method in methods:
            if experimental_method == baseline_method:
                continue
                
            # Prepare data
            comparison_data = []
            for target in df['target_value'].unique():
                baseline_data = df[(df['method'] == baseline_method) & 
                                 (df['target_value'] == target)]['percent_error']
                exp_data = df[(df['method'] == experimental_method) & 
                             (df['target_value'] == target)]['percent_error']
                
                if len(baseline_data) > 0 and len(exp_data) > 0:
                    baseline_error = float(baseline_data.iloc[0])
                    exp_error = float(exp_data.iloc[0])
                    
                    # Skip infinite values
                    if not np.isinf(baseline_error) and not np.isinf(exp_error):
                        comparison_data.append({
                            'baseline_score': -baseline_error,  # Negative because lower error is better
                            'experimental_score': -exp_error
                        })
            
            if len(comparison_data) > 0:
                logger.logMessage("info", f"Comparing {experimental_method} vs {baseline_method} with {len(comparison_data)} valid comparison points")
                
                # Perform bootstrap analysis
                difference_scores, mean_baseline, mean_experimental = generate_difference_scores_dict(
                    comparison_data, 'baseline_score', 'experimental_score'
                )
                
                results = bootstrap_resampling(difference_scores, mean_baseline, mean_experimental)
                
                logger.logMessage("info", f"Bootstrap analysis results for {experimental_method} vs {baseline_method}:")
                logger.logMessage("info", json.dumps(results, indent=2))
                
                # Log interpretation
                p_value = results.get('p_value', 1.0)
                if p_value < 0.05:
                    logger.logMessage("info", f"{experimental_method} is significantly different from {baseline_method} (p < 0.05)")
                else:
                    logger.logMessage("info", f"No significant difference between {experimental_method} and {baseline_method} (p >= 0.05)")
            else:
                logger.logMessage("warning", f"No valid comparison data for {experimental_method} vs {baseline_method}")
    
    except Exception as e:
        logger.logMessage("error", f"Error in statistical analysis: {str(e)}")

def run_experiment(pilot_mode: str):
    # Initialize components
    resistor_series = ResistorSeries()
    
    # Configure experiment based on pilot mode
    if pilot_mode == 'MINI_PILOT':
        num_values = 5
        max_resistors = 2
        available_values = resistor_series.full_E12
        runs_per_value = 1
    elif pilot_mode == 'PILOT':
        num_values = 50  # Changed from 20 to 50 for follow-on experiment
        max_resistors = 3
        available_values = resistor_series.full_E24
        runs_per_value = 3
    else:  # FULL_EXPERIMENT
        num_values = 100
        max_resistors = 3
        available_values = resistor_series.full_E24
        runs_per_value = 5
    
    logger.logMessage("info", f"Starting experiment in {pilot_mode} mode with {num_values} values, {max_resistors} max resistors, and {runs_per_value} runs per value")
    
    # Initialize methods
    llm_advisor = LLMAdvisor(available_values, max_resistors)
    baseline_simple = BaselineSimple(available_values)
    baseline_math = BaselineMathematical(available_values, max_resistors)
    
    # Generate random target values
    np.random.seed(42)  # For reproducibility
    exp_range = np.log10(np.array([10, 1e6]))  # 10Ω to 1MΩ
    target_values = np.power(10, np.random.uniform(exp_range[0], exp_range[1], num_values))
    
    # Initialize results DataFrame
    results = []
    
    # Run experiment
    for target in target_values:
        logger.logMessage("info", f"Processing target value: {target} ohms")
        
        for run in range(runs_per_value):
            logger.logMessage("info", f"Run {run + 1}/{runs_per_value}")
            
            # Test each method
            for method_name, method in [
                ("LLM", llm_advisor),
                ("Simple", baseline_simple),
                ("Mathematical", baseline_math)
            ]:
                start_time = time.time()
                
                try:
                    if method_name == "Simple":
                        suggestion = method.find_closest_series(target)
                    elif method_name == "Mathematical":
                        suggestion = method.find_optimal_combination(target)
                    else:  # LLM
                        suggestion = method.get_suggestion(target)
                    
                    if suggestion is None:
                        logger.logMessage("error", f"Method {method_name} failed for target {target} ohms")
                        # Record failure result
                        result = {
                            'target_value': float(target),
                            'method': method_name,
                            'suggested_components': [],
                            'connection_type': [],
                            'actual_resistance': 0.0,
                            'percent_error': float('inf'),
                            'within_1_percent': False,
                            'within_5_percent': False,
                            'within_10_percent': False,
                            'num_components': 0,
                            'computation_time': float(time.time() - start_time)
                        }
                    else:
                        computation_time = time.time() - start_time
                        
                        # Calculate metrics
                        percent_error = calculate_percent_error(target, suggestion['actual_resistance'])
                        
                        # Record results with explicit type conversion
                        result = {
                            'target_value': float(target),
                            'method': method_name,
                            'suggested_components': suggestion['components'],
                            'connection_type': suggestion['connections'],
                            'actual_resistance': float(suggestion['actual_resistance']),
                            'percent_error': float(percent_error),
                            'within_1_percent': bool(percent_error <= 1),
                            'within_5_percent': bool(percent_error <= 5),
                            'within_10_percent': bool(percent_error <= 10),
                            'num_components': int(len(suggestion['components'])),
                            'computation_time': float(computation_time)
                        }
                    
                    results.append(result)
                    logger.logMessage("debug", f"Result for {method_name}: {json.dumps(result)}")
                    
                except Exception as e:
                    logger.logMessage("error", f"Error running {method_name}: {str(e)}")
                    continue
    
    # Convert results to DataFrame
    df = pd.DataFrame(results)
    
    # Save results
    with open('results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Generate plots
    plot_results(df, pilot_mode)
    
    # Perform statistical analysis
    perform_statistical_analysis(df)
    
    # Log summary statistics
    for method in df['method'].unique():
        method_data = df[df['method'] == method]
        logger.logMessage("info", f"\nSummary for {method}:")
        logger.logMessage("info", f"Mean percent error: {method_data['percent_error'].mean():.2f}%")
        logger.logMessage("info", f"Median percent error: {method_data['percent_error'].median():.2f}%")
        logger.logMessage("info", f"Success rates:")
        logger.logMessage("info", f"  Within 1%: {(method_data['within_1_percent'].mean() * 100):.1f}%")
        logger.logMessage("info", f"  Within 5%: {(method_data['within_5_percent'].mean() * 100):.1f}%")
        logger.logMessage("info", f"  Within 10%: {(method_data['within_10_percent'].mean() * 100):.1f}%")
        logger.logMessage("info", f"Mean computation time: {method_data['computation_time'].mean():.3f} seconds")

def main():
    logger.logMessage("info", f"Starting experiment in {PILOT_MODE} mode")
    run_experiment(PILOT_MODE)
    logger.logMessage("info", "Experiment completed")

if __name__ == "__main__":
    main()