from collections import Counter
from concurrent.futures.process import ProcessPoolExecutor
from operator import itemgetter, attrgetter

from tqdm import tqdm
from typing import NamedTuple, Tuple, Iterator, Optional, List

from epics.domain import PlayerItem
from epics.player import PlayerService


class Roster(NamedTuple):
    rfl: PlayerItem
    snp: PlayerItem
    ent: PlayerItem
    sup: PlayerItem
    flx: PlayerItem


class GetRosterPowerTask:
    country_bonus = {1: 0, 2: 4, 3: 11, 4: 24, 5: 49}
    team_bonus = {1: 0, 2: 4, 3: 11}

    def get_efficiency_bonus(self, roster: Roster) -> Optional[int]:
        rf, sn, sp, fr, flx = roster.rfl, roster.snp, roster.sup, roster.ent, roster.flx

        team_counter = Counter([rf.team_name, sn.team_name, sp.team_name, fr.team_name, flx.team_name])
        if team_counter.most_common(1)[0][1] > 3:
            return None

        country_counter = Counter([rf.country, sn.country, sp.country, fr.country, flx.country])
        team_efficiency = sum((self.team_bonus[t] for t in team_counter.values()))
        country_efficiency = sum((self.country_bonus[c] for c in country_counter.values()))

        return team_efficiency + country_efficiency

    def __call__(self, roster: Roster) -> Tuple[str, Optional[float]]:
        rf, sn, sp, fr, flx = roster.rfl, roster.snp, roster.sup, roster.ent, roster.flx
        team_key = ','.join((f'{p.template_title}({p.player_rating})' for p in
                             sorted([rf, sn, sp, fr, flx], key=attrgetter('player_id'))))

        bonus = self.get_efficiency_bonus(roster)
        if bonus is None:
            return team_key, None

        pwr = sum((p.player_rating for p in [rf, sn, sp, fr, flx])) * (1.0 + bonus / 100.0)
        return team_key, pwr


class TeamService:

    def __init__(self) -> None:
        self.p_service = PlayerService()

    def get_rosters(self) -> List[Tuple[str, float]]:
        with ProcessPoolExecutor() as executor:
            return sorted({key: pwr for key, pwr
                           in executor.map(GetRosterPowerTask(), tqdm(list(self.get_roster_iter())), chunksize=10)
                           if pwr is not None}.items(),
                          key=itemgetter(1))

    def get_roster_iter(self) -> Iterator[Roster]:
        rfl, snp, ent, sup, flx = self.get_role_rosters((75, 75, 75, 65, 75))
        for r in list(rfl.values()):
            for s in list(snp.values()):
                for e in list(ent.values()):
                    for sp in list(sup.values()):
                        for f in list(flx.values()):
                            salary = r.salary + s.salary + e.salary + sp.salary + f.salary
                            if (f.player_id not in {r.player_id, s.player_id, sp.player_id, e.player_id}
                                    and salary <= 45000):
                                yield Roster(r, s, e, sp, f)

    def get_role_rosters(self, min_ratings: Tuple[int, int, int, int, int]):
        rfl, snp, ent, sup, flx = {}, {}, {}, {}, {}
        for p in list(self.p_service.get_owned().values()):
            if p.role_id == 46 and p.player_rating >= min_ratings[0]:
                if p.player_id not in rfl or rfl[p.player_id].player_rating < p.player_rating:
                    rfl[p.player_id] = p
            if p.role_id == 48 and p.player_rating >= min_ratings[1]:
                if p.player_id not in snp or snp[p.player_id].player_rating < p.player_rating:
                    snp[p.player_id] = p
            if p.role_id == 49 and p.player_rating >= min_ratings[2]:
                if p.player_id not in ent or ent[p.player_id].player_rating < p.player_rating:
                    ent[p.player_id] = p
            if p.role_id == 47 and p.player_rating >= min_ratings[3]:
                if p.player_id not in sup or sup[p.player_id].player_rating < p.player_rating:
                    sup[p.player_id] = p
            if p.player_rating >= min_ratings[4]:
                if p.player_id not in flx or flx[p.player_id].player_rating < p.player_rating:
                    flx[p.player_id] = p

        return rfl, snp, ent, sup, flx

    def print_rosters(self):
        for r, p in self.get_rosters()[-100:]:
            print(f'{r}: {p:.2f}')


team = TeamService()
