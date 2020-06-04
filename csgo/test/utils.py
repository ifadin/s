from csgo.type.price import STItemPrice, PriceTimeRange, STItemPriceDetails


def get_avg_price_entry(time_range: PriceTimeRange, price: int) -> STItemPrice:
    return STItemPrice('', {time_range: STItemPriceDetails(price, 0)})