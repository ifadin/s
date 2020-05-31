const hexaone = require('hexa.one');
const api = new hexaone(process.env.HEXA_API_KEY);
const fs = require('fs');


(async () => {
    try {
        const prices = await api.getPrices(730);
        fs.writeFileSync('csgo/hexa_prices.json', JSON.stringify(prices));
    } catch (err) {
        console.log(err);
    }
})();