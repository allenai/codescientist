import os
import json
import time
import random
from datetime import datetime
import statistics
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Required for headless environments
import matplotlib.pyplot as plt

from discoveryworld.DiscoveryWorldAPI import DiscoveryWorldAPI
from experiment_common_library import Logger, llm_response, run_dot_graphviz, bootstrap_resampling, generate_difference_scores_parallel_arrays

# Create global logger
logger = Logger()

# Set the experiment mode
PILOT_MODE = "PILOT"  # Options: "MINI_PILOT", "PILOT", "FULL_EXPERIMENT"

# Configure experiment parameters based on pilot mode
if PILOT_MODE == "MINI_PILOT":
    EPISODES_PER_DIFFICULTY = 2
    MAX_STEPS_PER_EPISODE = 20
    SEEDS = range(0, 2)
    DIFFICULTIES = ["Easy"]
elif PILOT_MODE == "PILOT":
    EPISODES_PER_DIFFICULTY = 50  # Modified from 10 to 50 per follow-on requirements
    MAX_STEPS_PER_EPISODE = 50
    SEEDS = range(0, 50)  # Modified from range(0,10) to range(0,50)
    DIFFICULTIES = ["Easy"]
else:  # FULL_EXPERIMENT
    EPISODES_PER_DIFFICULTY = 50
    MAX_STEPS_PER_EPISODE = 100
    SEEDS = range(0, 50)
    DIFFICULTIES = ["Easy", "Normal", "Challenge"]

class BaselineReActAgent:
    def __init__(self, thread_id=1):
        self.thread_id = thread_id
        self.step_counter = 0
        self.last_actions = []
        self.stuck_counter = 0
        self.has_meter = False
        self.measured_animals = set()
        self.protein_levels = {}
        self.last_location = None
        self.visited_locations = set()
        
    def think(self, observation):
        """Think about what to do next based on current observation"""
        # First priority: Get the proteomics meter if we don't have it
        if not self.has_meter:
            for obj in observation["ui"]["accessibleEnvironmentObjects"]:
                if "proteomics meter" in obj["name"].lower():
                    return {"action": "PICKUP", "arg1": obj["uuid"], "arg2": None}
        
        # Second priority: Measure unmeasured animals if we have the meter
        if self.has_meter:
            for obj in observation["ui"]["accessibleEnvironmentObjects"]:
                if (any(animal in obj["name"].lower() for animal in ["prismatic beast", "vortisquid", "animaplant"]) and 
                    obj["uuid"] not in self.measured_animals and
                    "statue" not in obj["name"].lower()):
                    meter_uuid = next((obj["uuid"] for obj in observation["ui"]["inventoryObjects"] if "proteomics meter" in obj["name"].lower()), None)
                    if meter_uuid:
                        return {"action": "USE", "arg1": meter_uuid, "arg2": obj["uuid"]}
        
        # If nothing else to do, explore
        valid_directions = observation["ui"]["agentLocation"]["directions_you_can_move"]
        if valid_directions:
            # Avoid getting stuck by preferring unexplored directions
            recent_moves = self.last_actions[-3:] if self.last_actions else []
            available_directions = [d for d in valid_directions if d not in recent_moves]
            if available_directions:
                chosen_direction = random.choice(available_directions)
            else:
                chosen_direction = random.choice(valid_directions)
            self.last_actions.append(chosen_direction)
            return {"action": "MOVE_DIRECTION", "arg1": chosen_direction, "arg2": None}
        return None

    def update(self, observation, action):
        """Update agent's state based on observation and action"""
        self.step_counter += 1
        
        # Update inventory tracking
        inventory = set(obj["uuid"] for obj in observation["ui"]["inventoryObjects"])
        self.has_meter = any("proteomics meter" in obj["name"].lower() for obj in observation["ui"]["inventoryObjects"])
        
        # Track location
        current_location = (
            observation["ui"]["agentLocation"]["x"],
            observation["ui"]["agentLocation"]["y"]
        )
        if current_location == self.last_location:
            self.stuck_counter += 1
        else:
            self.stuck_counter = 0
            self.visited_locations.add(current_location)
        self.last_location = current_location
        
        # Update protein measurements
        if action and action["action"] == "USE" and self.has_meter:
            target_obj = next((obj for obj in observation["ui"]["accessibleEnvironmentObjects"] if obj["uuid"] == action["arg2"]), None)
            if target_obj and "statue" not in target_obj["name"].lower():
                message = observation["ui"]["lastActionMessage"].lower()
                if "protein a:" in message and "protein b:" in message:
                    try:
                        protein_a = float(message.split("protein a:")[1].split()[0])
                        protein_b = float(message.split("protein b:")[1].split()[0])
                        self.protein_levels[target_obj["name"]] = {
                            "protein_a": protein_a,
                            "protein_b": protein_b
                        }
                        self.measured_animals.add(target_obj["uuid"])
                        logger.logMessage("info", f"Measured protein levels for {target_obj['name']}: A={protein_a}, B={protein_b}")
                    except Exception as e:
                        logger.logMessage("error", f"Failed to parse protein levels: {str(e)}")

