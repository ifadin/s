from unittest import TestCase

from csgo.type.item import ItemCondition


class ItemTest(TestCase):

    def test_item_cond_str(self):
        name = str(ItemCondition.WELL_WORN)
        self.assertEqual(name, 'Well-Worn')

    def test_item_cond_short_str(self):
        name = ItemCondition.to_short_str(ItemCondition.WELL_WORN)
        self.assertEqual(name, 'WW')
