import os
from collections import Counter
from concurrent.futures.process import ProcessPoolExecutor
from operator import itemgetter

from tqdm import tqdm
from typing import Dict, List, Iterable, Tuple, Optional, NamedTuple

from epics.auth import EAuth
from epics.domain import Rating, Player, Team, get_player_ratings, load_teams, load_collections
from epics.pack import load_packs, PackService

Lineup = Tuple[Player, Player, Player, Player, Player]
SimpleLineup = Tuple[str, str, str, str, str]

PlayerRatingsMap = Dict[str, Dict[str, List[int]]]
LineupRating = Tuple[int, int, int, int, int]

LINEUP_FILE_PATH = os.path.join('epics', 'data', 'lineups.csv')


class TeamRoster(NamedTuple):
    roster: SimpleLineup
    efficiency: int


class TeamPerformance(NamedTuple):
    roster: SimpleLineup
    ratings: LineupRating
    efficiency: int
    performance: float


class GetEfficiencyTask:
    country_bonus = {1: 0, 2: 4, 3: 11, 4: 24, 5: 49}
    team_bonus = {1: 0, 2: 4, 3: 11}

    def __call__(self, team: Lineup) -> Tuple[str, Optional[int]]:
        rf, sn, sp, fr, flx = team
        core_names = [rf.name, sn.name, sp.name, fr.name]
        team_key = ','.join(core_names + [flx.name])

        if flx.name in core_names:
            return team_key, None

        team_counter = Counter([rf.team_name, sn.team_name, sp.team_name, fr.team_name, flx.team_name])
        if team_counter.most_common(1)[0][1] > 3:
            return team_key, None

        country_counter = Counter([rf.country, sn.country, sp.country, fr.country, flx.country])
        team_efficiency = sum((self.team_bonus[t] for t in team_counter.values()))
        country_efficiency = sum((self.country_bonus[c] for c in country_counter.values()))

        return team_key, team_efficiency + country_efficiency


