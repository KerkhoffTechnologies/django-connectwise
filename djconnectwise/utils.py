import re
import hashlib
from io import BytesIO
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageOps
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

_underscorer1 = re.compile(r'(.)([A-Z][a-z]+)')
_underscorer2 = re.compile(r'([a-z0-9])([A-Z])')
FILENAME_EXTENSION_RE = re.compile(r'\.([\w]*)$')

# Any more than this, the days of the week will likely have all repeated.
YEARS_TO_CHECK = 6


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
    thumbnail = ImageOps.fit(avatar_image, size, Image.LANCZOS)

    # For now just change the extension to jpeg
    # https://stackoverflow.com/questions/37048807/python-image-library-and-keyerror-jpg
    if extension.lower() == 'jpg':
        extension = 'jpeg'

    byte_stream = BytesIO()
    thumbnail.save(byte_stream, format=extension)
    avatar_file = ContentFile(byte_stream.getvalue())

    return avatar_file, filename


def generate_image_url(company_id, guid):
    if not guid:
        return None

    return settings.CONNECTWISE_SERVER_URL + \
        '/v4_6_release/api/inlineimages/' + company_id + '/' + guid


def parse_sla_status(sla_status, date_created):
    """
    Parse the SLA status string from ConnectWise into a datetime object and
    SLA stage name.

    :param sla_status: The SLA status string from ConnectWise.
    :param date_created: The creation date of the ticket, UTC

    :return: A tuple containing the SLA stage name and the datetime object,
             or the SLA stage and None if the SLA status is Waiting or
             Resolved.
    """

    # Regex matches day-of-week, month/day, time, and timezone offset.
    # Example SLA data from CW: "Respond by Mon 01/27 4:00 PM UTC-08"
    pattern = (r'\w+\sby\s(\w{3})\s(\d{2})/(\d{2})\s(\d{1,2}:\d{2})\s'
               r'(AM|PM)\sUTC([+-]\d{1,2})')
    match = re.search(pattern, sla_status)

    if not match:
        # There is no date, so it is Waiting or Resolved. Just return the
        # status.
        return sla_status.strip(), None

    day_of_week, month, day, time_str, am_pm, tz_offset_str = match.groups()
    month = int(month)
    day = int(day)
    tz_offset_hours = int(tz_offset_str)
    tz_info = timezone(timedelta(hours=tz_offset_hours))

    utc_date = None

    # We'll iterate over several years, starting with date_created.year (as
    # the SLA can't be before the ticket was created).
    for check_year in range(
            date_created.year, date_created.year + YEARS_TO_CHECK):

        # Create with string because this makes handling AM/PM much easier.
        # Otherwise, we have to manually convert 12-hour to 24-hour, then
        # handle the case when it crosses midnight, it's a whole thing.
        date_string = f"{check_year} {month:02d} {day:02d} {time_str} {am_pm}"
        check_date = datetime.strptime(date_string, "%Y %m %d %I:%M %p")
        check_date = check_date.replace(tzinfo=tz_info)

        # Skip dates that occur before the ticket was created.
        if check_date < date_created:
            continue

        # Check if the date's day-of-week matches the expected day.
        if check_date.strftime("%a") == day_of_week:
            # Convert to UTC
            utc_date = check_date.astimezone(timezone.utc)
            break

    # If we reach this point, we couldn't find a valid date. Just return the
    # stage with utc date as None I guess. There isn't really much we can do,
    # and if you have a 6 year old SLA, that's a you problem.
    stage = sla_status.split()[0].lower()
    return stage, utc_date


class DjconnectwiseSettings:

    def get_settings(self):
        # Make some defaults
        request_settings = {
            'timeout': 30.0,
            'batch_size': 50,
            'max_attempts': 3,
            'max_url_length': 2000,
            'schedule_entry_conditions_size': 0,
            'response_version': '2020.4',
            'sync_child_tickets': True,
            'sync_time_and_note_entries': True,
            'sync_contact_communications': True,
            'keep_closed_ticket_days': 0,
            'keep_closed_status_board_ids': 0,
            'send_naive_datetimes': True,
        }

        if hasattr(settings, 'DJCONNECTWISE_CONF_CALLABLE'):
            request_settings.update(settings.DJCONNECTWISE_CONF_CALLABLE())

        return request_settings
