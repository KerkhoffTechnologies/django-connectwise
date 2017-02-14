from django.test import TestCase
from djconnectwise.utils import get_hash, get_filename_extension


class TestUtils(TestCase):

    def test_get_hash_returns_hash(self):
        self.assertEqual(
            get_hash('hello, world'.encode('utf-8')),
            'b7e23ec29af22b0b4e41da31e868d57226121c84'
        )

    def test_get_filename_extension_returns_extension(self):
        self.assertEqual(
            get_filename_extension('avatar.jpg'),
            'jpg'
        )
        # It also works with multiple dots in the name
        self.assertEqual(
            get_filename_extension('avatar.one.jpg'),
            'jpg'
        )

    def test_get_filename_extension_returns_none_when_invalid(self):
        self.assertEqual(
            get_filename_extension('avatar'),
            None
        )
        self.assertEqual(
            get_filename_extension(''),
            None
        )