class KnowledgeGraphAgent:
    def __init__(self, thread_id=1):
        self.graph = "digraph G {\n"
        self.nodes = set()
        self.edges = set()
        self.step_counter = 0
        self.thread_id = thread_id
        self.last_actions = []
        self.stuck_counter = 0
        self.inventory = set()
        self.has_meter = False
        self.last_location = None
        self.object_uuids = {}
        self.measured_animals = set()
        self.protein_levels = {}
        self.last_movement_attempts = []
        self.visited_locations = set()
        self.stuck_threshold = 3
        self.exploration_timeout = 5
        self.exploration_steps = 0
        self.measurement_attempts = {}
        self.max_measurement_attempts = 3
        self.successful_measurements = set()
        self.hypotheses = set()
        self.measured_statues = set()
        self.outliers = set()
        self.animal_locations = {}
        
        if not os.path.exists("to_save"):
            os.makedirs("to_save")

    def add_node(self, node_name, node_type):
        """Add a node to the graph with appropriate styling"""
        if node_name not in self.nodes:
            if node_type == "object":
                self.graph += f'    "{node_name}" [shape=box];\n'
            elif node_type == "property":
                self.graph += f'    "{node_name}" [shape=ellipse];\n'
            elif node_type == "hypothesis":
                self.graph += f'    "{node_name}" [shape=diamond];\n'
            elif node_type == "measurement":
                self.graph += f'    "{node_name}" [shape=hexagon];\n'
            self.nodes.add(node_name)
            logger.logMessage("info", f"Added {node_type} node: {node_name}")

    def add_edge(self, from_node, to_node, relation):
        """Add an edge to the graph"""
        edge = f'    "{from_node}" -> "{to_node}" [label="{relation}"];\n'
        if edge not in self.edges:
            self.graph += edge
            self.edges.add(edge)
            logger.logMessage("info", f"Added edge: {from_node} -> {to_node} ({relation})")

    def save_graph(self):
        """Save the current state of the graph"""
        graph_str = self.graph + "}\n"
        dot_filename = f"to_save/graph_step_{self.step_counter}.dot"
        with open(dot_filename, "w") as f:
            f.write(graph_str)
        pdf_filename = f"to_save/graph_step_{self.step_counter}.pdf"
        run_dot_graphviz(dot_filename, pdf_filename)
        logger.logMessage("info", f"Saved graph (nodes: {len(self.nodes)}, edges: {len(self.edges)})")

    def analyze_protein_levels(self):
        """Analyze protein levels to identify outliers using z-scores"""
        if len(self.protein_levels) < 2:
            return None

        # Calculate statistics for both proteins
        protein_a_values = [data["protein_a"] for data in self.protein_levels.values()]
        protein_b_values = [data["protein_b"] for data in self.protein_levels.values()]

        try:
            protein_a_mean = statistics.mean(protein_a_values)
            protein_a_stdev = statistics.stdev(protein_a_values) if len(protein_a_values) > 1 else 0
            protein_b_mean = statistics.mean(protein_b_values)
            protein_b_stdev = statistics.stdev(protein_b_values) if len(protein_b_values) > 1 else 0

            logger.logMessage("info", f"Protein A stats - mean: {protein_a_mean:.2f}, stdev: {protein_a_stdev:.2f}")
            logger.logMessage("info", f"Protein B stats - mean: {protein_b_mean:.2f}, stdev: {protein_b_stdev:.2f}")

            # Look for outliers (>2 standard deviations from mean)
            outliers = []
            for animal, data in self.protein_levels.items():
                a_zscore = (data["protein_a"] - protein_a_mean) / protein_a_stdev if protein_a_stdev > 0 else 0
                b_zscore = (data["protein_b"] - protein_b_mean) / protein_b_stdev if protein_b_stdev > 0 else 0
                
                logger.logMessage("info", f"Z-scores for {animal} - Protein A: {a_zscore:.2f}, Protein B: {b_zscore:.2f}")
                
                if abs(a_zscore) > 2 or abs(b_zscore) > 2:
                    outliers.append(animal)
                    self.outliers.add(animal)
                    hypothesis = f"{animal}_is_outlier"
                    if hypothesis not in self.hypotheses:
                        self.hypotheses.add(hypothesis)
                        self.add_node(hypothesis, "hypothesis")
                        self.add_edge(animal, hypothesis, "supports")
                        
                        # Add specific protein level nodes and evidence
                        if abs(a_zscore) > 2:
                            protein_node = f"protein_a_outlier_{data['protein_a']:.2f}"
                            self.add_node(protein_node, "property")
                            self.add_edge(hypothesis, protein_node, "supported_by")
                            logger.logMessage("info", f"Added protein A outlier evidence for {animal}")
                        
                        if abs(b_zscore) > 2:
                            protein_node = f"protein_b_outlier_{data['protein_b']:.2f}"
                            self.add_node(protein_node, "property")
                            self.add_edge(hypothesis, protein_node, "supported_by")
                            logger.logMessage("info", f"Added protein B outlier evidence for {animal}")
                        
                        logger.logMessage("info", f"Generated hypothesis: {animal} is an outlier")

            return outliers
        except Exception as e:
            logger.logMessage("error", f"Error analyzing protein levels: {str(e)}")
            return None

    def get_unmeasured_animal(self, observation):
        """Find an unmeasured animal in the current observation"""
        for obj in observation["ui"]["accessibleEnvironmentObjects"]:
            if (any(animal in obj["name"].lower() for animal in ["prismatic beast", "vortisquid", "animaplant"]) and 
                obj["uuid"] not in self.successful_measurements and
                (obj["uuid"] not in self.measurement_attempts or 
                 self.measurement_attempts[obj["uuid"]] < self.max_measurement_attempts) and
                "statue" not in obj["name"].lower()):
                return obj
        return None

    def get_exploration_action(self, observation):
        """Get an action to explore when stuck"""
        if not self.has_meter:
            for obj in observation["ui"]["accessibleEnvironmentObjects"]:
                if "proteomics meter" in obj["name"].lower():
                    logger.logMessage("info", "Found proteomics meter - attempting pickup")
                    return {"action": "PICKUP", "arg1": obj["uuid"], "arg2": None}
        
        if self.has_meter:
            unmeasured_animal = self.get_unmeasured_animal(observation)
            if unmeasured_animal:
                meter_uuid = next((obj["uuid"] for obj in observation["ui"]["inventoryObjects"] if "proteomics meter" in obj["name"].lower()), None)
                if meter_uuid:
                    logger.logMessage("info", f"Attempting to measure {unmeasured_animal['name']}")
                    return {"action": "USE", "arg1": meter_uuid, "arg2": unmeasured_animal["uuid"]}
        
        # Update animal locations from nearby objects
        for direction, objects in observation["ui"]["nearbyObjects"]["objects"].items():
            for obj in objects:
                if any(animal in obj["name"].lower() for animal in ["prismatic beast", "vortisquid", "animaplant"]):
                    self.animal_locations[obj["uuid"]] = direction
        
        # If we know of unmeasured animals in a specific direction, prefer that direction
        for uuid, direction in self.animal_locations.items():
            if uuid not in self.successful_measurements:
                valid_directions = observation["ui"]["agentLocation"]["directions_you_can_move"]
                if direction in valid_directions:
                    logger.logMessage("info", f"Moving {direction} towards unmeasured animal")
                    return {"action": "MOVE_DIRECTION", "arg1": direction, "arg2": None}
        
        # Otherwise, explore systematically
        valid_directions = observation["ui"]["agentLocation"]["directions_you_can_move"]
        if not valid_directions:
            return None
        
        self.exploration_steps += 1
        
        # Calculate scores for each direction based on exploration history
        direction_scores = {}
        for direction in valid_directions:
            score = 1.0  # Base score
            
            # Penalize recently visited directions
            if direction in self.last_movement_attempts[-3:]:
                score -= 0.5
            
            # Penalize directions that lead to visited locations
            current_loc = (
                observation["ui"]["agentLocation"]["x"],
                observation["ui"]["agentLocation"]["y"]
            )
            
            if direction == "north":
                new_loc = (current_loc[0], current_loc[1] - 1)
            elif direction == "south":
                new_loc = (current_loc[0], current_loc[1] + 1)
            elif direction == "east":
                new_loc = (current_loc[0] + 1, current_loc[1])
            else:  # west
                new_loc = (current_loc[0] - 1, current_loc[1])
                
            if new_loc in self.visited_locations:
                score -= 0.3
                
            direction_scores[direction] = score
        
        # Choose the direction with the highest score
        best_score = max(direction_scores.values())
        best_directions = [d for d, s in direction_scores.items() if s == best_score]
        chosen_direction = random.choice(best_directions)
        
        self.last_movement_attempts.append(chosen_direction)
        if len(self.last_movement_attempts) > 5:
            self.last_movement_attempts.pop(0)
        
        logger.logMessage("info", f"Exploring in direction: {chosen_direction}")
        return {"action": "MOVE_DIRECTION", "arg1": chosen_direction, "arg2": None}

    def think(self, observation):
        """Analyze current graph and decide next action"""
        logger.logMessage("info", f"Thinking at step {self.step_counter}")
        
        # First priority: Get proteomics meter
        if not self.has_meter:
            for obj in observation["ui"]["accessibleEnvironmentObjects"]:
                if "proteomics meter" in obj["name"].lower():
                    logger.logMessage("info", "Found proteomics meter - attempting pickup")
                    return {"action": "PICKUP", "arg1": obj["uuid"], "arg2": None}
        
        # Second priority: Check if we've found an outlier
        if len(self.protein_levels) >= 2:
            outliers = self.analyze_protein_levels()
            if outliers:
                logger.logMessage("info", f"Found outliers: {outliers}")
                # If we've found outliers and measured all accessible animals, we're done
                if not self.get_unmeasured_animal(observation):
                    logger.logMessage("info", "Found outliers and measured all accessible animals")
                    return None
        
        # Third priority: Measure unmeasured animals
        if self.has_meter:
            unmeasured_animal = self.get_unmeasured_animal(observation)
            if unmeasured_animal:
                meter_uuid = next((obj["uuid"] for obj in observation["ui"]["inventoryObjects"] if "proteomics meter" in obj["name"].lower()), None)
                if meter_uuid:
                    logger.logMessage("info", f"Attempting to measure {unmeasured_animal['name']}")
                    return {"action": "USE", "arg1": meter_uuid, "arg2": unmeasured_animal["uuid"]}
        
        # If nothing else to do, explore
        return self.get_exploration_action(observation)

    def update(self, observation, last_action=None):
        """Update knowledge graph based on new observation"""
        self.step_counter += 1
        self.extract_objects_and_properties(observation)
        
        if last_action:
            self.update_protein_levels(observation, last_action)
            
        self.save_graph()

    def extract_objects_and_properties(self, observation):
        """Extract objects and their properties from an observation"""
        logger.logMessage("info", f"Extracting objects and properties from observation at step {self.step_counter}")
        
        # Update inventory and meter status
        self.inventory = set(obj["uuid"] for obj in observation["ui"]["inventoryObjects"])
        self.has_meter = any("proteomics meter" in obj["name"].lower() for obj in observation["ui"]["inventoryObjects"])
        if self.has_meter:
            logger.logMessage("info", "Agent has acquired proteomics meter")
        
        # Update location tracking
        current_location = (
            observation["ui"]["agentLocation"]["x"],
            observation["ui"]["agentLocation"]["y"]
        )
        if current_location == self.last_location:
            self.stuck_counter += 1
        else:
            self.stuck_counter = 0
            self.visited_locations.add(current_location)
        self.last_location = current_location
        
        # Extract objects and their properties
        for obj in observation["ui"]["inventoryObjects"] + observation["ui"]["accessibleEnvironmentObjects"]:
            obj_name = obj["name"].lower()
            obj_uuid = obj["uuid"]
            self.object_uuids[obj_name] = obj_uuid
            
            self.add_node(obj_name, "object")
            
            if obj["description"]:
                desc_node = f"property_{obj['description']}"
                self.add_node(desc_node, "property")
                self.add_edge(obj_name, desc_node, "has_description")

    def update_protein_levels(self, observation, action):
        """Update protein levels based on measurement results"""
        if action["action"] == "USE" and any(obj["uuid"] == action["arg1"] and "proteomics meter" in obj["name"].lower() for obj in observation["ui"]["inventoryObjects"]):
            target_obj = next((obj for obj in observation["ui"]["accessibleEnvironmentObjects"] if obj["uuid"] == action["arg2"]), None)
            if target_obj:
                if "statue" in target_obj["name"].lower():
                    self.measured_statues.add(target_obj["uuid"])
                    return
                
                if target_obj["uuid"] not in self.measurement_attempts:
                    self.measurement_attempts[target_obj["uuid"]] = 0
                self.measurement_attempts[target_obj["uuid"]] += 1
                
                message = observation["ui"]["lastActionMessage"].lower()
                logger.logMessage("info", f"Attempting to parse protein levels from: {message}")
                
                try:
                    if "protein a:" in message and "protein b:" in message:
                        protein_a = float(message.split("protein a:")[1].split()[0])
                        protein_b = float(message.split("protein b:")[1].split()[0])
                        
                        self.protein_levels[target_obj["name"]] = {
                            "protein_a": protein_a,
                            "protein_b": protein_b
                        }
                        self.measured_animals.add(target_obj["uuid"])
                        self.successful_measurements.add(target_obj["uuid"])
                        
                        # Add measurement to knowledge graph
                        measurement_node = f"measurement_{target_obj['name']}_{self.step_counter}"
                        self.add_node(measurement_node, "measurement")
                        self.add_edge(target_obj["name"], measurement_node, "measured_at")
                        
                        protein_a_node = f"protein_a_{protein_a:.2f}"
                        protein_b_node = f"protein_b_{protein_b:.2f}"
                        self.add_node(protein_a_node, "property")
                        self.add_node(protein_b_node, "property")
                        self.add_edge(measurement_node, protein_a_node, "protein_a")
                        self.add_edge(measurement_node, protein_b_node, "protein_b")
                        
                        logger.logMessage("info", f"Successfully recorded protein levels for {target_obj['name']}")
                        
                        # Analyze for outliers
                        outliers = self.analyze_protein_levels()
                        if outliers:
                            logger.logMessage("info", f"Identified outliers: {outliers}")
                        
                        self.exploration_steps = 0
                except Exception as e:
                    logger.logMessage("error", f"Failed to parse protein levels: {str(e)}")

