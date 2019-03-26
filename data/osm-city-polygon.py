import copy
import csv
import json
from operator import itemgetter
from typing import List, Tuple, Set

import click
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


def get_id(element: dict) -> int:
    return itemgetter('id')(element)


def get_latitude(element: dict):
    return itemgetter('lat')(element)


def get_longitude(element: dict):
    return itemgetter('lon')(element)


def get_name(element: dict):
    return itemgetter('name')(itemgetter('tags')(element))


def get_type(element: dict):
    return itemgetter('type')(itemgetter('tags')(element))


def query_city_ids(api: API, out_file: str = None):
    query = 'rel["de:place"="city"]a'
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


def style_url(url: str):
    return click.style(url, fg='bright_blue')


def style_data(data):
    return click.style(str(data), fg='yellow')


def get_overpass_client(endpoint: str):
    return API(endpoint=endpoint) if endpoint else API()


def get_overpass_obj(ctx: dict):
    return ctx['overpass_api']


@click.group()
@click.option('--overpass-api', type=click.STRING)
@click.pass_context
def cli(ctx, overpass_api: str):
    ctx.ensure_object(dict)

    api = get_overpass_client(overpass_api)
    click.echo(f'Overpass API: {style_url(api.endpoint)}')
    ctx.obj['overpass_api'] = api


ISO_CODES_SHORTCUTS = {
    'Z_EU': {'AT', 'BE', 'CH', 'CZ', 'DE', 'DK', 'ES', 'FI', 'FR', 'GB', 'IE', 'IT', 'NL', 'NO', 'PL', 'PT', 'SE'}
}


def parse_iso_codes(iso_codes: Tuple) -> List[str]:
    codes = set(map(str.upper, iso_codes))
    validate_codes(codes)
    return sorted(parse_code_shortcuts(codes))


def validate_codes(codes: Set[str]):
    shortcuts = set(ISO_CODES_SHORTCUTS.keys())
    for c in codes:
        if len(c) != 2 and c not in shortcuts:
            raise ValueError(f'Code \'{c}\' is not in ISO format or from available shortcuts {shortcuts}')


def parse_code_shortcuts(codes_with_shortcuts: Set[str]) -> Set[str]:
    codes = copy.deepcopy(codes_with_shortcuts)
    for shortcut, value in ISO_CODES_SHORTCUTS.items():
        if shortcut in codes:
            codes.remove(shortcut)
            codes.update(value)

    return codes


def find_country_admin_center(code: str, api: API) -> Tuple[float, float]:
    query = f'rel["ISO3166-1"="{code}"];node(r:"admin_centre");'
    center = api.get(query, responseformat='json').get('elements', [])

    if len(center) != 1:
        raise ValueError(f'Could not detect admin center for country code {code}. Got response: {center}')

    return get_latitude(center[0]), get_longitude(center[0])


def find_country_boundary(code: str, use_land_area: bool, api: API) -> Tuple[int, str]:
    query = f'rel["ISO3166-1"="{code}"]'
    boundaries = api.get(query, responseformat='json').get('elements', [])

    if len(boundaries) == 0:
        raise ValueError(f'Could not find boundary for country code \'{code}\'')

    boundary = next((b for b in boundaries if get_type(b) == 'land_area'), boundaries[0]) \
        if use_land_area \
        else next((b for b in boundaries if get_type(b) != 'land_area'), None)

    if boundary is None:
        raise ValueError(f'Could not find boundary for country code \'{code}\'')

    return get_id(boundary), get_name(boundary)


def get_country_osm_relation(code: str, use_land_area: bool, api: API) -> dict:
    id, name = find_country_boundary(code, use_land_area, api)
    center_lat, center_lon = find_country_admin_center(code, api)

    return {'id': id, 'code': code, 'name': name, 'latitude': center_lat, 'longitude': center_lon}


def request_polygon(osm_id: int, poly_format: PolygonFormat):
    compute = requests.post(f'http://polygons.openstreetmap.fr/index.py?id={osm_id}',
                            data={} if poly_format == PolygonFormat.FULL else {
                                'x': poly_format.x, 'y': poly_format.y,
                                'z': poly_format.z
                            })
    compute.raise_for_status()

    return compute


def query_polygon(osm_id: int, poly_format: PolygonFormat, result_format='wkt') -> str:
    query = requests.get(
        f'http://polygons.openstreetmap.fr/get_{result_format}.py?id={osm_id}&params={poly_format.params}')
    query.raise_for_status()
    lines = query.text.strip().split(';')
    if len(lines) == 0:
        raise ValueError(f'Unknown response format: {query.text}')

    return lines[1] if len(lines) > 1 else lines[0]


def get_polygons(osm_id: int, formats: List[PolygonFormat], key_name='area') -> dict:
    polygon = {}
    for f in formats:
        request_polygon(osm_id, f)
        polygon[to_polygon_field_name(key_name, f)] = query_polygon(osm_id, f)
    return polygon


@cli.command(name='country', help='Convert OSM country')
@click.argument('iso_codes', type=click.STRING, nargs=-1, required=True)
@click.option('--full-boundary', is_flag=True, help='Use full country boundary (not only land area)')
@click.pass_context
def convert_country(ctx, iso_codes: Tuple, full_boundary: bool):
    codes = parse_iso_codes(iso_codes)
    click.echo(f'Countries: {style_data(codes)}')

    for code in codes:
        click.echo(f'Processing {style_data(code)}...')
        rel = get_country_osm_relation(code, not full_boundary, get_overpass_obj(ctx.obj))
        poly = get_polygons(rel['id'], [PolygonFormat.SIMPLE])
        click.echo(poly)


if __name__ == '__main__':
    cli()


def some():
    city_ids = load_city_ids('some.json')
    cities = enrich_with_polygon_info(city_ids, [PolygonFormat.BASIC, PolygonFormat.SIMPLE, PolygonFormat.FULL], 'area')
    save_to_csv('out.csv', cities, ['id', 'name',
                                    to_polygon_field_name('area', PolygonFormat.SIMPLE),
                                    to_polygon_field_name('area', PolygonFormat.BASIC),
                                    to_polygon_field_name('area', PolygonFormat.FULL)])
