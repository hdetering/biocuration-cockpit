import argparse
import itertools
import re

import bs4
import scispacy
import spacy
import obonet
import networkx
import uuid
import os
from spacy.matcher import PhraseMatcher
from spacy.tokens import Span

# from single_cell_use_case.OntologyAnnotator.Abbreviation import replace_all_abbreviations
# from single_cell_use_case.OntologyAnnotator.Utils import load_bioc_study
from Abbreviation import get_all_abbreviations
from Utils import load_bioc_study, write_bioc_study
import difflib


def get_similarity_score(input_str, target_str):
    return difflib.SequenceMatcher(None, input_str, target_str).ratio()


def sort_strings_by_similarity(input_str, string_list):
    scores = [get_similarity_score(input_str, target_str) for target_str in string_list]
    return list(zip(string_list, scores))[0]


class SpacyModel:

    def __init__(self, ontology_path):
        # pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_ner_bionlp13cg_md-0.5.3.tar.gz
        self.model = spacy.load("en_ner_bionlp13cg_md", disable=["ner"])
        self.ontology = obonet.read_obo(ontology_path)  # ("/home/tr142/Downloads/uberon.obo")
        self.term_list = self.get_simple_term_list()
        # self.ontology = obonet.read_obo("/home/hdetering/Dropbox/Projects/Bgee/visualisation/data/uberon.obo")
        self.term_matcher = PhraseMatcher(self.model.vocab, attr="LOWER")
        self.abbreviation_matcher = PhraseMatcher(self.model.vocab)
        self.__add_ontology_terms()

    def __add_ontology_terms(self):
        id_to_name = {id_: data.get('name') for id_, data in self.ontology.nodes(data=True)}
        for node in self.ontology.nodes:
            if id_to_name[node]:
                patterns = []
                patterns.extend(get_term_variations(id_to_name[node]))
                if "synonym" in self.ontology.nodes[node].keys():
                    for syn in self.ontology.nodes[node]["synonym"]:
                        patterns.extend(get_term_variations(syn[1:syn.find("\"", 1)]))
                patterns = self.model.tokenizer.pipe(patterns)
                self.term_matcher.add(node, patterns, on_match=self.__on_match)

    def get_simple_term_list(self):
        terms = {}
        for key, data in self.ontology.nodes(data=True):
            if "name" not in data.keys():
                continue
            terms[data["name"]] = key
            if "synonym" not in data.keys():
                continue
            for syn in data["synonym"]:
                terms[syn[1:syn.find("\"", 1)]] = key
        return terms

    def set_abbreviations(self, abbrevs):
        result = []
        self.abbreviation_matcher = PhraseMatcher(self.model.vocab)
        for abbrev in abbrevs:
            try:
                term_id = sort_strings_by_similarity(abbrev[1], self.term_list)
                if term_id[1] < 0.8:
                    continue
                result.append([self.term_list[term_id[0]], abbrev[0]])
            except:
                return None
        for term in result:
            self.abbreviation_matcher.add(term[0], self.model.tokenizer.pipe(term[1]), on_match=self.__on_match)

    def __on_match(self, matcher, doc, i, matches):
        """
        (Event handler) Add matched entity to document entity list if no overlap is caused.
        @param matcher: Matcher object which fired the event
        @param doc: nlp doc object
        @param i: index of the current match
        @param matches: list of matches found by the matcher object
        """
        match_id, start, end = matches[i]
        entity = Span(doc, start, end,
                      label=self.model.vocab.strings[match_id])
        try:
            doc.ents += (entity,)
        except Exception:
            entities_to_replace = []
            for ent in doc.ents:
                if (start <= ent.start < end) or (start < ent.end <= end):
                    if entity.label_.isnumeric() and not ent.label_.isnumeric():
                        return
                    if not entity.label_.isnumeric() and ent.label_.isnumeric():
                        entities_to_replace.append(ent)
                        continue
                    if len(ent) < len(entity):
                        entities_to_replace.append(ent)
            if entities_to_replace:
                doc.ents = [x for x in doc.ents if x not in entities_to_replace]
                doc.ents += (entity,)
            return

    def annotate_text(self, text):
        annotated_doc = self.model(text)
        self.term_matcher(annotated_doc)
        #self.abbreviation_matcher(annotated_doc)
        return annotated_doc


def remove_comma_variation(term: str):
    if "," in term:
        adjusted_term = term.split(",")
        adjusted_term = adjusted_term[1] + " " + adjusted_term[0]
        adjusted_term = adjusted_term.lstrip()
        return adjusted_term
    else:
        return None


def get_plural_variation(term: str):
    if term.lower()[-1] == "s":
        return term[:-1]
    else:
        return term + "s"


