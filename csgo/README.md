
## Install

```shell script
    python3 -m venv .venv
    source setup.rc
    pythron3 -m pip install -U -r requirements.txt 
```

## Update prices

```shell script
  http "http://csgobackpack.net/api/GetItemsList/v2/?no_details=true&currency=RUB" > csgo/bck_prices.json
```

```shell script
  http "https://api.hexa.one/market/prices/730?key=<api_key>" > csgo/hexa_prices.json
```

BS
```shell script
    python -c 'from csgo.update import update_bs_prices; update_bs_prices()'
    python -c 'from csgo.update import update_bs_sales; update_bs_sales()'
```

LF
```shell script
  http "$(echo "aHR0cHM6Ly9sb290LmZhcm0vZnVsbHByaWNlLmpzb24=" | base64 -d)" > csgo/lf/lf_sales.json
  http "$(echo "aHR0cHM6Ly9sb290LmZhcm0vYm90c0ludmVudG9yeV83MzAuanNvbg==" | base64 -d)" > csgo/lf/lf_prices.json
  http "$(echo "aHR0cHM6Ly9sb290LmZhcm0vYm90c0ludmVudG9yeV9BdWN0aW9ucy5qc29u" | base64 -d)" > csgo/lf/lf_auctions.json
  python -c 'from csgo.inventory import update_lf; update_lf()'
  http "$(echo "aHR0cHM6Ly9sb290LmZhcm0vZ2V0UmVzZXJ2ZXMucGhw" | base64 -d)" cookie:"PHPSESSID=$LF_SESSION_ID" > csgo/lf/lf_rsv.json
```

DM:
```shell script
    python -c 'from csgo.inventory import update_dm; update_dm()'
```

## Data sources

https://github.com/cs-idb/cs-idb/blob/master/data