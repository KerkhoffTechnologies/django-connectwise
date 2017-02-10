import hashlib
import re

_underscorer1 = re.compile(r'(.)([A-Z][a-z]+)')
_underscorer2 = re.compile('([a-z0-9])([A-Z])')
FILENAME_EXTENSION_RE = re.compile('\.([\w]*)$')

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
    """From the given filename, return the extension, or None if it can't be parsed."""
    m = FILENAME_EXTENSION_RE.search(filename)
    return m.group(1) if m else None
