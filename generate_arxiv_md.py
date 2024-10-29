from datetime import datetime
from xml.etree import ElementTree

import requests
import re
import os

from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError


# Namespaces
ATOM = '{http://www.w3.org/2005/Atom}'
ARXIV = '{http://arxiv.org/schemas/atom}'

# Regular expressions to check if arxiv id is valid
NEW_STYLE = re.compile(r'^\d{4}\.\d{4,}(v\d+)?$')
OLD_STYLE = re.compile(r"""(?x)
^(
   math-ph
  |hep-ph
  |nucl-ex
  |nucl-th
  |gr-qc
  |astro-ph
  |hep-lat
  |quant-ph
  |hep-ex
  |hep-th
  |stat
    (\.(AP|CO|ML|ME|TH))?
  |q-bio
    (\.(BM|CB|GN|MN|NC|OT|PE|QM|SC|TO))?
  |cond-mat
    (\.(dis-nn|mes-hall|mtrl-sci|other|soft|stat-mech|str-el|supr-con))?
  |cs
    (\.(AR|AI|CL|CC|CE|CG|GT|CV|CY|CR|DS|DB|DL|DM|DC|GL|GR|HC|IR|IT|LG|LO|
      MS|MA|MM|NI|NE|NA|OS|OH|PF|PL|RO|SE|SD|SC))?
  |nlin
    (\.(AO|CG|CD|SI|PS))?
  |physics
    (\.(acc-ph|ao-ph|atom-ph|atm-clus|bio-ph|chem-ph|class-ph|comp-ph|
      data-an|flu-dyn|gen-ph|geo-ph|hist-ph|ins-det|med-ph|optics|ed-ph|
      soc-ph|plasm-ph|pop-ph|space-ph))?
  |math
      (\.(AG|AT|AP|CT|CA|CO|AC|CV|DG|DS|FA|GM|GN|GT|GR|HO|IT|KT|LO|MP|MG
      |NT|NA|OA|OC|PR|QA|RT|RA|SP|ST|SG))?
)/\d{7}(v\d+)?$""")


def is_valid(arxiv_id):
    """Checks if id resembles a valid arxiv identifier."""
    return bool(NEW_STYLE.match(arxiv_id)) or bool(OLD_STYLE.match(arxiv_id))

class Reference(object):
    """Represents a single reference."""
    def __init__(self, entry_xml):
        self.xml = entry_xml
        self.url = self._field_text('id')
        self.id = self._id()
        self.authors = self._authors()
        self.title = self._field_text('title')
        if len(self.id) == 0 or len(self.authors) == 0 or len(self.title) == 0:
            raise Exception("No such publication")
        self.summary = self._field_text('summary')
        self.category = self._category()
        self.year, self.month = self._published()
        self.pub_date = self._field_text('published')
        self.updated = self._field_text('updated')
        self.bare_id = self.id[:self.id.rfind('v')]
        self.note = self._field_text('journal_ref', namespace=ARXIV)
        self.doi = self._field_text('doi', namespace=ARXIV)

    def _authors(self):
        """Extracts author names from xml."""
        xml_list = self.xml.findall(ATOM + 'author/' + ATOM + 'name')
        return [field.text for field in xml_list]

    def _field_text(self, id, namespace=ATOM):
        """Extracts text from arbitrary xml field"""
        try:
            return self.xml.find(namespace + id).text.strip()
        except:
            return ""

    def _category(self):
        """Get category"""
        try:
            return self.xml.find(ARXIV + 'primary_category').attrib['term']
        except:
            return ""

    def _id(self):
        """Get arxiv id"""
        try:
            id_url = self._field_text('id')
            return id_url[id_url.find('/abs/') + 5:]
        except:
            return ""

    def _published(self):
        """Get published date"""
        published = self._field_text('published')
        if len(published) < 7:
            return "", ""
        y, m = published[:4], published[5:7]
        return y, m

    def citation_key(self):
        """Generate a citation key based on authors and year."""
        author_last_names = [name.split()[-1].lower() for name in self.authors]
        year = self.year
        title_words = self.title.lower().split()  # Split title into words

        # Get the first word of the title
        first_word = title_words[0].replace(":", "") if title_words else ""  # Handle case where title might be empty
        
        # Construct the key: "firstauthoryearfirstwordoftitle"
        key = f"{author_last_names[0]}{year}{first_word}"
        return key

    def to_dict(self):
        """Convert reference to a dictionary."""
        return {
            "key": self.citation_key(),
            "author": " and ".join(self.authors),
            "title": self.title,
            "eprint": self.id,
            "archivePrefix": "arXiv",
            "primaryClass": self.category,
            "year": self.year,
            "month": self.month,
            "pubdate": self.pub_date,
            "doi": self.doi,
            "url": self.url,
            "note": self.note,
            "summary": self.summary,
        }