def run_episode(agent, api, seed, difficulty, max_steps, agent_type="knowledge_graph"):
    """Run a single episode"""
    logger.logMessage("info", f"Starting episode with seed {seed}, difficulty {difficulty}, agent type {agent_type}")
    
    success = api.loadScenario("Proteomics", difficulty, seed, 1)
    if not success:
        logger.logMessage("error", "Failed to load scenario")
        return None
    
    observation = api.getAgentObservation(0)
    
    last_action = None
    for step in range(max_steps):
        if agent_type == "knowledge_graph":
            agent.update(observation, last_action)
        else:
            agent.update(observation, last_action)
        
        action = agent.think(observation)
        
        if action is None:
            logger.logMessage("info", "Agent has completed its task or cannot determine next action")
            break
            
        logger.logMessage("info", f"Taking action: {json.dumps(action)}")
        
        result = api.performAgentAction(0, action)
        if not result.get("success", False):
            logger.logMessage("warning", f"Action failed: {json.dumps(result)}")
        
        last_action = action
        
        api.tick()
        observation = api.getAgentObservation(0)
        
        if api.world.taskScorer.tasks[0].completed:
            break
    
    scorecard = api.getTaskScorecard()[0]
    
    result = {
        "completion": int(scorecard["completed"]),
        "success": int(scorecard["completedSuccessfully"]),
        "process_score": scorecard["scoreNormalized"],
        "steps": step + 1,
        "protein_levels": agent.protein_levels
    }
    
    if agent_type == "knowledge_graph":
        result.update({
            "nodes": len(agent.nodes),
            "edges": len(agent.edges),
            "hypotheses": list(agent.hypotheses)
        })
    
    return result

