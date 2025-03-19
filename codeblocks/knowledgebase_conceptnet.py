# Name: ConceptNet Knowledge Base
# Description: Provides fast, local access to the English subset of the ConceptNet knowledge base. This a pre-processed version of ConceptNet that makes it easier to use.
# inclusion_criteria: If you need to access ConceptNet knowledge base, and need the English subset, this codeblock is likely to be useful.
# exclusion_criteria: If you don't need to access ConceptNet knowledge base, or need a different language subset, this codeblock is unlikely to be useful. Similarly, this pre-processed version contains only the node names and edges, and discards all other metadata.
# python_version: >=3.8
# pip_requirement: gdown

import os
import json
import subprocess

from experiment_common_library import ConceptNet        # Import the ConceptNet class

# Example usage
def example_usage():
    # Create a ConceptNet object
    conceptNet = ConceptNet()

    term = "cat"

    # Find nodes that start with a given string
    print(f"Nodes starting with '{term}' (non-strict):")
    nodes = conceptNet.find_nodes(term, strict=False)
    print(nodes)
    # Expected return (extremely long; truncated): ['catheterized', 'categorize/v/wn/cognition', 'cataplasm', 'cattiness', 'cat_rig/n/wn/artifact', 'catty_corner', 'catalina_coupon', 'catenary_bridges', 'catsicles', 'catching/n/opencyc/catching_on_fiire', 'catalan_republic', 'catherinian', 'catchline', 'categorical_imperatives', ... ]

    # Find nodes that start with a given string (strict)
    print(f"Nodes starting with '{term}' (strict):")
    nodes = conceptNet.find_nodes(term, strict=True)        # Strict = true
    print(nodes)
    # Expected return: ['cat/n/wn/animal', 'cat/n/wn/artifact', 'cat/n/wikt/en_5', 'cat/n/wikt/en_9', 'cat/n/wn/person', 'cat/n', 'cat/v/wn/contact', 'cat/n/wikt/en_8', 'cat', 'cat/v/wn/body', 'cat/n/wikt/en_3', 'cat/a/wikt/en_4', 'cat/n/wp/novel', 'cat/n/wn/act', 'cat/v/wikt/en_1', 'cat/n/wikt/en_6', 'cat/n/wikt/en_1', 'cat/v/wikt/en_3', 'cat/n/wikt/en_2']

    # Get edges for a node
    node_name = "cat/n"
    print(f"Edges for node '{node_name}':")
    edges = conceptNet.get_node_edges(node_name)
    print(edges)
    # Expected return: [['cat/n', 'ExternalURL', 'http://sw.opencyc.org/2012/05/10/concept/en/Cat'], ['cat/n', 'HasContext', 'medicine'], ['cat/n', 'INV_DerivedFrom', 'cat_scan'], ['cat/n', 'INV_FormOf', 'cats'], ['cat/n', 'INV_IsA', 'adult_cat/n'], ['cat/n', 'INV_IsA', 'house_cat/n'], ['cat/n', 'INV_IsA', 'kitten/n'], ['cat/n', 'INV_IsA', 'male_cat/n'], ['cat/n', 'INV_IsA', 'she_cat'], ['cat/n', 'IsA', 'felis/n'], ['cat/n', 'IsA', 'non_person_animal/n'], ['cat/n', 'RelatedTo', 'acetyltransferase'], ['cat/n', 'RelatedTo', 'chloramphenicol'], ['cat/n', 'RelatedTo', 'computed_axial_tomography'], ['cat/n', 'RelatedTo', 'computer_aided_translation'], ['cat/n', 'Synonym', 'ct']]

    # Get a list of all relation types across all edges in the graph
    print("All relation types:")
    relations = conceptNet.get_all_relations()
    print(relations)
    # Expected return: ['Antonym', 'AtLocation', 'CapableOf', 'Causes', 'CausesDesire', 'CreatedBy', 'DefinedAs', 'DerivedFrom', 'Desires', 'DistinctFrom', 'Entails', 'EtymologicallyDerivedFrom', 'EtymologicallyRelatedTo', 'ExternalURL', 'FormOf', 'HasA', 'HasContext', 'HasFirstSubevent', 'HasLastSubevent', 'HasPrerequisite', 'HasProperty', 'HasSubevent', 'INV_Antonym', 'INV_AtLocation', 'INV_CapableOf', 'INV_Causes', 'INV_CausesDesire', 'INV_CreatedBy', 'INV_DefinedAs', 'INV_DerivedFrom', 'INV_Desires', 'INV_DistinctFrom', 'INV_Entails', 'INV_EtymologicallyDerivedFrom', 'INV_EtymologicallyRelatedTo', 'INV_ExternalURL', 'INV_FormOf', 'INV_HasA', 'INV_HasContext', 'INV_HasFirstSubevent', 'INV_HasLastSubevent', 'INV_HasPrerequisite', 'INV_HasProperty', 'INV_HasSubevent', 'INV_InstanceOf', 'INV_IsA', 'INV_LocatedNear', 'INV_MadeOf', 'INV_MannerOf', 'INV_MotivatedByGoal', 'INV_NotCapableOf', 'INV_NotDesires', 'INV_NotHasProperty', 'INV_PartOf', 'INV_ReceivesAction', 'INV_RelatedTo', 'INV_SimilarTo', 'INV_SymbolOf', 'INV_Synonym', 'INV_UsedFor', 'INV_dbpedia/capital', 'INV_dbpedia/field', 'INV_dbpedia/genre', 'INV_dbpedia/genus', 'INV_dbpedia/influencedBy', 'INV_dbpedia/knownFor', 'INV_dbpedia/language', 'INV_dbpedia/leader', 'INV_dbpedia/occupation', 'INV_dbpedia/product', 'InstanceOf', 'IsA', 'LocatedNear', 'MadeOf', 'MannerOf', 'MotivatedByGoal', 'NotCapableOf', 'NotDesires', 'NotHasProperty', 'PartOf', 'ReceivesAction', 'RelatedTo', 'SimilarTo', 'SymbolOf', 'Synonym', 'UsedFor', 'dbpedia/capital', 'dbpedia/field', 'dbpedia/genre', 'dbpedia/genus', 'dbpedia/influencedBy', 'dbpedia/knownFor', 'dbpedia/language', 'dbpedia/leader', 'dbpedia/occupation', 'dbpedia/product']
    # NOTE: Having INV_ prefixes indicates the inverse of the relation. For example, "INV_IsA" is the inverse of "IsA". So "Cat IsA Animal" would be represented as "Animal INV_IsA Cat".

    # Let's run through that "IsA" and "INV_IsA" example
    cat_node = "cat/n/wn/animal"    # Hopefully this is the 'cat (animal)' node
    print(f"Edges for node '{cat_node}' (IsA and INV_IsA only):")
    edges = conceptNet.get_node_edges(cat_node, filter_relation_types=["IsA", "INV_IsA"])
    print(edges)
    # Expected return: [['cat/n/wn/animal', 'INV_IsA', 'domestic_cat/n/wn/animal'], ['cat/n/wn/animal', 'INV_IsA', 'wildcat/n/wn/animal'], ['cat/n/wn/animal', 'IsA', 'feline/n/wn/animal']]
    # i.e. that `cat (animal)` is a kind of `feline (animal)`, and that `domestic cat (animal)` and `wildcat (animal)` are kinds of `cat (animal)`.

    # Get a list of all nodes in the graph (node names only)
    # print("All node names:")
    # nodes = conceptNet.get_all_nodes()
    # print(nodes)
    # You likely won't want to print this, as it's a very long list of node names (millions of nodes)


# Main
if __name__ == "__main__":
    example_usage()
