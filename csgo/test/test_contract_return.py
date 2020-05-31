from unittest import TestCase

from csgo.contract import calculate_trade_contract_return, get_contract_candidates
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
    ItemB4_2 = Item('item4b-2', 4, 'B')
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
