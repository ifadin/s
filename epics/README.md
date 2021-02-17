
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
    
    python -m epics.cli update -y 2020 2021 --cache 0
    python -m epics.cli track -m 0.3 --pps 1.0 -b 80
    while :; do python -m epics.cli upgrade -y 2020 --pps 1.0 -b 25 -l a r ; sleep 300; done
    python -m epics.cli goal
```