def get_int_from_roman(s: str) -> int:
    """
    :type s: str
    :rtype: int
    """
    # Credit to https://www.tutorialspoint.com/roman-to-integer-in-python for this function
    roman = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000, 'IV': 4, 'IX': 9, 'XL': 40, 'XC': 90,
             'CD': 400, 'CM': 900}
    i = 0
    num = 0
    while i < len(s):
        if i + 1 < len(s) and s[i:i + 2] in roman:
            num += roman[s[i:i + 2]]
            i += 2
        else:
            num += roman[s[i]]
            i += 1
    return num


def get_roman_numeral_variation(term: str):
    search_result = re.search(r"(\d+)", term)
    roman_numerals = [
        "M", "CM", "D", "CD",
        "C", "XC", "L", "XL",
        "X", "IX", "V", "IV",
        "I"
    ]
    numerals = [
        1000, 900, 500, 400,
        100, 90, 50, 40,
        10, 9, 5, 4,
        1
    ]
    is_original_roman = False
    if not search_result:
        for word in term.split(" "):
            if word in roman_numerals:
                replacement = word
                is_original_roman = True
                break
    result = None
    replacement = ''
    if not is_original_roman:
        if not search_result:
            return None
        num = search_result.group(0)
        replacement = num
        # Adapted from solution found here
        # https://www.w3resource.com/python-exercises/class-exercises/python-class-exercise-1.php
        roman_num = ''
        i = 0
        num = int(num)
        while num > 0:
            for _ in range(num // numerals[i]):
                roman_num += roman_numerals[i]
                num -= numerals[i]
            i += 1
        result = term.replace(replacement, roman_num)
    elif is_original_roman:
        roman_num = replacement
        replacement = get_int_from_roman(roman_num)
        result = term.replace(roman_num, str(replacement))

    return result


def get_term_variations(term):
    """
    Calculate every plausible variation of the input term, including synonyms.
    :param term: LexiconEntry object containing the desired term.
    :return: List of string variations.
    """
    patterns = [term]
    # TODO: plurals + reverse the roman numerals too!
    funcs = [remove_comma_variation, get_hyphenated_variations,
             get_roman_numeral_variation, get_plural_variation]
    new_patterns = []
    combos = [itertools.combinations(funcs, 1), itertools.combinations(funcs, 2),
              itertools.combinations(funcs, 3), itertools.combinations(funcs, 4)]
    combos = [x for y in combos for x in y]
    for pattern in patterns:
        for combo in combos:
            for func in combo:
                new_variant = func(pattern)
                if new_variant and new_variant not in new_patterns:
                    if type(new_variant) == list:
                        new_patterns += new_variant
                    else:
                        new_patterns.append(new_variant)
    new_patterns = list(set(patterns + new_patterns))
    return new_patterns


def get_hyphenated_variations(term: str):
    output = []
    # Remove hyphens.
    if "-" in term:
        output.append(term.replace("-", " "))
    # Add each variation of hyphenations.
    if " " in term:
        location = term.find(" ")
        for i in range(term.count(" ")):
            hyphenated = term[:location] + "-" + term[location + 1:]
            output.append(hyphenated)
            location = term.find(" ", location + 1)
            # no further spaces found.
            if location == -1:
                break
    return output


def main(ontology_path, directory):
    model = SpacyModel(ontology_path)
    files = [x for x in os.listdir(directory) if ".json" in x and ".ann." not in x and ".pubann." not in x]
    # for file in files:
    for idx_file in range(len(files)):
        filepath = os.path.join(directory, files[idx_file])
        study = load_bioc_study(filepath)
        if "documents" not in study:
            study = {"documents": [study]}
        full_text = "\n".join([x["text"] for x in study["documents"][0]["passages"]])
        abbreviations = get_all_abbreviations(full_text)
        model.set_abbreviations(abbreviations)
        for doc in study["documents"]:
            # for passage in doc["passages"]:
            for idx_psg in range(len(doc["passages"])):
                text = doc["passages"][idx_psg]["text"]
                offset = doc["passages"][idx_psg]["offset"]
                annotated_text = model.annotate_text(text)
                if annotated_text.ents:
                    # import pdb; pdb.set_trace()
                    print(annotated_text.text_with_ws)
                    print([(x.text, x.label_, offset + x.start_char, offset + x.end_char) for x in annotated_text.ents])
                    doc["passages"][idx_psg]["annotations"] += [{
                        "id": str(uuid.uuid4()),
                        "infons": {
                            "x-ref": x.label_
                        },
                        "text": x.text,
                        "locations": [{
                            "offset": offset + x.start_char,
                            "length": x.end_char - x.start_char + 1
                        }]
                    } for x in annotated_text.ents]
            fn_out = os.path.basename(filepath).replace(".json", ".ann.json")
            outfile = os.path.join(filepath.rsplit("/", 1)[0], fn_out)
            write_bioc_study(doc, outfile)

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='PROG')
    parser.add_argument('-d', '--directory', type=str, help="Path to directory containing bioc files for processing")
    parser.add_argument('-o', '--ontology', type=str,
                        help="Path or URL to the ontology OBO file")
    args = parser.parse_args()
    ontology_path = args.ontology
    directory = args.directory
    main(ontology_path, directory)
