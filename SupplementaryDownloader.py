import os
import random
import sys
from os.path import isfile, join, exists
from time import sleep
import requests
from bioc import biocjson
from lxml import etree
import logging
import argparse

logging.basicConfig(filename="SuppDownloader.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %("
                                                                               "message)s")
refs_log = logging.getLogger("ReferenceLogger")
refs_handler = logging.FileHandler("FailedSuppLinks.log")
refs_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
refs_log.addHandler(refs_handler)

missing_html_files = []
no_supp_links = []
bioc_failed = []
headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:101.0) Gecko/20100101 Firefox/101.0"}


def get_article_links(pmc_id):
    random_delay()
    response = None
    try:
        response = requests.get(F"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}", headers=headers)
    except requests.ConnectionError as ce:
        logging.error(F"{pmc_id} could not be downloaded:\n{ce}")
        missing_html_files.append(F"{pmc_id}")
    except Exception as ex:
        logging.error(F"{pmc_id} could not be downloaded:\n{ex}")
        missing_html_files.append(F"{pmc_id}")
    return response


def get_formatted_pmcid(bioc_file, is_id=False):
    pmc_id = F"{bioc_file.documents[0].id}" if not is_id else bioc_file
    if "PMC" not in pmc_id:
        pmc_id = F"PMC{pmc_id}"
    return pmc_id


def download_supplementary_file(link_address, new_dir, pmc_id):
    try:
        random_delay()
        file_response = requests.get(link_address, headers=headers, stream=True)
        if file_response.ok:
            new_file_path = new_dir + "/" + link_address.split("/")[-1].replace(" ", "_")
            with open(new_file_path, "wb") as f_out:
                for chunk in file_response.iter_content(chunk_size=1024 * 8):
                    if chunk:
                        f_out.write(chunk)
                        f_out.flush()
                        os.fsync(f_out.fileno())
            return True
    except IOError as ioe:
        logging.error(F"Error writing data from {link_address} due to:\n{ioe}")
        print(F"Error writing data from {link_address}\n")
        refs_log.error(F"{pmc_id} - Error writing data from {link_address}")
    except requests.ConnectionError as ce:
        logging.error(F"Error connecting to {link_address} due to: \n{ce}")
        print(F"Error connecting to {link_address}\n")
        refs_log.error(F"{pmc_id} - Error connecting to {link_address}")
    except Exception as ex:
        logging.error(
            F"Unexpected error occurred for article {pmc_id}, downloading: {link_address}\n{ex}")
        print(F"{pmc_id} error downloading {link_address}\n")
        refs_log.error(F"{pmc_id} - error downloading {link_address}")
    return False


def download_supplementary_files(supp_links, new_dir, pmc_id):
    for link in supp_links:
        link_address = link.attrib['href']
        if "www." not in link_address and "http" not in link_address:
            link_address = F"https://www.ncbi.nlm.nih.gov{link.attrib['href']}"
        download_supplementary_file(link_address, new_dir, pmc_id)


def get_supp_docs(input_directory, bioc_file, pmc_bioc, is_id=False):
    pmc_id = get_formatted_pmcid(bioc_file, is_id)
    response = get_article_links(pmc_id)
    if response.ok:
        supp_links = etree.HTML(response.text).xpath("//*[@id='data-suppmats']//a")
        supp_links = supp_links + etree.HTML(response.text).xpath("//div[@class='sup-box half_rhythm']/a["
                                                                  "@data-ga-action='click_feat_suppl']")
        if not supp_links:
            logging.info(F"{pmc_id} does not contain supplementary links.")
            no_supp_links.append(F"{pmc_id}")
        else:
            new_dir = input_directory + F"/{pmc_id}_supplementary" if input_directory else F"{pmc_id}_supplementary"
            try:
                if not exists(new_dir):
                    os.mkdir(new_dir)
            except IOError:
                logging.error(F"Unable to process {pmc_id}: Unable to create local directory.")
            download_supplementary_files(supp_links, new_dir, pmc_id)
    else:
        missing_html_files.append(F"{pmc_id}")
        return False
    if pmc_bioc:
        download_PMC_BioC(pmc_id, pmc_bioc, input_directory)
    return True


