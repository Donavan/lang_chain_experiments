import io
import re
import os
import uuid
import gzip
import fandom
import hashlib
import argparse
from fandom_wiki_page import FandomWikiPage
from bs4 import BeautifulSoup, NavigableString, Tag


class FandomWikiExtractor:
    def __init__(self):
        self.__init_regex()

    def __init_regex(self):
        this_is_about = r'This page is about the(.*?)For the(.*?)see(.*?)\.'
        citations = r'\[.*?\]'
        gender = r'♂|💓|♀'
        book_tv = r'\s*Books character\s*|\s*TV character\s*'
        # TODO: Allow passing extra/replacements in
        self.strip_regexes = [this_is_about, book_tv, citations, gender]

    # TODO: Make this possible to be a handler
    def __cleanse_text(self, text: str) -> str:
        text = text.replace("\n(", " (")

        for r in self.strip_regexes:
            text = re.sub(r, '', text, flags=re.IGNORECASE)

        return text.lstrip('\n').replace("\n\n", "\n").replace("\n,\n", "\n").replace("\n (", " (").strip()

    def __extract_text_from_div(self, soup):
        def extract_text_recursive(element):
            # Initialize an empty list to store the text from child elements
            texts = []
            # Iterate over each child element
            for child in element.children:
                # If the child is a NavigableString (text), add it to the list
                if isinstance(child, NavigableString):
                    texts.append(child.strip())
                # If the child is a Tag (HTML element), recursively extract its text
                elif isinstance(child, Tag):
                    texts.extend(extract_text_recursive(child))
            return texts

        # Extract text from the div element and its children
        all_texts = self.__cleanse_text('\n'.join(extract_text_recursive(soup)))
        return all_texts.replace("\n\n", "\n").split("\n")

    def __load_infobox(self, soup) -> [dict]:
        # Initialize an empty list to store the sections
        sections = []

        # Extract the first section name from the text of the first h2 element in the aside
        first_section_name = soup.find('h2', class_='pi-item pi-item-spacing pi-title pi-secondary-background').text.strip()

        # Extract the content for the first section (div elements before the section elements)
        first_section_content_divs = soup.find_all('div', class_='pi-item pi-data pi-item-spacing pi-border-color', recursive=False)

        # Create a dictionary for the first section content
        first_section_content = {}
        for div in first_section_content_divs:
            key = div.find('h3').text.strip().lower().replace("(es)", "es").replace("(s)", "s").replace(" ", "_")
            first_section_content[key] = self.__extract_text_from_div(div.find('div'))

        # Create a dictionary for the first section
        first_section_dict = {
            "section_name": first_section_name,
            "content": first_section_content
        }

        # Append the dictionary to the list of sections
        sections.append(first_section_dict)

        # Find all section elements and extract their content
        for section in soup.find_all('section', class_='pi-item pi-group pi-border-color'):
            # Extract the section name from the text of the h2 element
            section_name = section.find('h2').text.strip().replace("(es)", "es")

            # Extract the content for this section
            content_divs = section.find_all('div', class_='pi-item pi-data pi-item-spacing pi-border-color')
            content = {}
            for div in content_divs:
                key = div.find('h3').text.strip().lower().replace("(es)", "es").replace("(s)", "s").replace(" ", "_")
                content[key] = self.__extract_text_from_div(div.find('div'))

            # Create a dictionary for this section
            section_dict = {
                "section_name": section_name,
                "content": content
            }

            # Append the dictionary to the list of sections
            sections.append(section_dict)

        return sections

    @staticmethod
    def __compress_html(soup: BeautifulSoup):
        # Find and remove all <link> elements with rel="stylesheet"
        for link in soup.find_all('link', rel='stylesheet'):
            link.decompose()

        # Find and remove all <script> elements
        for script in soup.find_all('script'):
            script.decompose()

        # Compress the modified HTML content and return it as gzipped bytes
        with io.BytesIO() as bytes_io:
            with gzip.GzipFile(fileobj=bytes_io, mode='w') as gzip_file:
                gzip_file.write(str(soup).encode('utf-8'))
            gzipped_html = bytes_io.getvalue()
        return gzipped_html

    @staticmethod
    def __generate_uuid_from_seed(seed):
        # Hash the seed value using SHA-1
        hash_value = hashlib.sha1(seed.encode('utf-8')).hexdigest()

        # Convert the first 16 bytes of the hash to a UUID
        return str(uuid.UUID(hash_value[:32]))


    def __extract_additional_meta(self, section_uuid, data):
        # Split the content into lines
        lines = data['content'].split('\n')
        data['uuid'] = section_uuid
        # Initialize variables to store the extracted information
        main_article = None
        spoilers = []

        # Initialize a list to store the updated content
        updated_content = []

        # Iterate over each line in the content
        for line in lines:
            # Check if the line contains "Main article:"
            if "Main article:" in line:
                # Extract the title after the colon and strip leading/trailing whitespace
                main_article = line.split(':', 1)[1].strip()
            # Check if the line contains "Spoilers for:"
            elif "Spoilers for" in line:
                # Extract the spoilers after the colon and up to the word "follow"
                spoiler = line.split('Spoilers for', 1)[1].split('follow')[0].strip()
                # Append the extracted spoiler to the list of spoilers
                spoilers.append(spoiler)
            else:
                # If the line does not contain "Main article:" or "Spoilers for:", add it to the updated content
                updated_content.append(line)

        # Update the content in the dictionary
        data['content'] = '\n'.join(updated_content)

        # Add the extracted information to the dictionary
        if main_article is not None:
            data['main_article'] = main_article
        if spoilers:
            data['spoilers'] = spoilers

        return data

    def __update_section_meta(self, page, sections):
        # Iterate over each dictionary in the array and call the extract_info function
        for i, section in enumerate(sections):
            section_uuid = self.__generate_uuid_from_seed(page.url + section['title'].lower())
            # Update the current section using the extract_info function
            sections[i] = self.__extract_additional_meta(section_uuid, section)
            # Check if the current section has nested sections
            if 'sections' in section:
                # Call the update_page_content function recursively to update the nested sections
                sections[i]['sections'] = self.__update_section_meta(page, section['sections'])

        return sections

    def extract_wiki_page(self, wiki: str, page_name: str):
        fandom.set_wiki(wiki)
        page_name = page_name

        page = fandom.page(page_name)
        soup = BeautifulSoup(page.html, 'html.parser')

        page_uuid =  self.__generate_uuid_from_seed(page.url.lower())

        # Find all 'a' tags that link top the categories this page is in
        cat_links = soup.find_all('a', href=lambda href: href and "Category:" in href,
                                  attrs={'data-tracking-label': lambda label: label and label.startswith('categories-top')})

        info_box = self.__load_infobox(soup.find('aside', class_=lambda c: c and "infobox" in c))

        page_categories = []
        for cat_link in cat_links:
            page_categories.append(cat_link.text.lower())

        page_content = page.content

        sections = self.__update_section_meta(page, page_content.get('sections', []))

        page_content['sections'] = sections
        page_content['content'] = self.__cleanse_text(page_content['content'])

        return {'page': FandomWikiPage(page, page_name, page_categories, info_box), 'compressed_html': self.__compress_html(soup)}