def arxiv_request(ids):
    """Sends a request to the arxiv API."""
    q = urlencode([("id_list", ",".join(ids)), ("max_results", len(ids))])
    xml = urlopen("http://export.arxiv.org/api/query?" + q)
    return ElementTree.fromstring(xml.read())

def arxiv2bib_dict(id_list):
    """Fetches citations for ids in id_list into a dictionary indexed by id"""
    ids = []
    results = {}

    # Validate ids
    for id in id_list:
        if is_valid(id):
            ids.append(id)
        else:
            results[id] = {"error": "Invalid arXiv identifier"}

    if len(ids) == 0:
        return results

    # Make the API call
    xml = arxiv_request(ids)

    # Parse each reference and store it in dictionary
    entries = xml.findall(ATOM + "entry")
    for id, entry in zip(id_list, entries):
        try:
            ref = Reference(entry)
            results[id] = ref.to_dict()
        except Exception as error:
            results[id] = {"error": str(error)}

    return results

def fetch_bibtex(ids):
    """Fetch BibTeX entries for a list of arXiv IDs."""
    return arxiv2bib_dict(ids)

def generate_markdown_file(metadata):
    # Remove unnecessary spaces and newlines
    title = ' '.join(metadata['title'].split())
    summary = ' '.join(metadata['summary'].split())

    # Wrap in quotes if it contains colons
    title = f'"{title.replace('"', '')}"' if ':' in title else title
    summary = f'"{summary.replace('"', '')}"' if ':' in summary else summary

    # Get the current date and format it
    now = datetime.now()
    date_added = now.strftime("%Y-%m-%d (%a)")
    date_published = datetime.strptime(metadata['pubdate'], "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")

    content = \
f'''---
title: {title}
authors: {metadata['author']}
tldr: {summary}
venue: arXiv
date_published: {date_published}
rating: 0/5
date_added: {date_added}
url: {metadata['url']}
links: 
tags:
---
> [!notes] Notes
> Summary, Quotes, Thoughts, Questions, etc.

---
# PDF

![[{metadata['key']}.pdf]]'''
    
    return content

def download_pdf(arxiv_id, filename):
    pdf_url = f"http://arxiv.org/pdf/{arxiv_id}.pdf"
    response = requests.get(pdf_url)
    
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded: {filename}")
    else:
        print(f"Failed to download PDF: {response.status_code}")

def run(entries):
    # Links should be in the format https://arxiv.org/pdf/<paper identifier>, https://arxiv.org/abs/<paper identifier>
    paper_ids = [entry.split('/')[-1] for entry in entries]
    bibtex_db = fetch_bibtex(paper_ids)
    
    for paper_id in paper_ids:
        metadata = bibtex_db[paper_id]
        with open(f"{metadata['key']}.md", "w") as f:
            f.write(generate_markdown_file(metadata))
        download_pdf(paper_id, f"{metadata['key']}.pdf")


if __name__ == "__main__":
    # Read URLs from links.txt
    with open('links.txt', 'r') as file:
        entries = [line.strip() for line in file if line.strip()]  # Read lines and strip whitespace
    
    run(entries)