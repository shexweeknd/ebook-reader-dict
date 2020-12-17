"""Parse and store raw Wiktionary data."""
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, Generator, Tuple
from xml.etree import ElementTree
from xml.etree.ElementTree import Element


def xml_iter_parse(file: str) -> Generator[Element, None, None]:
    """Efficient XML parsing for big files.
    Elements are yielded when they meet the "page" tag.
    """

    doc = ElementTree.iterparse(file, events=("start", "end"))
    _, root = next(doc)

    start_tag = None

    for event, element in doc:
        if (
            start_tag is None
            and event == "start"
            and element.tag == "{http://www.mediawiki.org/xml/export-0.10/}page"
        ):
            start_tag = element.tag
        elif start_tag is not None and event == "end" and element.tag == start_tag:
            yield element
            start_tag = None

            # Keep memory low
            root.clear()


def xml_parse_element(element: Element) -> Tuple[str, str]:
    """Parse the *element* to retrieve the word and its definitions."""
    revision = element[3]
    if revision.tag == "{http://www.mediawiki.org/xml/export-0.10/}restrictions":
        # When a word is "restricted", then the revision comes just after
        revision = element[4]
    elif not revision:
        # This is a "redirect" page, not interesting.
        return "", ""

    # The Wikicode can be at different indexes, but not ones lower than 5
    for info in revision[5:]:
        if info.tag == "{http://www.mediawiki.org/xml/export-0.10/}text":
            code = info.text or ""
            break
    else:
        # No Wikicode, maybe an unfinished page.
        return "", ""

    word = element[0].text or ""  # title
    return word, code


def process(filename: str, locale: str) -> Dict[str, str]:
    """Process the big XML file and retain only information we are interested in."""
    words: Dict[str, str] = defaultdict(str)

    print(f">>> Processing {filename} ...", flush=True)
    for element in xml_iter_parse(filename):
        word, code = xml_parse_element(element)
        if not word or not code or ":" in word:
            continue
        words[word] = code

    return words


def save(snapshot: str, words: Dict[str, str], output_dir: Path) -> None:
    """Persist data."""
    raw_data = output_dir / f"data_wikicode-{snapshot}.json"
    with raw_data.open(mode="w", encoding="utf-8") as fh:
        json.dump(words, fh, indent=4, sort_keys=True)

    print(f">>> Saved {len(words):,} words into {raw_data}", flush=True)


def get_latest_xml_file(locale: str, output_dir: Path) -> str:
    """Get the name of the last pages-*.xml file."""
    files = list(output_dir.glob("pages-*.xml"))
    return str(sorted(files)[-1]) if files else ""


def main(locale: str) -> int:
    """Entry point."""
    output_dir = Path(os.getenv("CWD", "")) / "data" / locale
    filename = get_latest_xml_file(locale, output_dir)
    if not filename:
        print(">>> No dump found. Run with --download first ... ", flush=True)
        return 1

    date = filename.split(".")[0].split("-")[1]
    if not (output_dir / f"data_wikicode-{date}.json").is_file():
        words = process(filename, locale)
        save(date, words, output_dir)
    print(">>> Parse done!", flush=True)
    return 0