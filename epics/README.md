
## Install

```shell script
    python3 -m venv .venv
    source setup.rc
    python -m pip install -r epics/requirements.txt 
```

## Update

```shell script
    python -c 'from epics.update import updater; updater.update_collections()'
    python -c 'from epics.update import updater; updater.update_teams()'

    python -c 'from epics.calculate import calculator; calculator.calculate_lineups_efficiency()'
    python -c "from epics.calculate import calculator; calculator.get_team_performance(rarity_upper_limit='Very Rare')"
    
    python -c "from epics.spin import spinner; spinner.start()"
    python -c "from epics.track import tracker; tracker.start(60)"
    python -c "from epics.game import fighter; fighter.start()"
```
