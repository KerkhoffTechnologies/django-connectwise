import hashlib
import json
import re
from io import BytesIO

from PIL import Image, ImageOps
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

_underscorer1 = re.compile(r'(.)([A-Z][a-z]+)')
_underscorer2 = re.compile(r'([a-z0-9])([A-Z])')
FILENAME_EXTENSION_RE = re.compile(r'\.([\w]*)$')


def camel_to_snake(s):
    """
    Is it ironic that this function is written in camel case, yet it
    converts to snake case? hmm..
    """
    subbed = _underscorer1.sub(r'\1_\2', s)
    return _underscorer2.sub(r'\1_\2', subbed).lower()


def snake_to_camel(snake_case_text):
    tokens = snake_case_text.split('_')
    return ''.join(word.capitalize() for word in tokens)


def get_hash(content):
    """Return the hex SHA-1 hash of the given content."""
    return hashlib.sha1(content).hexdigest()


def get_filename_extension(filename):
    """From the given filename, return the extension,
    or None if it can't be parsed.
    """
    m = FILENAME_EXTENSION_RE.search(filename)
    return m.group(1) if m else None


def generate_filename(size, current_filename, extension):
    img_dimensions = 'x'.join([str(i) for i in size])
    filename = '{}{}.{}'.format(current_filename, img_dimensions, extension)
    return filename


def remove_thumbnail(avatar_filename):
    thumbnail_size = {
        'avatar': (80, 80),
        'micro_avatar': (20, 20),
    }
    # This deletes the image name from DB field
    # and also removes thumbnails from storage.
    extension = get_filename_extension(avatar_filename)
    for size in thumbnail_size:
        filename = generate_filename(thumbnail_size[size],
                                     avatar_filename, extension)
        default_storage.delete(filename)

    default_storage.delete(avatar_filename)


def generate_thumbnail(avatar, size, extension, filename):
    filename = generate_filename(size, filename, extension)
    avatar_image = Image.open(BytesIO(avatar))
    thumbnail = ImageOps.fit(avatar_image, size, Image.ANTIALIAS)

    # For now just change the extension to jpeg
    # https://stackoverflow.com/questions/37048807/python-image-library-and-keyerror-jpg
    if extension.lower() == 'jpg':
        extension = 'jpeg'

    byte_stream = BytesIO()
    thumbnail.save(byte_stream, format=extension)
    avatar_file = ContentFile(byte_stream.getvalue())

    return avatar_file, filename


def process_error_response(response):
    error = response.content.decode("utf-8")
    # decode the bytes encoded error to a string
    # error = error.args[0].decode("utf-8")
    error = error.replace('\r\n', '')
    messages = []

    try:
        error = json.loads(error)
        stripped_message = error.get('message').rstrip('.') if \
            error.get('message') else 'No message'
        primary_error_msg = '{}.'.format(stripped_message)
        if error.get('errors'):
            for error_message in error.get('errors'):
                messages.append(
                    '{}.'.format(error_message.get('message').rstrip('.'))
                )

        messages = ' The error was: '.join(messages)

        msg = '{} {}'.format(primary_error_msg, messages)

    except json.decoder.JSONDecodeError:
        # JSON decoding failed
        msg = 'An error occurred: {} {}'.format(response.status_code,
                                                error)
    except KeyError:
        # 'code' or 'message' was not found in the error
        msg = 'An error occurred: {} {}'.format(response.status_code,
                                                error)
    return msg


class DjconnectwiseSettings:
    def get_settings(self):
        # Make some defaults
        request_settings = {
            'timeout': 30.0,
            'batch_size': 50,
            'max_attempts': 3,
            'schedule_entry_conditions_size': 0,
            'response_version': '2019.5',
            'sync_child_tickets': True,
            'sync_time_and_note_entries': True,
        }

        if hasattr(settings, 'DJCONNECTWISE_CONF_CALLABLE'):
            request_settings.update(settings.DJCONNECTWISE_CONF_CALLABLE())

        return request_settings
