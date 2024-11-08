from generate_arxiv_md import run as arxiv_runner
from generate_openreview_md import run as openreview_runner


if __name__ == "__main__":
    # Read URLs from links.txt
    with open('./outputs/links.txt', 'r') as file:
        entries = [line.strip() for line in file if line.strip()]  # Read lines and strip whitespace
    entries_arxiv = [entry for entry in entries if 'arxiv' in entry]
    entries_openreview = [entry for entry in entries if 'openreview' in entry]

    arxiv_runner(entries_arxiv)
    openreview_runner(entries_openreview)