def plot_results(results):
    """Generate plots comparing baseline and experimental conditions"""
    # Separate results by agent type
    kg_results = [r for r in results["episodes"] if r["agent_type"] == "knowledge_graph"]
    baseline_results = [r for r in results["episodes"] if r["agent_type"] == "baseline"]
    
    # Plot process scores
    plt.figure(figsize=(10, 6))
    plt.plot([r["process_score"] for r in kg_results], label="Knowledge Graph Agent")
    plt.plot([r["process_score"] for r in baseline_results], label="Baseline Agent")
    plt.xlabel("Episode")
    plt.ylabel("Process Score")
    plt.title("Process Scores by Agent Type")
    plt.legend()
    plt.savefig("to_save/process_scores.pdf")
    plt.close()
    
    # Plot graph complexity for knowledge graph agent
    plt.figure(figsize=(10, 6))
    plt.plot([r["nodes"] for r in kg_results], label="Nodes")
    plt.plot([r["edges"] for r in kg_results], label="Edges")
    plt.xlabel("Episode")
    plt.ylabel("Count")
    plt.title("Knowledge Graph Complexity")
    plt.legend()
    plt.savefig("to_save/graph_complexity.pdf")
    plt.close()

def analyze_results(results):
    """Perform statistical analysis of results"""
    kg_scores = [r["process_score"] for r in results["episodes"] if r["agent_type"] == "knowledge_graph"]
    baseline_scores = [r["process_score"] for r in results["episodes"] if r["agent_type"] == "baseline"]
    
    difference_scores, mean_baseline, mean_experimental = generate_difference_scores_parallel_arrays(baseline_scores, kg_scores)
    bootstrap_results = bootstrap_resampling(difference_scores, mean_baseline, mean_experimental)
    
    return bootstrap_results

