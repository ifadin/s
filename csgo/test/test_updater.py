from unittest import TestCase

from csgo.interface.updater import Updater


class UpdaterTest(TestCase):

    def test_get_file_name(self):
        name = Updater.get_file_name('DM-53 | Look it')
        self.assertEqual(name, 'dm_53_look_it.json')

    def test_get_file_name_with_special(self):
        name = Updater.get_file_name("DM-53 | come'get'it")
        self.assertEqual(name, "dm_53_come_get_it.json")
