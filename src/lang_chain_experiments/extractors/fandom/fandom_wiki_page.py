import json
from fandom import FandomPage


class FandomWikiPage:
    def __init__(self, page: FandomPage, page_name: str, categories: [str], info_box):
        self.wiki = page.wiki
        self.page_name = page_name
        self.page_url = page.url
        self.page_title = page.title
        self.revision_id = page.revision_id
        self.page_id = page.pageid
        self.content = page.content
        self.categories = categories
        self.info_box = info_box

    def to_json(self):
        """Convert the FandomWikiPage object to a JSON string."""
        return json.dumps(self.__dict__, indent=4)

    @classmethod
    def from_json(cls, json_str):
        """Load a FandomWikiPage object from a JSON string."""
        data = json.loads(json_str)
        page = cls.__new__(cls)
        page.__dict__.update(data)
        return page

    def save_to_file(self, file_path):
        """Save the FandomWikiPage object to a JSON file."""
        with open(file_path, 'w') as f:
            f.write(self.to_json())

    @classmethod
    def load_from_file(cls, file_path):
        """Load a FandomWikiPage object from a JSON file."""
        with open(file_path, 'r') as f:
            json_str = f.read()
        return cls.from_json(json_str)
