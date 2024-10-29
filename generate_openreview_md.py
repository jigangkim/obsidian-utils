from datetime import datetime
import requests
import re


# Regular expression to check if OpenReview ID is valid
OPENREVIEW_ID = re.compile(r'^[\w-]+$')


def is_valid(openreview_id):
    """Checks if ID resembles a valid OpenReview identifier."""
    return bool(OPENREVIEW_ID.match(openreview_id))

class Reference:
    """Represents a single reference from OpenReview."""
    def __init__(self, json_data):
        self.json_data = json_data
        self.id = json_data['id']
        self.title = json_data['content']['title']['value']
        self.authors = json_data['content']['authors']['value']
        # self.tldr = json_data['content']['TLDR']['value'] # This isn't always present
        self.summary = json_data['content']['abstract']['value']
        self.pdf_url = f"https://openreview.net{json_data['content']['pdf']['value']}"
        self.url = f"https://openreview.net/forum?id={json_data['forum']}"
        self.pub_date = json_data.get('pdate', '')
        self.venueid = json_data['content']['venueid']['value']
        if not self.id or not self.authors or not self.title:
            raise Exception("No such publication")

    def citation_key(self):
        """Generate a citation key based on authors and year."""
        author_last_names = [name.split()[-1].lower() for name in self.authors]
        year = datetime.fromtimestamp(self.pub_date / 1000).year if self.pub_date else "YYYY"
        first_word = self.title.lower().split()[0].replace(":", "") if self.title else ""
        return f"{author_last_names[0]}{year}{first_word}"

    def to_dict(self):
        """Convert reference to a dictionary."""
        return {
            "key": self.citation_key(),
            "author": " and ".join(self.authors),
            "title": self.title,
            "eprint": self.id,
            "url": self.url,
            # "tldr": self.tldr,
            "summary": self.summary,
            "pubdate": datetime.fromtimestamp(self.pub_date / 1000).strftime("%Y-%m-%d") if self.pub_date else '',
            "venue": self.venueid.split('/')[0],
        }

def openreview_request(ids):
    """Sends a request to the OpenReview API."""
    url = "https://api2.openreview.net/notes"
    params = {
        "id": ids,
        "details": "all"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()  # Raise an error for bad responses
    data = response.json()
    return data['notes']  # Return the list of notes

def openreview2bib_dict(id_list):
    """Fetches citations for ids in id_list into a dictionary indexed by id."""
    results = {}

    # Validate ids
    for id in id_list:
        if is_valid(id):
            try:
                notes = openreview_request(id)
                if notes:
                    ref = Reference(notes[0])  # Use the first note returned
                    results[id] = ref.to_dict()
                else:
                    results[id] = {"error": "No notes found"}
            except Exception as error:
                results[id] = {"error": str(error)}
        else:
            results[id] = {"error": "Invalid OpenReview identifier"}

    return results

def fetch_bibtex(ids):
    """Fetch BibTeX entries for a list of OpenReview IDs."""
    return openreview2bib_dict(ids)

def generate_markdown_file(metadata):
    # Remove unnecessary spaces and newlines
    title = ' '.join(metadata['title'].split())
    # summary = f'tldr; {metadata["tldr"]} abstract; {metadata['summary']}'
    summary = metadata['summary']
    summary = ' '.join(summary.split())

    # Wrap in quotes if it contains colons
    title = f'"{title.replace('"', '')}"' if ':' in title else title
    summary = f'"{summary.replace('"', '')}"' if ':' in summary else summary

    now = datetime.now()
    date_added = now.strftime("%Y-%m-%d (%a)")

    content = \
f'''---
title: {title}
authors: {metadata['author']}
tldr: {summary}
venue: OpenReview
date_published: {metadata['pubdate']}
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

def download_pdf(openreview_id, filename):
    pdf_url = f"https://openreview.net/pdf?id={openreview_id}"
    response = requests.get(pdf_url)
    
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded: {filename}")
    else:
        print(f"Failed to download PDF: {response.status_code}")

def run(entries):
    # Links should be in the format https://openreview.net/pdf?id=<paper identifier>, https://openreview.net/forum?id=<paper identifier>
    paper_ids = [entry.split('id=')[-1] for entry in entries]
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