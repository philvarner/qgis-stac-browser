import re
from urllib.parse import urlparse
from .collection import Collection
from .link import Link
from .search_result import SearchResult
from ..utils import network

class API: 
    def __init__(self, json=None):
        self._json = json
        self._data = self._json.get('data', None)
        self._collections = [Collection(self, c) for c in self._json.get('collections', [])]

    def load(self):
        self._data = network.request(f'{self.href}/stac')
        self._collections = [self.load_collection(c) for c in self.collection_ids]

    def load_collection(self, collection_id):
        return Collection(self, network.request(f'{self.href}/collections/{collection_id}'))

    def search_items(self, collections=[], bbox=[], start_time=None,
                     end_time=None, page=1, limit=50, on_next_page=None):
        if on_next_page is not None:
            on_next_page(self)

        if end_time is None:
            time = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            time = f'{start_time.strftime("%Y-%m-%dT%H:%M:%SZ")}/{end_time.strftime("%Y-%m-%dT%H:%M:%SZ")}'

        body = {
                    'collections': [c.id for c in collections],
                    'bbox': bbox,
                    'time': time,
                    'page': page,
                    'limit': limit
               }
    
        search_result = SearchResult(self, network.request(f'{self.href}/stac/search', data=body))
        
        items = search_result.items
        if len(items) >= limit:
            items.extend(self.search_items(collections, bbox, start_time, end_time, page+1, limit, on_next_page=on_next_page))

        return items
     
    def collection_id_from_href(self, href):
        p = re.compile('\/collections\/(.*)')
        m = p.match(urlparse(href).path)
        if m is None:
            return None

        if m.groups() is None:
            return None

        return m.groups()[0]

    @property
    def json(self):
        return {
                    'href': self.href,
                    'data': self.data,
                    'collections': [c.json for c in self.collections],
                }

    @property
    def title(self):
        return self.data.get('title', None)

    @property
    def href(self):
        return self._json.get('href', None)

    @property
    def data(self):
        return self._data

    @property
    def links(self):
        return [Link(l) for l in self.data.get('links', [])]

    @property
    def collection_ids(self):
        collection_ids = []
        p = re.compile('\/collections\/(.*)')

        for link in self.links:
            m = p.match(urlparse(link.href).path)
            if m is None:
                continue

            if m.groups() is None:
                continue

            collection_ids.append(m.groups()[0])
        
        return collection_ids

    @property
    def collections(self):
        return self._collections
    
    def __lt__(self, other):
        return self.title.lower() < other.title.lower()
