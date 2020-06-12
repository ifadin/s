from unittest import TestCase

from csgo.contract import STItemReturnCalc
from csgo.price import STPriceManager
from csgo.test.utils import get_avg_price_entry
from csgo.type.contract import ItemReturn
from csgo.type.float import FloatRange
from csgo.type.item import Item, ItemCollection, ItemCondition
from csgo.type.price import PriceTimeRange, get_market_name


class CalculateTest(TestCase):
    ItemA5 = Item('item5', 5, 'A')
    ItemA4_1 = Item('item4-1', 4, 'A')
    ItemA4_2 = Item('item4-2', 4, 'A')
    ItemA3_1 = Item('item3-1', 3, 'A')
    ItemA3_2 = Item('item3-2', 3, 'A')
    ItemA3_3 = Item('item3-3', 3, 'A')
    ItemA2_1 = Item('item2-1', 2, 'A')
    ItemA2_2 = Item('item2-2', 2, 'A')
    ItemA2_3 = Item('item2-3', 2, 'A')
    ItemA2_4 = Item('item2-4', 2, 'A')
    ItemB4_1 = Item('item4b-1', 4, 'B')
    ItemB4_2 = Item('item4b-2', 4, 'B', min_float=0.1, max_float=0.6)
    ItemB3_1 = Item('item3b-1', 3, 'B')
    collections = {
        'A': ItemCollection('A', [
            ItemA5,
            ItemA4_1,
            ItemA4_2,
            ItemA3_1,
            ItemA3_2,
            ItemA3_3,
            ItemA2_1,
            ItemA2_2,
            ItemA2_3,
            ItemA2_4
        ]),
        'B': ItemCollection('B', [
            ItemB4_1,
            ItemB4_2,
            ItemB3_1
        ])
    }
    time_range: PriceTimeRange = PriceTimeRange[PriceTimeRange.DAYS_30.name]
    prices = {
        get_market_name('item5', ItemCondition.FACTORY_NEW): get_avg_price_entry(time_range, 1000),
        get_market_name('item4-1', ItemCondition.FACTORY_NEW): get_avg_price_entry(time_range, 100),
        get_market_name('item4-2', ItemCondition.FACTORY_NEW): get_avg_price_entry(time_range, 200),

        get_market_name('item5', ItemCondition.WELL_WORN): get_avg_price_entry(time_range, 100),
        get_market_name('item4-1', ItemCondition.WELL_WORN): get_avg_price_entry(time_range, 10),
        get_market_name('item4-2', ItemCondition.WELL_WORN): get_avg_price_entry(time_range, 20),

        get_market_name('item4-1', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(time_range, 800),
        get_market_name('item4-2', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(time_range, 400),
        get_market_name('item3-2', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(time_range, 50),

        get_market_name('item4b-1', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(time_range, 500),
        get_market_name('item4b-2', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(time_range, 300),
        get_market_name('item3b-1', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(time_range, 80),

        get_market_name('item4b-1', ItemCondition.FIELD_TESTED): get_avg_price_entry(time_range, 300),
        get_market_name('item4b-2', ItemCondition.FIELD_TESTED): get_avg_price_entry(time_range, 200),

        get_market_name('item4b-1', ItemCondition.WELL_WORN): get_avg_price_entry(time_range, 25),
        get_market_name('item4b-2', ItemCondition.WELL_WORN): get_avg_price_entry(time_range, 20),

        get_market_name('item4b-1', ItemCondition.BATTLE_SCARED): get_avg_price_entry(time_range, 15),
        get_market_name('item4b-2', ItemCondition.BATTLE_SCARED): get_avg_price_entry(time_range, 10),
        get_market_name('item3b-1', ItemCondition.BATTLE_SCARED): get_avg_price_entry(time_range, 5)
    }
    price_manager = STPriceManager(prices, collections)

    def test_get_item_conversion_return(self):
        calc = STItemReturnCalc(self.collections, self.price_manager)
        standard_float_return = calc.get_item_returns(self.ItemA3_2, self.time_range)
        expected = [
            ItemReturn(self.ItemA3_2, ItemCondition.MINIMAL_WEAR, 500, 600, FloatRange(0.07, 0.15),
                       guaranteed=False,
                       output_items={'item4-1 (Minimal Wear)': 800, 'item4-2 (Minimal Wear)': 400})]
        self.assertEqual(standard_float_return, expected)

        calc = STItemReturnCalc(self.collections, self.price_manager, possible_price_discount=0)
        limited_float_return = calc.get_item_returns(self.ItemB3_1, self.time_range)

        expected = [
            ItemReturn(self.ItemB3_1, ItemCondition.BATTLE_SCARED, 50, 107.5, FloatRange(0.45, 0.56),
                       guaranteed=False,
                       output_items={'item4b-1 (Battle-Scarred)': 15, 'item4b-2 (Field-Tested)': 200}),
            ItemReturn(self.ItemB3_1, ItemCondition.BATTLE_SCARED, 50, 17.5, FloatRange(0.56, 0.7),
                       guaranteed=False,
                       output_items={'item4b-1 (Battle-Scarred)': 15, 'item4b-2 (Well-Worn)': 20}),
            ItemReturn(self.ItemB3_1, ItemCondition.BATTLE_SCARED, 50, 12.5, FloatRange(0.7, 1),
                       guaranteed=False,
                       output_items={'item4b-1 (Battle-Scarred)': 15, 'item4b-2 (Battle-Scarred)': 10}),
            ItemReturn(self.ItemB3_1, ItemCondition.MINIMAL_WEAR, 800, 400, FloatRange(0.07, 0.09999999999999998),
                       guaranteed=False,
                       output_items={'item4b-1 (Minimal Wear)': 500, 'item4b-2 (Minimal Wear)': 300}),
            ItemReturn(self.ItemB3_1, ItemCondition.MINIMAL_WEAR, 800, 350, FloatRange(0.09999999999999998, 0.15),
                       guaranteed=False,
                       output_items={'item4b-1 (Minimal Wear)': 500, 'item4b-2 (Field-Tested)': 200})]

        self.assertEqual(limited_float_return, expected)