class Calculator:

    def __init__(self, auth: EAuth) -> None:
        self.auth = auth
        self.pack_service = PackService(load_collections(), load_packs(), self.auth)

    def calculate_lineups_efficiency(self, output_file_path: str = LINEUP_FILE_PATH):
        teams = load_teams()
        batches = list(self.get_lineups_combinations(teams))
        with ProcessPoolExecutor() as executor:
            with open(output_file_path, 'w') as f:
                for b in tqdm(batches):
                    for key, eff in executor.map(GetEfficiencyTask(), tqdm(b), chunksize=10):
                        if eff is not None and eff > 30:
                            f.write(f'{key},{eff}\n')
                    f.flush()

    @staticmethod
    def get_role_players(teams: Dict[str, Team]) -> Dict[int, List[Player]]:
        roles = {}
        for t in teams.values():
            for p in t.players.values():
                if p.role_id not in roles:
                    roles[p.role_id] = []
                roles[p.role_id].append(p)
        return roles

    @classmethod
    def get_lineups_combinations(cls, teams: Dict[str, Team]) -> Iterable[Iterable[Lineup]]:
        roles = cls.get_role_players(teams)
        rflrs, snprs, spprts, frgrs = roles[46], roles[48], roles[47], roles[49]
        flex = rflrs + snprs + spprts + frgrs
        return (((rf, sn, sp, fr, flx)
                 for rf in rflrs
                 for sn in snprs
                 for fr in frgrs
                 for flx in flex) for sp in spprts)

    @classmethod
    def get_player_ratings_by_rarity(cls, player_ratings: Dict[str, List[Rating]],
                                     sample_size: int = 5) -> PlayerRatingsMap:
        ratings_map = {}
        for p, ratings in player_ratings.items():
            if p not in ratings_map:
                ratings_map[p] = {}
            for r in ratings:
                if r.rarity not in ratings_map[p]:
                    ratings_map[p][r.rarity] = []
                if r.rating not in ratings_map[p][r.rarity]:
                    ratings_map[p][r.rarity] = sorted(ratings_map[p][r.rarity] + [r.rating],
                                                      reverse=True)[0:sample_size]
        return ratings_map

    @staticmethod
    def load_team_rosters(file_path: str = LINEUP_FILE_PATH) -> List[TeamRoster]:
        rosters = []
        with open(file_path) as f:
            for line in f:
                entries = line.split(',')
                rosters.append(
                    TeamRoster((entries[0], entries[1], entries[2], entries[3], entries[4]), int(entries[5])))
        return rosters

    @classmethod
    def get_lineup_ratings_simple(cls,
                                  roster: SimpleLineup,
                                  player_ratings: PlayerRatingsMap,
                                  rarity_upper_limit: str,
                                  sample_size: int) -> Iterable[LineupRating]:
        def get_rating(player_index: int, rating_index: int):
            return (roster_best_ratings[player_index][rating_index]
                    if rating_index < len(roster_best_ratings[player_index])
                    else roster_best_ratings[player_index][0])

        roster_best_ratings = [
            cls.get_player_best_ratings(player_ratings[pl], rarity_upper_limit, sample_size)
            for pl in roster
        ]
        return ((get_rating(0, rating_index),
                 get_rating(1, rating_index),
                 get_rating(2, rating_index),
                 get_rating(3, rating_index),
                 get_rating(4, rating_index))
                for rating_index in range(0, sample_size))

    @classmethod
    def get_lineup_ratings_exhaustive(cls,
                                      roster: SimpleLineup,
                                      player_ratings: PlayerRatingsMap,
                                      rarity_upper_limit: str,
                                      sample_size: int) -> Iterable[LineupRating]:
        roster_best_ratings = [
            cls.get_player_best_ratings(player_ratings[pl], rarity_upper_limit, sample_size)
            for pl in roster
        ]
        return (
            (pos1_r, pos2_r, pos3_r, pos4_r, pos5_r)
            for pos1_r in roster_best_ratings[0]
            for pos2_r in roster_best_ratings[1]
            for pos3_r in roster_best_ratings[2]
            for pos4_r in roster_best_ratings[3]
            for pos5_r in roster_best_ratings[4]
        )

    @classmethod
    def get_min_rating_salary(cls, rating: int, ratings: List[Rating], rarity_upper_limit: str) -> int:
        return min(r.salary for r in ratings if r.rating == rating and
                   cls.rarity_order[r.rarity] <= cls.rarity_order[rarity_upper_limit])

    @classmethod
    def get_player_best_ratings(cls,
                                ratings_map: Dict[str, List[int]],
                                rarity_upper_limit: str,
                                sample_size: int = 5) -> List[int]:
        accepted_ratings = []
        for rarity, ratings in ratings_map.items():
            if cls.rarity_order[rarity] <= cls.rarity_order[rarity_upper_limit]:
                accepted_ratings.extend(ratings)
        return sorted(list(set(accepted_ratings)), reverse=True)[0:sample_size]

    def get_team_performance(self, results_amount: int = 100,
                             rarity_upper_limit: str = 'Ultra Rare',
                             sample_size: int = 10):
        teams = load_teams()
        player_ratings = get_player_ratings(teams)
        ratings_by_rarity = self.get_player_ratings_by_rarity(player_ratings, sample_size)
        team_rosters = self.load_team_rosters()

        best_result = 0
        top_results = []
        for r in tqdm(team_rosters):
            for l_rating in self.get_lineup_ratings_exhaustive(r.roster, ratings_by_rarity, rarity_upper_limit,
                                                               sample_size):
                perf = sum(l_rating) / 5 * (1 + r.efficiency / 100)
                if perf > best_result:
                    best_result = perf
                    top_results.append(TeamPerformance(r.roster, l_rating, r.efficiency, perf))
                    if len(top_results) > results_amount:
                        top_results = top_results[-results_amount:]

        for res in reversed(top_results):
            salaries = tuple(
                self.get_min_rating_salary(res.ratings[i], player_ratings[res.roster[i]], rarity_upper_limit)
                for i in range(0, 5)
            )
            salary = sum(salaries)
            roster_name = ' | '.join(f'{res.roster[i]}({res.ratings[i]} {salaries[i]})' for i in range(0, 5))
            print(f'{salary} {roster_name} {res.performance:.2f} ({res.efficiency}%)')

    rarity_order = {
        'Abundant': 0, 'Rare': 1, 'Very Rare': 2, 'Super Rare': 3, 'Ultra Rare': 4, 'Limited': 5, 'Unique': 6, 'N/A': 10
    }

    def get_packs_roi(self):
        packs = self.pack_service.packs
        market_packs = self.pack_service.get_market_packs()
        res = sorted([
            (p, packs[p.id], packs[p.id].exp - p.price)
            for p in market_packs if p.id in packs
        ], key=itemgetter(2))

        for m, p, diff in res:
            if diff > 0:
                print(f'{self.pack_service.get_item_url(m.id)} {p.name} {m.price} {p.exp:.2f} ({diff:.2f})')