def main():
    results = {
        "pilot_mode": PILOT_MODE,
        "timestamp": datetime.now().isoformat(),
        "episodes": []
    }
    
    for difficulty in DIFFICULTIES:
        for seed in SEEDS:
            # Run knowledge graph agent
            kg_agent = KnowledgeGraphAgent(thread_id=seed)
            kg_api = DiscoveryWorldAPI(threadID=seed)
            kg_result = run_episode(kg_agent, kg_api, seed, difficulty, MAX_STEPS_PER_EPISODE, "knowledge_graph")
            
            if kg_result:
                kg_result.update({
                    "difficulty": difficulty,
                    "seed": seed,
                    "agent_type": "knowledge_graph"
                })
                results["episodes"].append(kg_result)
                logger.logMessage("info", f"Completed knowledge graph agent episode: difficulty={difficulty}, seed={seed}, success={kg_result['success']}")
            
            # Run baseline agent
            baseline_agent = BaselineReActAgent(thread_id=seed)
            baseline_api = DiscoveryWorldAPI(threadID=seed)
            baseline_result = run_episode(baseline_agent, baseline_api, seed, difficulty, MAX_STEPS_PER_EPISODE, "baseline")
            
            if baseline_result:
                baseline_result.update({
                    "difficulty": difficulty,
                    "seed": seed,
                    "agent_type": "baseline"
                })
                results["episodes"].append(baseline_result)
                logger.logMessage("info", f"Completed baseline agent episode: difficulty={difficulty}, seed={seed}, success={baseline_result['success']}")
    
    # Generate plots
    plot_results(results)
    
    # Perform statistical analysis
    stats = analyze_results(results)
    results["statistical_analysis"] = stats
    
    # Save results
    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()