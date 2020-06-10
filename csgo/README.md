# Update prices

```shell script
  http "http://csgobackpack.net/api/GetItemsList/v2/?no_details=true&currency=RUB" > csgo/bck_prices.json
```

```shell script
  http "https://api.hexa.one/market/prices/730?key=<api_key>" > csgo/hexa_prices.json
```

```shell script
  set -a && source .env && set +a
  http "$(echo "aHR0cHM6Ly9sb290LmZhcm0vZnVsbHByaWNlLmpzb24=" | base64 -d)" > csgo/lf_sales.json
  http "$(echo "aHR0cHM6Ly9sb290LmZhcm0vYm90c0ludmVudG9yeV83MzAuanNvbg==" | base64 -d)" > csgo/lf_prices.json
  http "$(echo "aHR0cHM6Ly9sb290LmZhcm0vZ2V0SW52X25ldy5waHA/Z2FtZT03MzA=" | base64 -d)" cookie:"PHPSESSID=$LF_SESSION_ID" > csgo/lf/lf_inv.json
  http "$(echo "aHR0cHM6Ly9sb290LmZhcm0vZ2V0UmVzZXJ2ZXMucGhw" | base64 -d)" cookie:"PHPSESSID=$LF_SESSION_ID" > csgo/lf/lf_rsv.json
```

## Data sources

https://github.com/cs-idb/cs-idb/blob/master/data