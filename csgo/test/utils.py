from csgo.type.price import ItemPrice, PriceTimeRange, ItemPriceDetails


def get_avg_price_entry(time_range: PriceTimeRange, price: int) -> ItemPrice:
    return ItemPrice('', {time_range: ItemPriceDetails(price, 0)})