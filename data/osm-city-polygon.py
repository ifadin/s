import csv
import json
from operator import itemgetter
from typing import List

import requests
from enum import Enum
from overpass import API


class PolygonFormat(Enum):
    FULL = ('full', 0, 0, 0)
    BASIC = ('basic', 0.004, 0.001, 0.001)
    SIMPLE = ('simple', 0.05, 0.05, 0.05)

    def __init__(self, name, x, y, z):
        self.desc = name
        self.x = x
        self.y = y
        self.z = z

    @property
    def params(self):
        return '0' if self.desc == 'full' else '{:.6f}-{:.6f}-{:.6f}'.format(self.x, self.y, self.z)


def get_from_file(file_path: str):
    with open(file_path, 'r') as f:
        return json.loads(f.read())


def get_id(element: dict):
    return itemgetter('id')(element)


def get_name(element: dict):
    return itemgetter('name')(itemgetter('tags')(element))


def query_city_ids(api: API, out_file: str = None):
    query = 'rel["de:place"="city"]'
    result = api.get(query, responseformat='json')
    if out_file:
        with open('some.json', 'w') as f:
            f.write(json.dumps(result))
    else:
        return result


def load_city_ids(source_file: str, query=False) -> List[dict]:
    if query:
        query_city_ids(API(), source_file)

    api_data = get_from_file(source_file)
    return sorted([{'id': get_id(e), 'name': get_name(e)} for e in api_data['elements']], key=itemgetter('name'))


def query_polygon(id: int, format: PolygonFormat):
    compute = requests.post(f'http://polygons.openstreetmap.fr/index.py?id={id}',
                            data={} if format == PolygonFormat.FULL else {'x': format.x, 'y': format.y, 'z': format.z})
    compute.raise_for_status()
    # print(f'REQUEST:\n{compute.request.headers}\n{compute.request.body}')
    # print(f'RESPONSE:\n{compute.headers}\n{compute.text}')

    query = requests.get(f'http://polygons.openstreetmap.fr/get_wkt.py?id={id}&params={format.params}')
    query.raise_for_status()
    lines = query.text.strip().split(';')
    if len(lines) == 0:
        raise ValueError(f'Unknown response format: {query.text}')

    return lines[1] if len(lines) > 1 else lines[0]


def enrich_with_polygon_info(cities: List[dict], formats: List[PolygonFormat], key_name: str) -> List[dict]:
    result = []
    for c in cities[1:3]:
        id = c['id']
        name = c['name']
        poly_info = {}
        for f in formats:
            print(f'Querying \'{f.desc}\' polygon info for {name} ({id})')
            poly_info[to_polygon_field_name(key_name, f)] = query_polygon(id, f)
        result.append({**c, **poly_info})
    return result


def save_to_csv(out_file: str, cities: List[dict], header=List[str]):
    with open(out_file, 'w', newline='') as csvfile:
        fieldnames = header
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for c in cities:
            writer.writerow(c)
    print(f'Saved to {out_file}')


def to_polygon_field_name(field: str, format: PolygonFormat):
    return f'{field}_{format.desc}'


countries = [('de', 51477)]

city_ids = load_city_ids('some.json')
cities = enrich_with_polygon_info(city_ids, [PolygonFormat.BASIC, PolygonFormat.SIMPLE, PolygonFormat.FULL], 'area')
save_to_csv('out.csv', cities, ['id', 'name',
                                to_polygon_field_name('area', PolygonFormat.SIMPLE),
                                to_polygon_field_name('area', PolygonFormat.BASIC),
                                to_polygon_field_name('area', PolygonFormat.FULL)])
