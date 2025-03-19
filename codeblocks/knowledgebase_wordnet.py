# Name: WordNet with NLTK (Comprehensive Guide)
# Description: This example provides a guide to using WordNet in Python via the NLTK library, covering synonyms, antonyms, hypernyms, hyponyms, and meronyms.
# inclusion_criteria: If you'd like to use WordNet (a lexical database with limited coverage of synonyms, antonyms, hypernyms, hyponyms, meronyms), this codeblock is likely to be useful.
# exclusion_criteria: If you're not explicitly using WordNet, this codeblock likely will not be useful.
# python_version: >=3.8
# pip_requirement: nltk


from experiment_common_library import setup_wordnet   # Import the setup_wordnet function


# Get synsets (semantic sets) for a word
def get_synsets(word: str):
    """
    Returns all synsets (semantic sets) for a word.

    Parameters:
    word (str): The word to search for.

    Returns:
    list: A list of synsets (wn.Synset objects).

    Example:
    >>> get_synsets("car")
    [Synset('car.n.01'), Synset('car.n.02'), Synset('car.n.03'), Synset('car.n.04')]
    """
    from nltk.corpus import wordnet as wn
    return wn.synsets(word)

# Get the definition ("gloss") of a synset.  Returns a string.
def get_synset_definition(synset):
    return synset.definition()

# Get the words in a synset
def get_words_in_synset(synset):
    """
    Returns all words (lemmas) in a given synset.

    Parameters:
    synset (wn.Synset): The synset to extract words from.

    Returns:
    list: A list of words (strings).

    Example:
    >>> get_words_in_synset(wn.synset('car.n.01'))
    ['car', 'auto', 'automobile', 'machine', 'motorcar']
    """
    return [lemma.name() for lemma in synset.lemmas()]

# Get synonyms for a word
def get_synonyms(word: str):
    """
    Returns all synonyms for a word across all its synsets.

    Parameters:
    word (str): The word to search for.

    Returns:
    list: A list of synonyms (strings).

    Example:
    >>> get_synonyms("car")
    ['car', 'auto', 'automobile', 'machine', 'motorcar']
    """
    from nltk.corpus import wordnet as wn

    synonyms = []
    for synset in wn.synsets(word):
        for lemma in synset.lemmas():
            synonyms.append(lemma.name())
    return list(set(synonyms))  # Remove duplicates

# Get antonyms for a word
def get_antonyms(word: str):
    """
    Returns all antonyms for a word across all its synsets.

    Parameters:
    word (str): The word to search for.

    Returns:
    list: A list of antonyms (strings).

    Example:
    >>> get_antonyms("good")
    ['evil', 'bad', 'ill']
    """
    from nltk.corpus import wordnet as wn

    antonyms = []
    for synset in wn.synsets(word):
        for lemma in synset.lemmas():
            if lemma.antonyms():
                antonyms.extend([ant.name() for ant in lemma.antonyms()])
    return list(set(antonyms))

# Get direct hypernyms (broader terms) for a word
def get_direct_hypernyms(word: str):
    """
    Returns direct hypernyms for a word.

    Parameters:
    word (str): The word to search for.

    Returns:
    list: A list of direct hypernyms (wn.Synset objects).

    Example:
    >>> get_direct_hypernyms("car")
    [Synset('motor_vehicle.n.01')]
    """
    from nltk.corpus import wordnet as wn

    hypernyms = []
    for synset in wn.synsets(word):
        hypernyms.extend(synset.hypernyms())
    return list(set(hypernyms))

# Get all continuous hypernyms (entire hypernym chain) for a word
def get_continuous_hypernyms(word: str):
    """
    Returns all continuous hypernyms (entire hypernym chain) for a word.

    Parameters:
    word (str): The word to search for.

    Returns:
    list: A list of continuous hypernyms (wn.Synset objects).

    Example:
    >>> get_continuous_hypernyms("car")
    [Synset('motor_vehicle.n.01'), Synset('wheeled_vehicle.n.01'), Synset('vehicle.n.01'), ...]
    """
    from nltk.corpus import wordnet as wn

    hypernyms = []
    for synset in wn.synsets(word):
        chain = synset.hypernym_paths()
        for path in chain:
            hypernyms.extend(path)
    return list(set(hypernyms))

