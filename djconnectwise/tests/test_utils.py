from django.test import TestCase
from djconnectwise.utils import get_hash, get_filename_extension, \
                                generate_thumbnail


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
        # It also works with spaces in the name
        self.assertEqual(
            get_filename_extension('avatar me.jpg'),
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

    def test_generate_micro_avatar_thumbnail(self):
        from . import mocks

        avatar = mocks.get_member_avatar()
        size = (20, 20)
        extension = 'png'
        filename = 'AnonymousMember.png'
        processed_filename = 'AnonymousMember.png20x20.png'

        file, thumb_filename = generate_thumbnail(avatar,
                                                  size, extension, filename)

        self.assertEqual(processed_filename, thumb_filename)
