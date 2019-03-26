import math
import unittest
from math import nan
from unittest import mock


def add(x):
    return x + 1


def compute(x, y):
    return y * add(x)


b = []


def dirty_add(x):
    return b + [x]


class AddTest(unittest.TestCase):

    def test_add_positive(self):
        self.assertEqual(add(3), 4, 'positive number addition')

    def test_add_negative(self):
        self.assertEqual(add(-2), -1, 'negative number addition')

    def test_add_zero(self):
        self.assertEqual(add(0), 1, 'zero value addition')

    def test_add_nan(self):
        self.assertTrue(math.isnan(add(nan)), 'NaN addition')

    def test_add_inf(self):
        self.assertEqual(add(math.inf), math.inf, 'inf addition')


class DirtyStateTest(unittest.TestCase):

    def test_dirty_add(self):
        self.assertEqual(dirty_add(1), [1])

    def test_dirty_state(self):
        b.append(2)
        self.assertEqual(dirty_add(1), [1])


class ArrTest(unittest.TestCase):

    def setUp(self):
        self.arr = [1, 2, 3]

    def test_arr_addition(self):
        self.assertEqual(self.arr + [4], [1, 2, 3, 4])

    def test_arr_len(self):
        self.assertEqual(len(self.arr), 3)


class MockTest(unittest.TestCase):

    def test_compute_func(self):
        self.assertEqual(compute(1, 2), 4)

    @mock.patch('test.test_functions.add', return_value=-10)
    def test_compute_with_mocked_add(self, m):
        self.assertEqual(compute(1, 2), -20)
