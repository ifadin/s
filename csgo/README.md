# Update prices

```shell script
  http "http://csgobackpack.net/api/GetItemsList/v2/?no_details=true&currency=RUB" > csgo/bck_prices.json
```

```shell script
  yarn install
  HEXA_API_KEY=<api_key> node csgo/t.js
```

## Data sources

https://github.com/cs-idb/cs-idb/blob/master/data/paintkits.json