from unittest import TestCase

from csgo.conversion import FloatRange, get_conversion_required_ranges, get_condition_from_float, \
    get_item_possible_conditions, get_item_condition_ranges, get_item_to_item_conversions
from csgo.type.item import Item, ItemCondition


class ConversionTest(TestCase):

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
            ItemCondition.BATTLE_SCARED: FloatRange(min_value=0.45, max_value=0.6),
            ItemCondition.WELL_WORN: FloatRange(min_value=0.38, max_value=0.45),
            ItemCondition.FIELD_TESTED: FloatRange(min_value=0.15, max_value=0.38),
            ItemCondition.MINIMAL_WEAR: FloatRange(min_value=0.1, max_value=0.15)
        }

        self.assertEqual(ranges, expected)

    def test_get_item_conversion_ranges(self):
        item = Item('test', 4, 'test', min_float=0.1, max_float=0.6)
        ranges = get_conversion_required_ranges(item)
        expected = {
            ItemCondition.BATTLE_SCARED: FloatRange(min_value=0.7, max_value=1),
            ItemCondition.WELL_WORN: FloatRange(min_value=0.56, max_value=0.7),
            ItemCondition.FIELD_TESTED: FloatRange(min_value=0.09999999999999998, max_value=0.56),
            ItemCondition.MINIMAL_WEAR: FloatRange(min_value=0, max_value=0.09999999999999998)
        }

        self.assertEqual(ranges, expected)

    def test_get_item_possible_conversion_with_left_inclusion(self):
        #   0 ---------------- 0.85 ----- 1
        #       0.45 --- 0.6
        item = Item('test', 0, 'test', max_float=0.6)
        target_item = Item('target_test', 0, 'test', min_float=0, max_float=0.08)

        conversions = get_item_to_item_conversions(item, ItemCondition.BATTLE_SCARED, target_item)
        expected = {
            ItemCondition.FACTORY_NEW: FloatRange(0.45, 0.6)
        }
        self.assertEqual(conversions, expected)

    def test_get_item_possible_conversion_with_right_inclusion(self):
        #   0 -----0.85 ------------- 1
        #               0.9 --- 0.95
        item = Item('test', 0, 'test', min_float=0.9, max_float=0.95)
        target_item = Item('target_test', 0, 'test', min_float=0, max_float=0.08)

        conversions = get_item_to_item_conversions(item, ItemCondition.BATTLE_SCARED, target_item)
        expected = {
            ItemCondition.MINIMAL_WEAR: FloatRange(0.9, 0.95)
        }
        self.assertEqual(conversions, expected)

    def test_get_item_possible_conversion_with_intersection(self):
        #   0 ---------- 0.85 ------------- 1
        #         0.6 -------- 0.95
        item = Item('test', 0, 'test', min_float=0.6, max_float=0.95)
        target_item = Item('target_test', 0, 'test', min_float=0, max_float=0.08)

        conversions = get_item_to_item_conversions(item, ItemCondition.BATTLE_SCARED, target_item)
        expected = {
            ItemCondition.MINIMAL_WEAR: FloatRange(0.8750000000000001, 0.95),
            ItemCondition.FACTORY_NEW: FloatRange(0.6, 0.8750000000000001)
        }
        self.assertEqual(conversions, expected)

    def test_get_item_possible_conversions_target_range_inclusion(self):
        item = Item('test', 4, 'test', min_float=0, max_float=1)
        # 0 ---- 0.099 ---- 0.56 ---- 0.7 ---- 1
        target_item = Item('target_test', 4, 'test', min_float=0.1, max_float=0.6)

        conversions = get_item_to_item_conversions(item, ItemCondition.BATTLE_SCARED, target_item)
        expected = {
            ItemCondition.BATTLE_SCARED: FloatRange(0.7, 1),
            ItemCondition.WELL_WORN: FloatRange(0.56, 0.7),
            ItemCondition.FIELD_TESTED: FloatRange(0.45, 0.56)
        }
        self.assertEqual(conversions, expected)

        conversions = get_item_to_item_conversions(item, ItemCondition.MINIMAL_WEAR, target_item)
        expected = {
            ItemCondition.FIELD_TESTED: FloatRange(0.09999999999999998, 0.15),
            ItemCondition.MINIMAL_WEAR: FloatRange(0.07, 0.09999999999999998)
        }
        self.assertEqual(conversions, expected)

        conversions = get_item_to_item_conversions(item, ItemCondition.FACTORY_NEW, target_item)
        expected = {
            ItemCondition.MINIMAL_WEAR: FloatRange(0, 0.07)
        }
        self.assertEqual(conversions, expected)