def output_problematic_logs():
    if no_supp_links:
        with open("NoSuppLinks.txt", "w", encoding="utf-8") as f_in:
            f_in.write("\n".join(no_supp_links))
    if missing_html_files:
        with open("NoArticleHtml.txt", "w", encoding="utf-8") as f_in:
            f_in.write("\n".join(missing_html_files))


def process_directory(input_directory, pmc_bioc=False):
    new_files = [x for x in os.listdir(input_directory) if isfile(join(input_directory, x))]
    for file in new_files:
        if ".json" not in file:
            continue
        logging.info(F"Processing file {file}")
        bioc_file = load_file(join(input_directory, file))
        result = get_supp_docs(input_directory, bioc_file, pmc_bioc)
        if not result:
            missing_html_files.append(F"{bioc_file.documents[0].id}")


def process_pmc_id(pmc_ids, pmc_bioc=False):
    for pmc_id in pmc_ids.split(","):
        logging.info(F"Processing {pmc_id}")
        directory = ""
        result = get_supp_docs(directory, pmc_id, pmc_bioc, True)
        if not result:
            missing_html_files.append(F"{pmc_id}")
        if pmc_bioc:
            download_PMC_BioC(pmc_id, pmc_bioc)


def process_pmc_id_file(id_file, pmc_bioc=False):
    logging.info(F"Processing {id_file}")
    try:
        with open(id_file, "r") as in_file:
            for line in in_file:
                process_pmc_id(line.strip())
            if pmc_bioc:
                download_PMC_BioC(line.strip(), pmc_bioc)
    except FileNotFoundError as fnfe:
        logging.error(fnfe)
        sys.exit(F"File not found: {id_file}")
    except Exception as ex:
        logging.error(ex)
        sys.exit(F"An exception occurred: \n{ex}")

# to be used by external scripts
def download_doc_pmc_id(pmc_id, dir_out, pmc_bioc='json'):
    logging.info(F"Processing {pmc_id}")
    directory = dir_out
    result = get_supp_docs(directory, pmc_id, pmc_bioc, True)
    if not result:
        return False
    if pmc_bioc:
        download_PMC_BioC(pmc_id, pmc_bioc, dir_out)
    return True

def download_PMC_BioC(pmc_id, pmc_bioc='json', input_directory=False):
    try:
        response = requests.get(
            f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_{pmc_bioc}/{pmc_id}/unicode")
        if response.ok:
            if not os.path.exists("BioC") and not input_directory:
                os.mkdir("BioC")
            with open(f"{input_directory if input_directory else 'BioC'}/{pmc_id}.{pmc_bioc}", "w") as outfile:
                outfile.write(response.text)
    except Exception as ex:
        logging.error(ex)


def process_file(input_file):
    logging.info(F"Processing file {input_file}")
    bioc_file = load_file(input_file)
    directory = input_file[:str(input_file).rfind("/")] if "/" in input_file else ""
    result = get_supp_docs(directory, bioc_file)
    if not result:
        missing_html_files.append(F"{bioc_file.documents[0].id}")


def random_delay(lower=4, upper=10):
    sleep(random.randint(lower, upper))


def load_file(input_path):
    try:
        with open(input_path, "r", encoding="utf-8") as f_in:
            input_file = biocjson.load(f_in)
        return input_file
    except FileNotFoundError as fnfe:
        logging.error(fnfe)
        sys.exit(F"File not found: {input_path}")
    except Exception as ex:
        logging.error(ex)
        sys.exit(F"An exception occurred: \n{ex}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--input_file", type=str,
                        help="path to file containing PMC ids, one id per line")
    parser.add_argument("-d", "--input_directory", type=str,
                    help="input directory path, directory should contain bioc files")
    parser.add_argument("-l", "--input_list", type=str,
                    help="list of comma separated PMC ids")
    parser.add_argument("-b", "--PMC_BioC", type=str, help="if provided BioC files will be downloaded from PMC in the specified format and saved")
    args = parser.parse_args()
    if args.input_directory:
        process_directory(args.input_directory, args.PMC_BioC)
    if args.input_file:
        process_pmc_id_file(args.input_file, args.PMC_BioC)
    if args.input_list:
        process_pmc_id(args.input_list, args.PMC_BioC)
    output_problematic_logs()


if __name__ == "__main__":

    main()
