
## Install

```shell script
    python3 -m venv .venv
    source setup.rc
    python -m pip install -r epics/requirements.txt 
```

## Update

```shell script
    python -c 'from epics.update import updater; updater.update_teams()'
    python -c 'from epics.update import updater_a; updater_a.update_roster()'

    python -c 'from epics.calculate import calculator; calculator.calculate_lineups_efficiency()'
    python -c "from epics.calculate import calculator; calculator.get_team_performance(rarity_upper_limit='Very Rare')"
    python -c 'from epics.team import team_a; team_a.print_rosters()'
    
    python -m epics.cli update 2020 0
    python -m epics.cli track
    python -m epics.cli items 60
    python -m epics.cli goal
```
