# Name: DOT Graphviz Graph
# Description: This is an example of using DOT/Graphviz to create a graph.
# inclusion_criteria: If you want to create graphs (i.e. composed of nodes and edges), either generally (in text), or exporting them (visually), then you may want to use this codeblock.
# exclusion_criteria: If you are not creating graphs (composed of nodes and edges), or using DOT/Graphviz related concepts, then this codeblock is unlikely to be useful.
# python_version: >=3.8


from experiment_common_library import run_dot_graphviz  # Import the run_dot_graphviz function

# An example of a simple 3 node graph
def example1():
    # Create an example DOT file, line by line
    example_dot = "digraph G {\n"
    example_dot += "    A -> B;\n"
    example_dot += "    B -> C;\n"
    example_dot += "    C -> A;\n"
    example_dot += "}\n"

    # Save the DOT file to 'example_graph.dot'
    with open('example_graph.dot', 'w') as f:
        f.write(example_dot)

    # Run the DOT/Graphviz program to create a graph from the DOT file
    run_dot_graphviz('example_graph.dot', 'example_graph.pdf')

# An example of a graph with labeled edges
def example2():
    # Create an example DOT file with labeled edges
    example_dot = "digraph G {\n"
    example_dot += "    A -> B [label=\"Edge from A to B\"];\n"
    example_dot += "    B -> C [label=\"Edge from B to C\"];\n"
    example_dot += "    C -> A [label=\"Edge from C to A\"];\n"
    example_dot += "}\n"

    # Save the DOT file to 'example_graph_labeled.dot'
    with open('example_graph_labeled.dot', 'w') as f:
        f.write(example_dot)

    # Run the DOT/Graphviz program to create a graph from the DOT file
    run_dot_graphviz('example_graph_labeled.dot', 'example_graph_labeled.pdf')

# Main
if __name__ == "__main__":
    example1()
    example2()