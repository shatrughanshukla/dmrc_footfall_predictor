"""
Line-topology-aware travel time graph, used by routes.py in place of the old
dmrc_all_station_travel_times.csv (straight-line haversine between every
pair of stations, ~48.5k rows for permutations that mostly aren't reachable
without changing lines).

See network_topology.py for what data was missing and why the old approach
had no alternative but straight-line distance.

Node = (station, line) e.g. ("Rajiv Chowk", "Yellow Line"). This
"line-expanded" graph is what lets us charge an interchange penalty only
when a route actually switches platforms/lines, instead of moving for free
between lines that happen to share a station name.
"""
import math
import heapq
import csv
from collections import defaultdict

from app.network_topology import (
    LINES, INTERCHANGES, INTERCHANGE_PENALTY_MIN, DEFAULT_SEGMENT_MIN, ALIASES,
)

AVG_SPEED_KMH = 32.0  # DMRC's published average commercial speed (incl. dwell)
MAX_SEGMENT_MIN = 8.0  # ~4.3 km -- beyond this between *adjacent* stations, the coordinate is almost certainly wrong, not the track
_STRIP_CHARS = "†‡*#¤"


def _normalize(name):
    name = "".join(ch for ch in name if ch not in _STRIP_CHARS)
    return (
        name.strip().lower()
        .replace("–", "-").replace("—", "-").replace("−", "-")
        .replace(",", "").replace(".", "").replace("  ", " ")
    )


def _load_stations(csv_path):
    """Returns {normalized_name: (canonical_name, lat, lon)}."""
    stations = {}
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = "".join(ch for ch in row["Station"].strip() if ch not in _STRIP_CHARS).strip()
            lat = row["Latitude"].strip()
            lon = row["Longitude"].strip()
            lat = float(lat) if lat else None
            lon = float(lon) if lon else None
            stations[_normalize(name)] = (name, lat, lon)
    return stations


def _is_placeholder_coord(lat, lon, coord_counts):
    """Flags coordinates that are obviously a stuck/default value rather than
    a real geocode -- the exact same (lat, lon) recurring across more than 2
    stations (e.g. every Noida Sector X station sharing one point)."""
    if lat is None or lon is None:
        return True
    return coord_counts[(lat, lon)] > 2


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _match_topology_to_canonical(stations):
    mapping = {}
    all_topology_names = set()
    for stops in LINES.values():
        all_topology_names.update(stops)
    all_topology_names.update(INTERCHANGES.keys())

    for name in all_topology_names:
        norm = _normalize(name)
        if norm in stations:
            mapping[name] = stations[norm][0]
            continue
        alias = ALIASES.get(norm)
        if alias and _normalize(alias) in stations:
            mapping[name] = stations[_normalize(alias)][0]
    return mapping


def build_graph(csv_path):
    """Builds the line-expanded graph: {(station, line): {(station, line): minutes}}."""
    stations = _load_stations(csv_path)
    mapping = _match_topology_to_canonical(stations)

    coord_counts = defaultdict(int)
    for _, lat, lon in stations.values():
        if lat is not None and lon is not None:
            coord_counts[(lat, lon)] += 1

    graph = defaultdict(dict)

    for line, stops in LINES.items():
        canon_stops = [mapping.get(s) for s in stops]
        for a, b in zip(canon_stops, canon_stops[1:]):
            if a is None or b is None:
                continue
            _, lat1, lon1 = stations[_normalize(a)]
            _, lat2, lon2 = stations[_normalize(b)]
            if not _is_placeholder_coord(lat1, lon1, coord_counts) and \
               not _is_placeholder_coord(lat2, lon2, coord_counts):
                weight = max((_haversine_km(lat1, lon1, lat2, lon2) / AVG_SPEED_KMH) * 60, 1.0)
                if weight > MAX_SEGMENT_MIN:
                    # Real adjacent DMRC stations are essentially never this
                    # far apart (even the longest suburban stretches run
                    # ~3-4 km). A haversine result this large means the
                    # coordinate itself is wrong -- not a duplicate
                    # placeholder (already caught above), just a bad,
                    # unique-looking value -- e.g. "Hindon" in the source
                    # data sits ~22 km north of its actual neighbours
                    # Shaheed Sthal and Arthala. Fall back rather than trust it.
                    weight = DEFAULT_SEGMENT_MIN
            else:
                weight = DEFAULT_SEGMENT_MIN
            graph[(a, line)][(b, line)] = weight
            graph[(b, line)][(a, line)] = weight

    for station, lines_here in INTERCHANGES.items():
        canon = mapping.get(station)
        if canon is None:
            continue
        line_list = list(lines_here)
        for i in range(len(line_list)):
            for j in range(i + 1, len(line_list)):
                na, nb = (canon, line_list[i]), (canon, line_list[j])
                graph[na][nb] = INTERCHANGE_PENALTY_MIN
                graph[nb][na] = INTERCHANGE_PENALTY_MIN

    return graph


def shortest_times_from(graph, station_name):
    """Multi-source Dijkstra from every line-node of `station_name` (a station
    with two lines starts the search from both). Returns
    {destination_station_name: minutes}, using whichever line gets there
    fastest and automatically paying the interchange penalty when a route
    needs to switch lines."""
    start_nodes = [n for n in graph if n[0] == station_name]
    dist = {n: 0.0 for n in start_nodes}
    pq = [(0.0, n) for n in start_nodes]
    heapq.heapify(pq)
    visited = set()

    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        for v, w in graph[u].items():
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(pq, (nd, v))

    best_per_station = {}
    for (station, _line), d in dist.items():
        if station not in best_per_station or d < best_per_station[station]:
            best_per_station[station] = d
    best_per_station.pop(station_name, None)
    return best_per_station
