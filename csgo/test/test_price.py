from unittest import TestCase

from csgo.price import get_item_price_name, PriceManager
from csgo.test.utils import get_avg_price_entry
from csgo.type.item import Item, ItemCollection, ItemCondition, ItemRarity
from csgo.type.price import PriceTimeRange


class CalculateTest(TestCase):
    collections = {'test': ItemCollection('test', [
        Item('item5', 5, 'test'),
        Item('item4-1', 4, 'test'),
        Item('item4-2', 4, 'test'),
        Item('item3-1', 3, 'test'),
        Item('item3-2', 3, 'test'),
        Item('item3-3', 3, 'test'),
        Item('item2-1', 2, 'test'),
        Item('item2-2', 2, 'test'),
        Item('item2-3', 2, 'test'),
        Item('item2-4', 2, 'test')
    ])}
    time_range: PriceTimeRange = PriceTimeRange[PriceTimeRange.DAYS_30.name]

    def test_get_item_price_name(self):
        name = get_item_price_name('item-1', ItemCondition.BATTLE_SCARED)

        self.assertEqual(name, 'item-1 (Battle-Scarred)')

    def test_price_approximation_top_level_item(self):
        prices = {
            get_item_price_name('item5', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 1000),
            get_item_price_name('item4-1', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 100),
            get_item_price_name('item4-2', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 200),

            get_item_price_name('item5', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 100),
            get_item_price_name('item4-1', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 10),
            get_item_price_name('item4-2', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 20),

            get_item_price_name('item4-1', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 500),
            get_item_price_name('item4-2', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 250),

            get_item_price_name('item4-1', ItemCondition.BATTLE_SCARED): get_avg_price_entry(self.time_range, 27),
            get_item_price_name('item4-2', ItemCondition.BATTLE_SCARED): get_avg_price_entry(self.time_range, 37)

        }

        item_condition = ItemCondition.MINIMAL_WEAR
        price_manager = PriceManager(prices, self.collections)
        price = price_manager.get_approx_price(
            Item('item5', 5, 'test'), item_condition, self.time_range)
        self.assertEqual(price, (10 * 500 + 5 * 250) / 2)

        item_condition = ItemCondition.BATTLE_SCARED
        price = price_manager.get_approx_price(
            Item('item5', 5, 'test'), item_condition, self.time_range)
        self.assertEqual(price, (10 * 27 + 5 * 37) / 2)

    def test_price_approximation_lowest_level_item(self):
        prices = {
            get_item_price_name('item2-4', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 100),
            get_item_price_name('item3-1', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 200),
            get_item_price_name('item3-2', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 400),
            get_item_price_name('item3-3', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 500),

            get_item_price_name('item2-4', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 10),
            get_item_price_name('item3-1', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 20),
            get_item_price_name('item3-2', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 40),
            get_item_price_name('item3-3', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 50),

            get_item_price_name('item3-1', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 500),
            get_item_price_name('item3-2', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 250),
            get_item_price_name('item3-3', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 320)
        }
        item_condition = ItemCondition.MINIMAL_WEAR
        price_manager = PriceManager(prices, self.collections)
        price = price_manager.get_approx_price(Item('item2-4', 2, 'test'), item_condition, self.time_range)
        self.assertEqual(price, (0.5 * 500 + 0.25 * 250 + 0.2 * 320) / 3)

    def test_price_approximation_mid_level_item(self):
        prices = {
            get_item_price_name('item5', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 1000),
            get_item_price_name('item4-1', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 800),
            get_item_price_name('item3-1', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 200),
            get_item_price_name('item3-2', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 400),
            get_item_price_name('item3-3', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 100),

            get_item_price_name('item5', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 600),
            get_item_price_name('item4-1', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 400),
            get_item_price_name('item3-1', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 30),
            get_item_price_name('item3-2', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 20),
            get_item_price_name('item3-3', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 10),

            get_item_price_name('item5', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 550),
            get_item_price_name('item3-1', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 125),
            get_item_price_name('item3-2', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 250),
            get_item_price_name('item3-3', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 320)
        }
        item_condition = ItemCondition.MINIMAL_WEAR
        price_manager = PriceManager(prices, self.collections)
        price = price_manager.get_approx_price(
            Item('item4-1', 4, 'test'), item_condition, self.time_range)
        self.assertAlmostEqual(price, (
                550 * (800 / 1000 + 400 / 600) / 2 +
                125 * (800 / 200 + 400 / 30) / 2 +
                250 * (800 / 400 + 400 / 20) / 2 +
                320 * (800 / 100 + 400 / 10) / 2) / 4)

    def test_price_approximation_with_missing_reference_info(self):
        prices = {
            get_item_price_name('item5', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 1000),
            get_item_price_name('item4-1', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 800),
            get_item_price_name('item3-3', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 100),

            get_item_price_name('item4-1', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 400),
            get_item_price_name('item3-1', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 30),
            get_item_price_name('item3-2', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 20),
            get_item_price_name('item3-3', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 10),

            get_item_price_name('item5', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 550),
            get_item_price_name('item3-1', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 125),
            get_item_price_name('item3-2', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 250),
            get_item_price_name('item3-3', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 320)
        }
        item_condition = ItemCondition.MINIMAL_WEAR
        price_manager = PriceManager(prices, self.collections)
        price = price_manager.get_approx_price(
            Item('item4-1', 4, 'test'), item_condition, self.time_range)
        self.assertAlmostEqual(price, (
                550 * (800 / 1000) +
                125 * (400 / 30) +
                250 * (400 / 20) +
                320 * (800 / 100 + 400 / 10) / 2) / 4)

    def test_price_approximation_with_missing_level_info(self):
        prices = {
            get_item_price_name('item5', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 1000),
            get_item_price_name('item4-1', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 800),
            get_item_price_name('item3-3', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 100),

            get_item_price_name('item4-1', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 400),
            get_item_price_name('item3-1', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 30),
            get_item_price_name('item3-2', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 20),
            get_item_price_name('item3-3', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 10),

            get_item_price_name('item5', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 550),
            get_item_price_name('item3-3', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 320)
        }
        item_condition = ItemCondition.MINIMAL_WEAR
        price_manager = PriceManager(prices, self.collections)
        price = price_manager.get_approx_price(
            Item('item4-1', 4, 'test'), item_condition, self.time_range)
        self.assertAlmostEqual(price, (
                550 * (800 / 1000) +
                320 * (800 / 100 + 400 / 10) / 2) / 2)

    def test_condition_increase_ratios(self):
        prices = {
            get_item_price_name('item5', ItemCondition.BATTLE_SCARED): get_avg_price_entry(self.time_range, 100),
            get_item_price_name('item5', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 500),
            get_item_price_name('item5', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 900),
            get_item_price_name('item5', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 1000),

            get_item_price_name('item4-1', ItemCondition.BATTLE_SCARED): get_avg_price_entry(self.time_range, 30),
            get_item_price_name('item4-1', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 90),
            get_item_price_name('item4-2', ItemCondition.BATTLE_SCARED): get_avg_price_entry(self.time_range, 20),
            get_item_price_name('item4-2', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 40),
            get_item_price_name('item4-2', ItemCondition.FIELD_TESTED): get_avg_price_entry(self.time_range, 60),

            get_item_price_name('item2-1', ItemCondition.BATTLE_SCARED): get_avg_price_entry(self.time_range, 20),
            get_item_price_name('item2-2', ItemCondition.FIELD_TESTED): get_avg_price_entry(self.time_range, 60),
            get_item_price_name('item2-2', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 80)
        }

        price_manager = PriceManager(prices, self.collections)
        expected = {
            ItemRarity.COVERT: {
                ItemCondition.BATTLE_SCARED: 100 / 500,
                ItemCondition.MINIMAL_WEAR: 900 / 1000},
            ItemRarity.CLASSIFIED: {
                ItemCondition.BATTLE_SCARED: (30 / 90 + 20 / 40) / 2,
                ItemCondition.WELL_WORN: 40 / 60},
            ItemCondition.FIELD_TESTED: {
                ItemCondition.FIELD_TESTED: 60 / 80}
        }

        self.assertEqual(price_manager.condition_increase_ratios, expected)

    def test_approx_price_by_rarity(self):
        prices = {
            get_item_price_name('item5', ItemCondition.BATTLE_SCARED): get_avg_price_entry(self.time_range, 100),
            get_item_price_name('item5', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 500),
            get_item_price_name('item5', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 900),
            get_item_price_name('item5', ItemCondition.FACTORY_NEW): get_avg_price_entry(self.time_range, 1000),

            get_item_price_name('item4-1', ItemCondition.BATTLE_SCARED): get_avg_price_entry(self.time_range, 30),
            get_item_price_name('item4-1', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 90),
            get_item_price_name('item4-2', ItemCondition.BATTLE_SCARED): get_avg_price_entry(self.time_range, 20),
            get_item_price_name('item4-2', ItemCondition.WELL_WORN): get_avg_price_entry(self.time_range, 40),
            get_item_price_name('item4-2', ItemCondition.FIELD_TESTED): get_avg_price_entry(self.time_range, 60),

            get_item_price_name('item2-1', ItemCondition.BATTLE_SCARED): get_avg_price_entry(self.time_range, 20),
            get_item_price_name('item2-2', ItemCondition.FIELD_TESTED): get_avg_price_entry(self.time_range, 60),
            get_item_price_name('item2-2', ItemCondition.MINIMAL_WEAR): get_avg_price_entry(self.time_range, 80)
        }

        price_manager = PriceManager(prices, self.collections)

        self.assertEqual(price_manager.get_approx_price_from_rarity(
            Item('item4-1', 4, 'test'), ItemCondition.FIELD_TESTED, self.time_range), 90 / (40 / 60))
