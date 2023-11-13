import os
import sys
import json

def bioc2pubanno(infile, outfile):
  # read input file (BioC JSON)
  doc = {}
  with open(infile, 'rt') as f:
    doc = json.loads(f.read())
  if 'documents' in doc:
    doc = doc['documents'][0]

  doc_out = {
    'text': '\n'.join([psg['text'] for psg in doc['passages']]),
    'denotations': [{
      'id': a['id'],
      'span': {
        'begin': a['locations'][0]['offset'],
        'end': a['locations'][0]['offset'] + a['locations'][0]['length'] - 1,
      },
      'obj': a['infons']['x-ref'] if 'x-ref' in a['infons'] else a['text'] #'Term'
    } for p in doc['passages'] for a in p['annotations']]
  }

  with open(outfile, 'wt') as f:
    f.write(json.dumps(doc_out))


if __name__ == '__main__':
  # check command line params
  if len(sys.argv) < 3:
    print(f'usage: {sys.argv[0]} infile outfile')
    sys.exit(1)

  bioc_file = sys.argv[1]
  pubanno_file = sys.argv[2]
  assert os.path.exists(bioc_file), f'ERROR: file does not exist: {bioc_file}'
  
  bioc2pubanno(bioc_file, pubanno_file)