# Get direct hyponyms (narrower terms) for a word
def get_direct_hyponyms(word: str):
    """
    Returns direct hyponyms for a word.

    Parameters:
    word (str): The word to search for.

    Returns:
    list: A list of direct hyponyms (wn.Synset objects).

    Example:
    >>> get_direct_hyponyms("car")
    [Synset('ambulance.n.01'), Synset('limousine.n.01'), Synset('sports_car.n.01')]
    """
    from nltk.corpus import wordnet as wn

    hyponyms = []
    for synset in wn.synsets(word):
        hyponyms.extend(synset.hyponyms())
    return list(set(hyponyms))

# Get all continuous hyponyms (entire hyponym tree) for a word
def get_continuous_hyponyms(word: str):
    """
    Returns all continuous hyponyms (entire hyponym tree) for a word.

    Parameters:
    word (str): The word to search for.

    Returns:
    list: A list of continuous hyponyms (wn.Synset objects).

    Example:
    >>> get_continuous_hyponyms("car")
    [Synset('ambulance.n.01'), Synset('fire_engine.n.01'), Synset('limousine.n.01'), ...]
    """
    from nltk.corpus import wordnet as wn

    hyponyms = []
    for synset in wn.synsets(word):
        for hyponym in synset.closure(lambda s: s.hyponyms()):
            hyponyms.append(hyponym)
    return list(set(hyponyms))

# Get part meronyms (components) for a word
def get_part_meronyms(word: str):
    """
    Returns part meronyms (components) for a word.

    Parameters:
    word (str): The word to search for.

    Returns:
    list: A list of part meronyms (wn.Synset objects).

    Example:
    >>> get_part_meronyms("car")
    [Synset('accelerator.n.01'), Synset('brake.n.01'), Synset('steering_wheel.n.01')]
    """
    from nltk.corpus import wordnet as wn

    meronyms = []
    for synset in wn.synsets(word):
        meronyms.extend(synset.part_meronyms())
    return list(set(meronyms))

# Example usage
def example_usage():
    word = "car"

    print(f"Synsets for '{word}':")
    print(get_synsets(word))
    # Expected: [Synset('car.n.01'), Synset('car.n.02'), Synset('car.n.03'), Synset('car.n.04'), Synset('cable_car.n.01')]

    print(f"\nWords in first synset of '{word}':")
    print(get_words_in_synset(get_synsets(word)[0]))
    # Expected: ['car', 'auto', 'automobile', 'machine', 'motorcar']

    print(f"\nDefinition of first synset of '{word}':")
    print(get_synset_definition(get_synsets(word)[0]))
    # Expected: a motor vehicle with four wheels; usually propelled by an internal combustion engine

    print(f"\nSynonyms for '{word}':")
    print(get_synonyms(word))
    # Expected: ['car', 'machine', 'railway_car', 'railroad_car', 'gondola', 'cable_car', 'motorcar', 'railcar', 'automobile', 'auto', 'elevator_car']

    print(f"\nDirect Hypernyms for '{word}':")
    print(get_direct_hypernyms(word))
    # Expected: [Synset('compartment.n.02'), Synset('wheeled_vehicle.n.01'), Synset('motor_vehicle.n.01')]

    print(f"\nContinuous Hypernyms for '{word}':")
    print(get_continuous_hypernyms(word))
    # Expected (long list; truncated): [Synset('car.n.02'), Synset('container.n.01'), Synset('car.n.03'), Synset('car.n.01'), Synset('entity.n.01'), Synset('whole.n.02'), Synset('compartment.n.02'), ... ]

    print(f"\nDirect Hyponyms for '{word}':")
    print(get_direct_hyponyms(word))
    # Expected (long list; truncated): [Synset('beach_wagon.n.01'), Synset('slip_coach.n.01'), Synset('compact.n.03'), Synset('gas_guzzler.n.01'), Synset('cab.n.03'), ... ]

    print(f"\nContinuous Hyponyms for '{word}':")
    print(get_continuous_hyponyms(word))
    # Expected (long list; truncated): [Synset('panda_car.n.01'), Synset('beach_wagon.n.01'), Synset('stock_car.n.02'), Synset('slip_coach.n.01'), Synset('compact.n.03'), ... ]

    print(f"\nPart meronyms for '{word}':")
    print(get_part_meronyms(word))
    # Expected (long list; truncated): [Synset('buffer.n.06'), Synset('third_gear.n.01'), Synset('window.n.02'), Synset('first_gear.n.01'), Synset('automobile_horn.n.01'), ... ]

# Main
if __name__ == "__main__":
    setup_wordnet()
    example_usage()
