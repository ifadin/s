from unittest import TestCase

from csgo.condition import ConditionRange, get_item_conversion_ranges, get_condition_from_float, \
    get_item_possible_conditions, get_item_condition_ranges, get_item_possible_conversions
from csgo.contract import calculate_trade_contract_return, get_contract_candidates, get_best_conversion_avg_price
from csgo.price import get_item_price_name, PriceManager
from csgo.test.utils import get_avg_price_entry
from csgo.type.item import Item, ItemCollection, ItemCondition, ItemRarity
from csgo.type.price import PriceTimeRange


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
    }
    price_manager = PriceManager(prices, collections)

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

    def test_contract_return_multiple_collections(self):
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

    def test_get_contract_candidates(self):
        candidates = get_contract_candidates(self.price_manager, self.time_range)
        expected = {
            ItemCondition.MINIMAL_WEAR: {
                ItemRarity.RESTRICTED: [self.ItemB3_1, self.ItemA3_2],
                ItemRarity.CLASSIFIED: [self.ItemA4_2]
            },
            ItemCondition.WELL_WORN: {
                ItemRarity.CLASSIFIED: [self.ItemA4_1]
            },
            ItemCondition.FACTORY_NEW: {
                ItemRarity.CLASSIFIED: [self.ItemA4_1]
            }
        }
        self.assertEqual(candidates, expected)

    def test_get_condition_from_float(self):
        self.assertEqual(get_condition_from_float(0.75), ItemCondition.BATTLE_SCARED)
        self.assertEqual(get_condition_from_float(0.45), ItemCondition.BATTLE_SCARED)
        self.assertEqual(get_condition_from_float(0.39), ItemCondition.WELL_WORN)
        self.assertEqual(get_condition_from_float(0.15), ItemCondition.FIELD_TESTED)
        self.assertEqual(get_condition_from_float(0.1), ItemCondition.MINIMAL_WEAR)
        self.assertEqual(get_condition_from_float(0.066), ItemCondition.FACTORY_NEW)

    def test_get_item_possible_conditions(self):
        item = Item('test', 4, 'test', min_float=0.1, max_float=0.4)
        conditions = get_item_possible_conditions(item)
        expected = [ItemCondition.WELL_WORN, ItemCondition.FIELD_TESTED, ItemCondition.MINIMAL_WEAR]

        self.assertEqual(conditions, expected)

    def test_get_item_condition_ranges(self):
        item = Item('test', 4, 'test', min_float=0.1, max_float=0.6)
        ranges = get_item_condition_ranges(item)
        expected = {
            ItemCondition.BATTLE_SCARED: ConditionRange(min_value=0.45, max_value=0.6),
            ItemCondition.WELL_WORN: ConditionRange(min_value=0.38, max_value=0.45),
            ItemCondition.FIELD_TESTED: ConditionRange(min_value=0.15, max_value=0.38),
            ItemCondition.MINIMAL_WEAR: ConditionRange(min_value=0.1, max_value=0.15)
        }

        self.assertEqual(ranges, expected)

    def test_get_item_conversion_ranges(self):
        item = Item('test', 4, 'test', min_float=0.1, max_float=0.6)
        ranges = get_item_conversion_ranges(item)
        expected = {
            ItemCondition.BATTLE_SCARED: ConditionRange(min_value=0.7, max_value=1),
            ItemCondition.WELL_WORN: ConditionRange(min_value=0.56, max_value=0.7),
            ItemCondition.FIELD_TESTED: ConditionRange(min_value=0.09999999999999998, max_value=0.56),
            ItemCondition.MINIMAL_WEAR: ConditionRange(min_value=0, max_value=0.09999999999999998)
        }

        self.assertEqual(ranges, expected)

    def test_get_item_possible_conversions(self):
        item = Item('test', 4, 'test', min_float=0, max_float=1)
        target_item = Item('target_test', 4, 'test', min_float=0.1, max_float=0.6)

        conversions = get_item_possible_conversions(item, ItemCondition.BATTLE_SCARED, target_item)
        expected = {ItemCondition.BATTLE_SCARED: 1, ItemCondition.WELL_WORN: 0.7, ItemCondition.FIELD_TESTED: 0.56}
        self.assertEqual(conversions, expected)

        conversions = get_item_possible_conversions(item, ItemCondition.MINIMAL_WEAR, target_item)
        expected = {ItemCondition.FIELD_TESTED: 0.56, ItemCondition.MINIMAL_WEAR: 0.09999999999999998}
        self.assertEqual(conversions, expected)

        conversions = get_item_possible_conversions(item, ItemCondition.FACTORY_NEW, target_item)
        expected = {ItemCondition.MINIMAL_WEAR: 0.09999999999999998}
        self.assertEqual(conversions, expected)

    def test_get_best_conversion_avg_price(self):
        prices_standard_float = get_best_conversion_avg_price(self.ItemA3_2, ItemCondition.MINIMAL_WEAR,
                                                              self.collections['A'], self.price_manager,
                                                              self.time_range)
        expected = [(800, 0.15), (400, 0.15)]
        self.assertEqual(prices_standard_float, expected)

        prices_custom_float = get_best_conversion_avg_price(self.ItemB3_1, ItemCondition.BATTLE_SCARED,
                                                            self.collections['B'], self.price_manager, self.time_range)
        expected = [(15, 1), (200, 0.56)]
        self.assertEqual(prices_custom_float, expected)
