from unittest import TestCase

from csgo.contract import get_contract_candidates, calculate_trade_contract_return, \
    STContractCalc
from csgo.conversion import FloatRange
from csgo.price import STPriceManager
from csgo.test.utils import get_avg_price_entry
from csgo.type.contract import ItemReturn
from csgo.type.item import Item, ItemCollection, ItemCondition, ItemRarity
from csgo.type.price import PriceTimeRange, get_item_price_name


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
        get_item_price_name('item5', ItemCondition.FACTORY_NEW): get_avg_price_entry(time_range, 1000),
        get_item_price_name('item4-1', ItemCondition.FACTORY_NEW): get_avg_price_entry(time_range, 100),
        get_item_price_name('item4-2', ItemCondition.FACTORY_NEW): get_avg_price_entry(time_range, 200),

        get_item_price_name('item5', ItemCondition.WELL_WORN): get_avg_price_entry(time_range, 100),
        get_item_price_name('item4-1', ItemCondition.WELL_WORN): get_avg_price_entry(time_range, 10),
        get_item_price_name('item4-2', ItemCondition.WELL_WORN): get_avg_price_entry(time_range, 20),

        get_item_price_name('item4-1', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(time_range, 800),
        get_item_price_name('item4-2', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(time_range, 400),
        get_item_price_name('item3-2', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(time_range, 50),

        get_item_price_name('item4b-1', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(time_range, 500),
        get_item_price_name('item4b-2', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(time_range, 300),
        get_item_price_name('item3b-1', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(time_range, 80),

        get_item_price_name('item4b-1', ItemCondition.FIELD_TESTED): get_avg_price_entry(time_range, 300),
        get_item_price_name('item4b-2', ItemCondition.FIELD_TESTED): get_avg_price_entry(time_range, 200),

        get_item_price_name('item4b-1', ItemCondition.WELL_WORN): get_avg_price_entry(time_range, 25),
        get_item_price_name('item4b-2', ItemCondition.WELL_WORN): get_avg_price_entry(time_range, 20),

        get_item_price_name('item4b-1', ItemCondition.BATTLE_SCARED): get_avg_price_entry(time_range, 15),
        get_item_price_name('item4b-2', ItemCondition.BATTLE_SCARED): get_avg_price_entry(time_range, 10),
        get_item_price_name('item3b-1', ItemCondition.BATTLE_SCARED): get_avg_price_entry(time_range, 5)
    }
    price_manager = STPriceManager(prices, collections)

    def test_get_item_conversion_return(self):
        calc = STContractCalc(self.collections, self.price_manager)
        standard_float_return = calc.get_item_returns(self.ItemA3_2, self.time_range)
        expected = [
            ItemReturn(self.ItemA3_2, ItemCondition.MINIMAL_WEAR, 50, 60.0, FloatRange(0.07, 0.15),
                       guaranteed=False,
                       conversion_items={'item4-1 (Minimal Wear)': 800, 'item4-2 (Minimal Wear)': 400})]
        self.assertEqual(standard_float_return, expected)

        calc = STContractCalc(self.collections, self.price_manager, possible_price_discount=0)
        limited_float_return = calc.get_item_returns(self.ItemB3_1, self.time_range)

        expected = [
            ItemReturn(self.ItemB3_1, ItemCondition.BATTLE_SCARED, 5, 10.75, FloatRange(0.45, 0.56),
                       guaranteed=False,
                       conversion_items={'item4b-1 (Battle-Scarred)': 15, 'item4b-2 (Field-Tested)': 200}),
            ItemReturn(self.ItemB3_1, ItemCondition.BATTLE_SCARED, 5, 1.75, FloatRange(0.56, 0.7),
                       guaranteed=False,
                       conversion_items={'item4b-1 (Battle-Scarred)': 15, 'item4b-2 (Well-Worn)': 20}),
            ItemReturn(self.ItemB3_1, ItemCondition.BATTLE_SCARED, 5, 1.25, FloatRange(0.7, 1),
                       guaranteed=False,
                       conversion_items={'item4b-1 (Battle-Scarred)': 15, 'item4b-2 (Battle-Scarred)': 10}),
            ItemReturn(self.ItemB3_1, ItemCondition.MINIMAL_WEAR, 80, 40.0, FloatRange(0.07, 0.09999999999999998),
                       guaranteed=False,
                       conversion_items={'item4b-1 (Minimal Wear)': 500, 'item4b-2 (Minimal Wear)': 300}),
            ItemReturn(self.ItemB3_1, ItemCondition.MINIMAL_WEAR, 80, 35.0, FloatRange(0.09999999999999998, 0.15),
                       guaranteed=False,
                       conversion_items={'item4b-1 (Minimal Wear)': 500, 'item4b-2 (Field-Tested)': 200})]

        self.assertEqual(limited_float_return, expected)

    def test_get_contract_candidates(self):
        candidates = get_contract_candidates(self.price_manager, self.time_range)
        expected = {
            ItemCondition.BATTLE_SCARED: {
                ItemRarity.RESTRICTED: [self.ItemB3_1]},
            ItemCondition.MINIMAL_WEAR: {
                ItemRarity.RESTRICTED: [self.ItemB3_1, self.ItemA3_2],
                ItemRarity.CLASSIFIED: [self.ItemA4_2]},
            ItemCondition.WELL_WORN: {
                ItemRarity.CLASSIFIED: [self.ItemA4_1]},
            ItemCondition.FACTORY_NEW: {
                ItemRarity.CLASSIFIED: [self.ItemA4_1]}
        }
        self.assertEqual(candidates, expected)

    def test_contract_return_guaranteed(self):
        item_condition = ItemCondition.FACTORY_NEW
        buy_price_reduction = 0.8
        res = calculate_trade_contract_return(
            [(self.ItemA4_1, self.collections['A']) for _ in range(0, 10)], item_condition,
            self.price_manager, self.time_range,
            buy_price_reduction=buy_price_reduction)

        expected_investment = 10 * 100 * buy_price_reduction
        expected_return = 1000
        expected_revenue = expected_return - expected_investment
        expected_roi = expected_revenue / expected_investment

        self.assertEqual(res.contract_investment, expected_investment)
        self.assertEqual(res.contract_return, expected_return)
        self.assertEqual(res.contract_revenue, expected_revenue)
        self.assertEqual(res.contract_roi, expected_roi)
        self.assertEqual(res.guaranteed, True)

    def test_contract_return_multiple_outcomes(self):
        item_condition = ItemCondition.MINIMAL_WEAR
        buy_price_reduction = 0.5
        res = calculate_trade_contract_return(
            [(self.ItemA3_2, self.collections['A']) for _ in range(0, 10)], item_condition,
            self.price_manager, self.time_range,
            buy_price_reduction=buy_price_reduction)

        expected_investment = 10 * 50 * buy_price_reduction
        expected_return = (400 + 800) / 2
        expected_revenue = expected_return - expected_investment
        expected_roi = expected_revenue / expected_investment
        self.assertEqual(res.contract_investment, expected_investment)
        self.assertEqual(res.contract_return, expected_return)
        self.assertEqual(res.contract_revenue, expected_revenue)
        self.assertEqual(res.contract_roi, expected_roi)
        self.assertEqual(res.guaranteed, False)

    def test_contract_approx_return_multiple_collections(self):
        item_condition = ItemCondition.MINIMAL_WEAR

        buy_price_reduction = 0.5
        items = [(self.ItemA3_2, self.collections['A']) for _ in range(0, 3)] + [
            (self.ItemB3_1, self.collections['B']) for _ in range(0, 7)]
        res = calculate_trade_contract_return(items, item_condition,
                                              self.price_manager, self.time_range,
                                              buy_price_reduction=buy_price_reduction)

        expected_investment = (3 * 50 + 7 * 80) * buy_price_reduction
        expected_return = (400 + 800) * 0.3 / 2 + (500 + 300) * 0.7 / 2
        expected_revenue = expected_return - expected_investment
        expected_roi = expected_revenue / expected_investment
        self.assertEqual(res.contract_investment, expected_investment)
        self.assertEqual(res.contract_return, expected_return)
        self.assertEqual(res.contract_revenue, expected_revenue)
        self.assertEqual(res.contract_roi, expected_roi)
        self.assertEqual(res.guaranteed, False)
