import json


def load_bioc_study(filename):
    bioc_study = None
    try:
        with open(F"{filename}", "r", encoding="utf-8") as fin:
            bioc_study = json.loads(fin.read())
    except IOError:
        print(F"Unable to locate/open file: {filename}")
    return bioc_study

def write_bioc_study(doc, filename):
    try:
        with open(filename, 'wt') as f:
            f.write(json.dumps(doc))
    except IOError:
        print(F"Unable to open file for writing: {filename}")