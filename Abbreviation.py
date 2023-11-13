import re


def __check_single_word_abbrev(fulltext, token):
    """
    Locate the expanded phrase for a single abbreviation
    @param fulltext: Text containing the declaration of the abbreviation
    @param token: Abbreviation to be expanded
    @return: The expanded text for the abbreviation.
    """
    # Identify first letter of the first word for the abbreviation
    result = ""
    first_char = token[0:1]
    # Get the number of occurrences of this letter in abbreviation.
    first_char_count = token.count(first_char)
    # Locate abbreviations in parenthesis
    search_regex = r"([ \-'\n\w0-9]+\n?\({0}[^a-zA-Z]{0,}\))".replace("{0}", re.escape(
        token))  # r"([ \-'\na-zA-Z0-9]+\n?\({0}\))".format(re.escape(token))
    declaration_match = re.search(
        search_regex, fulltext, re.IGNORECASE | re.MULTILINE)
    if declaration_match is None:  # No declaration found for token
        return None
    # First match SHOULD be the declaration of this abbreviation.
    # Split REGEX match to a list of words
    split_sent = declaration_match.group(0).replace(
        " )", ")").replace("( ", "(").replace("\n", "").split(" ")
    found_counter = 0
    found_indexes = []
    i = len(split_sent) - 2  # Indexing + ignore the actual abbreviation
    #  Moving backwards from the abbreviation, count each word in the sentence matching the first character.
    while i >= 0:
        if split_sent[i][0:1] == first_char:
            found_counter += 1
            found_indexes.append(i)
        i -= 1
    #  Add each word following (inclusively) the nth word with a matching first character.
    if first_char_count <= found_counter:
        found_indexes.sort()
        for x in split_sent[found_indexes[(first_char_count - found_counter)]:-1]:
            result += x + " "
    result = result.strip()
    if result:
        return result
    else:
        return False


def get_all_abbreviations(fulltext, section=None):
    """
    Returns the expanded form of an abbreviation from the fulltext.
    @param fulltext: The document containing the abbreviations and their declarations
    @return: String containing the expanded version of the abbreviation.
    """
    changes = []
    # r"([^(-]\b[a-z]{0,}[A-Z]{2,}[a-z]{0,}\b[^)-])"
    pattern = r"([^ \"',.(-]\b)?([a-z]{0,})([A-Z]{2,})([a-z]{0,})(\b[^;,.'\" )-]?)"
    input_text = None
    if section:
        input_text = section
    else:
        input_text = fulltext
    for match in re.findall(pattern, input_text):
        target = ""
        if type(match) == str:
            target = match
        else:
            target = match[2]
        target = target.strip()
        if target not in [x for [x, y] in changes]:
            changes.append(
                [target, replace_abbreviations(target, fulltext)])
    for change in changes:
        if change[1]:
            if change[1] != change[0]:
                input_text = input_text.replace(change[0], change[1])
    # Interpreter.__logger.info(changes) #  Can error due to strange encodings used.
    return [(x, y) for (x, y) in changes if x != y]


def replace_abbreviations(token, fulltext):
    """
    Returns the expanded form of an abbreviation from the fulltext.
    @param token: The abbreviation to be expanded.
    @param fulltext: The document containing the declaration of the abbreviation.
    @return: String containing the expanded version of the abbreviation.
    """
    # Remove all preceding and trailing white space.
    doc = token.strip()
    if len(doc) < 5:
        result = __check_single_word_abbrev(
            fulltext, doc.upper())
        if result:
            return result
        else:
            return doc
    else:
        return doc

def find_all_abbreviations(fulltext, section=None):
    """
    Returns the occurrences of all abbreviations found in the fulltext.
    @param fulltext: The document containing the abbreviations and their declarations
    @return: List containing the short and long forms of the abbreviations, dict with occurrences.
    """
    abbreviations = {}
    occurrences = {}
    # r"([^(-]\b[a-z]{0,}[A-Z]{2,}[a-z]{0,}\b[^)-])"
    pattern = r"([^ \"',.(-]\b)?([a-z]{0,})([A-Z]{2,})([a-z]{0,})(\b[^;,.'\" )-]?)"
    input_text = None
    if section:
        input_text = section
    else:
        input_text = fulltext
    for match in re.findall(pattern, input_text):
        target = ""
        if type(match) == str:
            target = match
        else:
            target = match[2]
        target = target.strip()
        if target not in abbreviations:
            abbreviations[target] = replace_abbreviations(target, fulltext)
            occurrences[target] = [match.span()]
        else:
            occurrences[target].append(match.span())
    
    return abbreviations, occurrences

def __clean_reference_remains(text):
    return text.replace("()", "").replace("(, )", "")

