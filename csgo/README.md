# Update prices

```shell script
  http "http://csgobackpack.net/api/GetItemsList/v2/?no_details=true&currency=RUB" > csgo/bck_prices.json
```

```shell script
  http "https://api.hexa.one/market/prices/730?key=<api_key>" > csgo/hexa_prices.json
```

```shell script
  http "https://loot.farm/fullprice.json" > csgo/lf_sales.json
  http "https://loot.farm/botsInventory_730.json" > csgo/lf_prices.json
```

## Data sources

https://github.com/cs-idb/cs-idb/blob/master/data