import streamlit as st
import streamlit.components.v1 as components
import os
import requests
import pandas as pd
from SupplementaryDownloader import download_doc_pmc_id
from bioc2pubannotation import bioc2pubanno
from Annotator import main as annotate

# configurable paths
path_ontology = '/home/hdetering/Dropbox/Projects/Bgee/visualisation/data/uberon.obo'

# toggle rendering of sections
show_doc = False
show_suppl = False
show_doc_anno = False
has_annotations = False
is_doc_downloaded = False
is_doc_annotated = False

# document PubAnnotation string (to show in viewer)
str_pubanno = ''
str_doc = ''
str_doc_ann = ''

st.write("""
# Biocuration Cockpit

Some (hopfully) useful functions to support the biocuration process. 
""")

id_pmc = st.text_input('PMCID', 'PMC6522369')
#st.write(f'You entered the following PMCID: "{id_pmc}"')

url_pmc = f'https://www.ncbi.nlm.nih.gov/pmc/articles/{id_pmc}/'
headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:101.0) Gecko/20100101 Firefox/101.0"}
r = requests.get(url_pmc, headers = headers)

# check if PMCID is valid
if r.status_code == 200:
  st.write(f'INFO: publication found: {url_pmc}')
else:
  st.write(f'ERROR: PMCID not found: {id_pmc}')
  st.write(f'Return code: {r.status_code}')

path_data = f'_{id_pmc}'

# check if document is present
fn_bioc_json = os.path.join(path_data, f'{id_pmc}.json')
fn_pubann = os.path.join(path_data, f'{id_pmc}.pubann.json')
if os.path.exists(fn_bioc_json):
  is_doc_downloaded = True
  show_doc = True

# download doc + supplementary material
if not is_doc_downloaded:
  #st.write('Download document')
  if st.button('Download'):
    with st.spinner('Downloading document (+ Supplementary files)...'):
      result = download_doc_pmc_id(id_pmc, path_data)
    if result:
      # convert document to PubAnnotator
      bioc2pubanno(fn_bioc_json, fn_pubann)
      # show document and supplementary UI sections
      show_doc = True
      show_suppl = True
      is_doc_downloaded = True
    else:
      st.write('Download failed!')

if is_doc_downloaded:
  # load doc PubAnnotation format
  with open(fn_pubann, 'rt') as f:
    str_doc = f.read()
  # check for supplementary items
  path_suppl = os.path.join(path_data, f'{id_pmc}_supplementary')
  df_supmat = pd.DataFrame()
  if os.path.exists(path_suppl):
    lst_files = []
    lst_paths = []
    for fn in os.listdir(path_suppl):
      if os.path.isfile(os.path.join(path_suppl, fn)):
        lst_files.append(fn)
        lst_paths.append(os.path.join(os.path.abspath(path_suppl), fn))
    lst_ext = [x.rsplit('.', 1)[1] for x in lst_files]
    lst_links = [f'<a target="_blank" href="file://{p}">{n}</a>' for (n,p) in zip(lst_files, lst_paths)]
    df_supmat = pd.DataFrame(zip(lst_links, lst_ext), columns=['filename', 'type'])
    # toggle supmat UI section
    show_suppl = True    

str_pubanno = str_doc

# check if document has annotations
fn_pubann = os.path.join(path_data, f'{id_pmc}.ann.pubann.json')
if os.path.exists(fn_pubann):
  with open(fn_pubann, 'rt') as f:
    str_doc_ann = f.read()
  show_doc_anno = True
  str_pubanno = str_doc_ann

if show_doc or show_doc_anno:
  st.write("""
## Document



Viewer showing document content (text only, formatting removed).
""")
  #components.iframe('https://textae.pubannotation.org/editor.html?mode=edit')
  components.html(f"""
<meta charset="utf-8" />
<link rel="stylesheet" href="https://textae.pubannotation.org/lib/css/textae.min.css" />
<script src="https://textae.pubannotation.org/lib/textae.min.js"></script>
                  
<div class="textae-editor">
  {str_pubanno}
</div>
""", height=600, scrolling=True)

# check for annotations
fn_anno = os.path.join(path_data, f'{id_pmc}.ann.pubann.json')
if os.path.exists(fn_anno):
  has_annotations = True
if not has_annotations and is_doc_downloaded:
  if st.button('Annotate!'):
    with st.spinner('Annotating document...'):
      result = annotate(path_ontology, path_data)
      #pass
    if result:
      fn_anno_bioc = os.path.join(path_data, f'{id_pmc}.ann.json')
      # convert document to PubAnnotator
      bioc2pubanno(fn_anno, fn_anno)
      # show document and supplementary UI sections
      has_annotations = True
    else:
      st.write('Annotation failed!')


if show_suppl:
  st.write("""
## Supplementary Files

List of supplementary files associated with the document.
""")
  #st.table(df_supmat)
  st.markdown(df_supmat.to_html(render_links=True, escape=False), unsafe_allow_html=True)


if not os.path.exists(path_data):
  os.mkdir(path_data)

# 2-column layout - doesn't work
# AttributeError: module 'streamlit' has no attribute 'beta_columns'
#col1, col2 = st.beta_columns(2)

# form example
#frm_download = st.form(key = 'frm_download')
#frm_download.write('Download supplementary materials')
#frm_download_submit = frm_download.form_submit_button('Do it!')