def main():
    # Create an argument parser
    parser = argparse.ArgumentParser(description='Fetch wiki pages.')

    # Define the arguments
    parser.add_argument('--out', type=str, default='./', help='The output folder for the results (default: ./)')
    parser.add_argument('--wiki', type=str, required=True, help='The name of the wiki the pages belong to')
    parser.add_argument('--no-html', action='store_true', help='Do not save the compressed HTML')
    parser.add_argument('pages', type=str, nargs='+', help='One or more page names to fetch')

    # Parse the arguments
    args = parser.parse_args()

    # Ensure the output folder path ends with "/"
    output_folder = os.path.join(args.out, '')

    # Create an instance of the FandomExtractor class
    extractor = FandomWikiExtractor()

    # Fetch and save each wiki page
    for page_name in args.pages:
        # Extract the wiki page
        result = extractor.extract_wiki_page(args.wiki, page_name)
        json_filepath = os.path.join(output_folder, f'{page_name}.json')
        result['page'].save_to_file(json_filepath)

        # Save the compressed HTML to a gzip file
        if not args.no_html:
            gzip_filename = f'{page_name}.html.gz'
            gzip_filepath = os.path.join(output_folder, gzip_filename)
            with open(gzip_filepath, 'wb') as gzip_file:
                gzip_file.write(result['compressed_html'])


if __name__ == '__main__':
    main()
