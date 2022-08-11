import datetime
import json
import logging
import re
from urllib.parse import urlparse

import pytz
import requests
from django.conf import settings
from django.core.cache import cache
from django.db import models
from retrying import retry

from djconnectwise.utils import DjconnectwiseSettings

# Cloud URLs:
# https://developer.connectwise.com/Products/Manage/Developer_Guide#Cloud_URLs
CW_CLOUD_URLS = {
    'au.myconnectwise.net': 'api-au.myconnectwise.net',
    'eu.myconnectwise.net': 'api-eu.myconnectwise.net',
    'na.myconnectwise.net': 'api-na.myconnectwise.net',
    'aus.myconnectwise.net': 'api-aus.myconnectwise.net',
    'za.myconnectwise.net': 'api-za.myconnectwise.net',
}
COMPANY_INFO_REQUIRED = 'company-info-required'
CW_CLOUD_DOMAIN = 'myconnectwise.net'
DEFAULT_CW_API_CODEBASE = 'v4_6_release/'

CW_RESPONSE_MAX_RECORDS = 1000  # The greatest number of records ConnectWise
# will send us in one response.
RETRY_WAIT_EXPONENTIAL_MULTAPPLIER = 1000  # Initial number of milliseconds to
# wait before retrying a request.
RETRY_WAIT_EXPONENTIAL_MAX = 10000  # Maximum number of milliseconds to wait
# before retrying a request.
CW_DEFAULT_PAGE = 1  # CW Pagination is 1-indexed
CONTENT_DISPOSITION_RE = re.compile(
    '^attachment; filename=\"{0,1}(.*?)\"{0,1}$'
)

logger = logging.getLogger(__name__)


class ConnectWiseAPIError(Exception):
    """Raise this, not request exceptions."""
    pass


class ConnectWiseAPIClientError(ConnectWiseAPIError):
    """
    Raise this to indicate any http error that falls within the
    4xx class of http status codes.
    """
    pass


class ConnectWiseAPIServerError(ConnectWiseAPIError):
    """
    Raise this to indicate a Server Error
    https://developer.connectwise.com/Manage/Developer_Guide#HTTP_Response_Codes
    500 class of http status codes.
    """
    pass


class ConnectWiseRecordNotFoundError(ConnectWiseAPIClientError):
    """The record was not found."""
    pass


class ConnectWiseSecurityPermissionsException(ConnectWiseAPIClientError):
    """The API credentials have insufficient security permissions."""
    pass


class CompanyInfoManager:
    COMPANYINFO_ENDPOINT = '{}/login/companyinfo/{}'

    def get_company_info(self, server_url, company_id):
        company_endpoint = self.COMPANYINFO_ENDPOINT.format(
            server_url, company_id
        )

        try:
            logger.debug('Making GET request to {}'.format(company_endpoint))
            response = requests.get(company_endpoint)
            if 200 <= response.status_code < 300:
                resp_json = response.json()
                if resp_json is None:
                    # CW returns None if company ID is unknown.
                    raise ConnectWiseAPIError(
                        'Null response received- company ID may be unknown.'
                    )
                else:
                    return resp_json
            elif response.status_code == 404:
                msg = 'CompanyInfo not found: {}'.format(company_endpoint)
                raise ConnectWiseRecordNotFoundError(msg)
            else:
                raise ConnectWiseAPIError(response.content)
        except requests.RequestException as e:
            raise ConnectWiseAPIError(
                'CompanyInfo request failed: GET {}: {}'.format(
                    company_endpoint, e
                )
            )

    def fetch_api_codebase(self, server_url, company_id, force_fetch=True):
        """
        Returns the Codebase value for the hosted Connectwise instance
        at the supplied URL. The Codebase is retrieved from the cache
        or, if it is not found, it is retrieved from the companyinfo endpoint.
        """
        cache_key = 'api_codebase'
        codebase_result = DEFAULT_CW_API_CODEBASE
        codebase_updated = False

        if CW_CLOUD_DOMAIN in server_url:
            logger.debug('Fetching ConnectWise codebase value from cache.')
            codebase_from_cache = cache.get(cache_key)
            logger.info(
                'Cached ConnectWise codebase was: {}'.format(
                    codebase_from_cache
                )
            )
            if not codebase_from_cache or force_fetch:
                company_info_json = self.get_company_info(
                    server_url, company_id
                )
                codebase_from_api = company_info_json['Codebase']

                codebase_updated = codebase_from_cache != codebase_from_api

                codebase_result = codebase_from_api
                logger.info(
                    'Setting ConnectWise codebase cache value to: {}'.format(
                        codebase_result
                    )
                )
                cache.set(cache_key, codebase_result)
            else:
                codebase_result = codebase_from_cache
        return codebase_result, codebase_updated


def retry_if_api_error(exception):
    """
    Return True if we should retry (in this case when it's an
    ConnectWiseAPIError), False otherwise.

    Basically, don't retry on ConnectWiseAPIClientError, because those are the
    type of exceptions where retrying won't help (404s, 403s, etc).
    """
    return type(exception) is ConnectWiseAPIError


class ConnectWiseAPIClient(object):
    API = None
    MAX_404_ATTEMPTS = 1

    def __init__(
        self,
        company_id=None,
        server_url=None,
        client_id=None,
        api_public_key=None,
        api_private_key=None,
    ):
        if not company_id:
            company_id = settings.CONNECTWISE_CREDENTIALS['company_id']
        if not server_url:
            server_url = settings.CONNECTWISE_SERVER_URL
        if not client_id:
            client_id = settings.CONNECTWISE_CLIENTID
        if not api_public_key:
            api_public_key = settings.CONNECTWISE_CREDENTIALS['api_public_key']
        if not api_private_key:
            api_private_key = settings.CONNECTWISE_CREDENTIALS[
                'api_private_key'
            ]

        if not self.API:
            raise ValueError('API not specified')

        self.info_manager = CompanyInfoManager()
        self.company_id = company_id
        self.api_public_key = api_public_key
        self.api_private_key = api_private_key
        self.server_url = self.change_cw_cloud_url(server_url)
        self.client_id = client_id
        self.auth = (
            '{0}+{1}'.format(company_id, self.api_public_key),
            '{0}'.format(self.api_private_key),
        )

        self.request_settings = DjconnectwiseSettings().get_settings()
        self.timeout = self.request_settings['timeout']

    def _endpoint(self, path):
        return '{0}{1}'.format(self.api_base_url, path)

    def _log_failed(self, response):
        logger.error('Failed API call: {0} - {1} - {2}'.format(
            response.url, response.status_code, response.content))

    def _prepare_error_response(self, response):
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

    @property
    def api_base_url(self):
        # This will be for this particular API-
        # i.e. https://connectwise.example.com/v4_6_release/apis/3.0/service/
        api_base_url, _ = self.build_api_base_url()
        return api_base_url

    def build_api_base_url(self, force_fetch=False):
        api_codebase, codebase_updated = \
            self.info_manager.fetch_api_codebase(
                self.server_url, self.company_id, force_fetch=force_fetch
            )

        api_base_url = '{0}/{1}apis/3.0/{2}/'.format(
            self.server_url,
            api_codebase,
            self.API,
        )

        return api_base_url, codebase_updated

    def get_headers(self):
        headers = {}

        response_version = self.request_settings.get('response_version')

        if response_version:
            headers['Accept'] = \
                'application/vnd.connectwise.com+json; version={}' \
                .format(response_version)

        if self.client_id:
            headers['clientId'] = self.client_id

        return headers

    def fetch_resource(self, endpoint_url, params=None, should_page=False,
                       retry_counter=None,
                       *args, **kwargs):
        """
        Issue a GET request to the specified REST endpoint.

        retry_counter is a dict in the form {'count': 0} that is passed in
        to verify the number of attempts that were made.
        """
        @retry(stop_max_attempt_number=self.request_settings['max_attempts'],
               wait_exponential_multiplier=RETRY_WAIT_EXPONENTIAL_MULTAPPLIER,
               wait_exponential_max=RETRY_WAIT_EXPONENTIAL_MAX,
               retry_on_exception=retry_if_api_error)
        def _fetch_resource(endpoint_url, params=None, should_page=False,
                            retry_counter=None, *args, **kwargs):
            if not retry_counter:
                retry_counter = {'count': 0}
            retry_counter['count'] += 1

            if not params:
                params = {}

            try:
                endpoint = self._endpoint(endpoint_url)
                logger.debug('Making GET request to {}'.format(endpoint))

                conditions_str = ''
                conditions = kwargs.get('conditions')
                if conditions:
                    logger.debug('Conditions: {}'.format(conditions))
                    conditions_str = 'conditions={}'.format(
                        self.prepare_conditions(conditions)
                    )
                    # URL encode needed characters
                    conditions_str = conditions_str.replace("+", "%2B")
                    conditions_str = conditions_str.replace(" ", "+")

                if should_page:
                    params['pageSize'] = kwargs.get('page_size',
                                                    CW_RESPONSE_MAX_RECORDS)
                    params['page'] = kwargs.get('page', CW_DEFAULT_PAGE)
                    endpoint += "?pageSize={}&page={}".format(
                        params['pageSize'], params['page'])

                    endpoint += "&" + conditions_str
                else:
                    endpoint += "?" + conditions_str

                response = requests.get(
                    endpoint,
                    auth=self.auth,
                    timeout=self.timeout,
                    headers=self.get_headers(),
                )
                logger.debug(" URL: {}".format(response.url))

            except requests.RequestException as e:
                logger.error('Request failed: GET {}: {}'.format(endpoint, e))
                raise ConnectWiseAPIError('{}'.format(e))

            if 200 <= response.status_code < 300:
                return response.json()

            elif response.status_code == 404:
                msg = 'Resource not found: {}'.format(response.url)
                logger.warning(msg)
                # If this is the first failure, try updating the
                # company info codebase value and let it be retried by the
                # @retry decorator.
                if retry_counter['count'] <= self.MAX_404_ATTEMPTS:
                    _, codebase_updated = self.build_api_base_url(
                        force_fetch=True
                    )
                    if codebase_updated:
                        # Since the codebase was updated, it is worthwhile
                        # to try this request again. It could be that the 404
                        # was due to hosted ConnectWise changing the codebase
                        # URL recently. So raise ConnectWiseAPIError, which
                        # will cause the call to be retried.
                        logger.info('Codebase value has changed, so this '
                                    'request will be retried.')
                        raise ConnectWiseAPIError(response.content)
                raise ConnectWiseRecordNotFoundError(msg)

            elif response.status_code == 403:
                self._log_failed(response)
                raise ConnectWiseSecurityPermissionsException(
                    self._prepare_error_response(response),
                    response.status_code
                )

            elif 400 <= response.status_code < 499:
                self._log_failed(response)
                raise ConnectWiseAPIClientError(
                    self._prepare_error_response(response))
            elif response.status_code == 500:
                self._log_failed(response)
                raise ConnectWiseAPIServerError(
                    self._prepare_error_response(response))
            else:
                self._log_failed(response)
                raise ConnectWiseAPIError(
                    self._prepare_error_response(response))

        if not retry_counter:
            retry_counter = {'count': 0}
        return _fetch_resource(endpoint_url, params=params,
                               should_page=should_page,
                               retry_counter=retry_counter,
                               *args, **kwargs)

    def prepare_conditions(self, conditions):
        """
        From the given array of individual conditions, format the conditions
        URL parameter according to ConnectWise requirements.
        """
        return '({})'.format(' and '.join(conditions))

    def request(self, method, endpoint_url, body=None):
        """
        Issue the given type of request to the specified REST endpoint.
        """
        try:
            logger.debug(
                'Making {} request to {}'.format(method, endpoint_url)
            )
            response = requests.request(
                method,
                endpoint_url,
                json=body,
                auth=self.auth,
                timeout=self.timeout,
                headers=self.get_headers(),
            )
        except requests.RequestException as e:
            logger.error(
                'Request failed: {} {}: {}'.format(method, endpoint_url, e)
            )
            raise ConnectWiseAPIError('{}'.format(e))

        if response.status_code == 204:  # No content
            return None
        elif 200 <= response.status_code < 300:
            return response.json()
        elif response.status_code == 403:
            self._log_failed(response)
            raise ConnectWiseSecurityPermissionsException(
                self._prepare_error_response(response), response.status_code)
        elif response.status_code == 404:
            msg = 'Resource not found: {}'.format(response.url)
            logger.warning(msg)
            raise ConnectWiseRecordNotFoundError(msg)
        elif 400 <= response.status_code < 499:
            self._log_failed(response)
            raise ConnectWiseAPIClientError(
                self._prepare_error_response(response))
        elif response.status_code == 500:
            self._log_failed(response)
            raise ConnectWiseAPIServerError(
                self._prepare_error_response(response))
        else:
            self._log_failed(response)
            raise ConnectWiseAPIError(response)

    def change_cw_cloud_url(self, server_url):
        """
        Replace the user-facing CW CLoud URLs with the API URLs.

        i.e. https://na.myconnectwise.net becomes
        https://api-na.myconnectwise.net

        See https://developer.connectwise.com/Products/Manage/Developer_Guide#Authentication  # noqa
        """
        url = urlparse(server_url)
        if url.netloc not in CW_CLOUD_URLS:
            # Don't change anything, just return.
            return server_url

        return url._replace(netloc=CW_CLOUD_URLS[url.netloc]).geturl()

    def update_instance(self, instance, changed_fields, endpoint_url):
        # Yeah, this schema is a bit bizarre. See CW docs at
        # https://developer.connectwise.com/Manage/Developer_Guide#Patch
        body = self._format_request_body(instance, changed_fields)
        return self.request('patch', endpoint_url, body)

    def _format_request_body(self, instance, changed_fields):
        body = []

        for field, value in changed_fields.items():

            # FieldTracker tracks Foreign Keys by database column name.
            # Remove _id to use the Django model field name.
            field = field.replace('_id', '')

            if field and field in instance.EDITABLE_FIELDS:
                field_update = {
                    'op': 'replace',
                    'path': instance.EDITABLE_FIELDS[field],
                }

                if isinstance(value, datetime.datetime):
                    field_update.update({
                        'value': value.astimezone(
                            pytz.timezone('UTC')).strftime(
                                "%Y-%m-%dT%H:%M:%SZ")
                    })

                elif isinstance(value, models.Model):
                    field_update.update({
                        'value': {
                            'id': value.id,
                        }
                    })
                else:
                    field_update.update({'value': str(value) if value else ''})

                body.append(field_update)

        return body

    def _format_patch_body(self, **kwargs):
        """
        Formats patch requests for dummy synchronizers to match CWs bizarre
        schema:
        # https://developer.connectwise.com/Manage/Developer_Guide#Patch
        """
        body = []
        for path, value in kwargs.items():
            body.append({
                'op': 'replace',
                'path': path,
                'value': value
            })

        return body


class CompanyAPIClient(ConnectWiseAPIClient):
    API = 'company'
    ENDPOINT_COMPANIES = 'companies'
    ENDPOINT_CONTACTS = 'contacts'
    ENDPOINT_COMPANY_STATUSES = '{}/statuses'.format(ENDPOINT_COMPANIES)
    ENDPOINT_COMPANY_TYPES = '{}/types'.format(ENDPOINT_COMPANIES)
    ENDPOINT_COMPANY_COMMUNICATION_TYPES = 'communicationTypes'
    ENDPOINT_CONTACT_COMMUNICATIONs = 'communications'

    def __init__(self, *args, **kwargs):
        # TODO This init method is temporary, remove in 1840 as well as
        #   references to self.communication_type_endpoint
        super().__init__(*args, **kwargs)

        self.communication_type_endpoint = False

    def by_id(self, company_id):
        endpoint_url = '{}/{}'.format(self.ENDPOINT_COMPANIES, company_id)
        return self.fetch_resource(endpoint_url)

    def get_single_contact(self, contact_id):
        endpoint_url = '{}/{}'.format(self.ENDPOINT_CONTACTS, contact_id)
        return self.fetch_resource(endpoint_url)

    def get_single_communication(self, communication_id):
        endpoint_url = '{}/{}/{}'.format(self.ENDPOINT_CONTACTS,
                                         self.ENDPOINT_CONTACT_COMMUNICATIONs,
                                         communication_id)
        return self.fetch_resource(endpoint_url)

    def get_companies(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_COMPANIES, should_page=True,
                                   *args, **kwargs)

    def get_company_statuses(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_COMPANY_STATUSES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_company_types(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_COMPANY_TYPES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_contacts(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_CONTACTS, should_page=True,
                                   *args, **kwargs)

    def get_contact_communications(self, contact_id, *args, **kwargs):
        endpoint_url = '{}/{}/communications'.format(self.ENDPOINT_CONTACTS,
                                                     contact_id)
        return self.fetch_resource(endpoint_url, should_page=True,
                                   *args, **kwargs)

    def get_communication_types(self, *args, **kwargs):
        self.communication_type_endpoint = True
        return self.fetch_resource(self.ENDPOINT_COMPANY_COMMUNICATION_TYPES,
                                   should_page=True, *args, **kwargs)

    def get_headers(self):
        """
        This is a temporary fix for setting the response version for the
        communication type endpoint. It does not accept our currently supported
        response version (2019.5). This will be fixed in an upcoming issue
        """
        headers = super().get_headers()

        if self.communication_type_endpoint:
            # Just checking if the response version exists
            response_version = self.request_settings.get('response_version')

            if response_version:
                headers['Accept'] = \
                    'application/vnd.connectwise.com+json; version=2020.4'

        return headers


class ScheduleAPIClient(ConnectWiseAPIClient):
    API = 'schedule'
    ENDPOINT_ENTRIES = 'entries'
    ENDPOINT_SCHEDULE_TYPES = 'types'
    ENDPOINT_SCHEDULE_STATUSES = 'statuses'
    ENDPOINT_CALENDARS = 'calendars'
    ENDPOINT_HOLIDAY = 'holidayLists'

    def get_schedule_statuses(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_SCHEDULE_STATUSES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_schedule_types(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_SCHEDULE_TYPES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_schedule_entries(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_ENTRIES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_schedule_entry(self, entry_id):
        endpoint_url = '{}/{}'.format(self.ENDPOINT_ENTRIES, entry_id)
        return self.fetch_resource(endpoint_url)

    def post_schedule_entry(self, target, schedule_type, **kwargs):
        endpoint_url = self._endpoint(self.ENDPOINT_ENTRIES)

        body = {
                    "objectId": target.id,
                    "type": {
                        "id": schedule_type.id,
                        "identifier": schedule_type.identifier,
                    }
                }

        member = kwargs.get("member")
        if member:
            body.update({
                "member": {
                            "id": member.id,
                            "identifier": member.identifier,
                            "name": str(member)
                          }
            })

        date_start = kwargs.get("date_start")
        if date_start:
            body["dateStart"] = date_start.astimezone(
                pytz.timezone('UTC')).strftime("%Y-%m-%dT%H:%M:%SZ")

        date_end = kwargs.get("date_end")
        if date_end:
            body["dateEnd"] = kwargs.get("date_end")
            body["dateEnd"] = date_end.astimezone(
                pytz.timezone('UTC')).strftime("%Y-%m-%dT%H:%M:%SZ")

        allow_conflicts = kwargs.get("allow_conflicts")
        if allow_conflicts is not None:
            body["allowScheduleConflictsFlag"] = allow_conflicts

        return self.request('post', endpoint_url, body)

    def patch_schedule_entry(self, **kwargs):
        schedule_id = kwargs.get("id")
        endpoint_url = self._endpoint(
            "{}/{}".format(self.ENDPOINT_ENTRIES, schedule_id))

        # Yeah, this schema is a bit bizarre. See CW docs at
        # https://developer.connectwise.com/Manage/Developer_Guide#Patch
        body = [
            {
                'op': 'replace',
                'path': 'doneFlag',
                'value': kwargs.get("done_flag")
            }
        ]
        return self.request('patch', endpoint_url, body)

    def delete_schedule_entry(self, entry_id):
        endpoint_url = self._endpoint(
            '{}/{}'.format(self.ENDPOINT_ENTRIES, entry_id))
        return requests.request(
            'delete',
            endpoint_url,
            auth=self.auth,
            timeout=self.timeout,
            headers=self.get_headers(),
        )

    def get_calendars(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_CALENDARS,
                                   should_page=True,
                                   *args, **kwargs)

    def get_holidays(self, holiday_list_id, *args, **kwargs):
        endpoint_url = '{}/{}/holidays'.format(
            self.ENDPOINT_HOLIDAY,
            holiday_list_id
            )
        return self.fetch_resource(
            endpoint_url,
            should_page=True,
            *args,
            **kwargs
            )

    def get_holiday_lists(self, *args, **kwargs):
        return self.fetch_resource(
            self.ENDPOINT_HOLIDAY,
            should_page=True,
            *args,
            **kwargs
            )


class TimeAPIClient(ConnectWiseAPIClient):
    API = 'time'
    ENDPOINT_ENTRIES = 'entries'
    ENDPOINT_WORK_TYPES = 'workTypes'
    ENDPOINT_WORK_ROLES = 'workRoles'

    def get_time_entries(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_ENTRIES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_work_types(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_WORK_TYPES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_work_roles(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_WORK_ROLES,
                                   should_page=True,
                                   *args, **kwargs)

    def post_time_entry(self, target_data, **kwargs):
        endpoint_url = self._endpoint(self.ENDPOINT_ENTRIES)

        time_start = kwargs.get("time_start")
        time_start = time_start.astimezone(pytz.timezone('UTC')).strftime(
            "%Y-%m-%dT%H:%M:%SZ")

        body = {
                    "chargeToId": target_data['id'],
                    "chargeToType": target_data['type'],
                    "timeStart": time_start,
                    "addToDetailDescriptionFlag": kwargs
                    .get("description_flag"),
                    "addToInternalAnalysisFlag": kwargs
                    .get("analysis_flag"),
                    "addToResolutionFlag": kwargs.get("resolution_flag"),
                    "emailResourceFlag": kwargs.get("resource_flag"),
                    "emailContactFlag": kwargs.get("contact_flag"),
                    "emailCcFlag": kwargs.get("cc_flag"),
                }

        member = kwargs.get("resource")
        if member:
            body.update({
                "member": {
                    "id": member.id,
                    "identifier": member.identifier,
                    "name": str(member),
                }

            })

        time_end = kwargs.get("time_end")
        if time_end:
            time_end = time_end.astimezone(pytz.timezone('UTC')).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
            body.update({"timeEnd": time_end})

        hours_deduct = kwargs.get("hours_deduct")
        if hours_deduct:
            body.update({"hoursDeduct": hours_deduct})

        actual_hours = kwargs.get("actual_hours")
        if actual_hours:
            body.update({"actualHours": actual_hours})

        billable_option = kwargs.get("billable_option")
        if billable_option:
            body.update({"billableOption": billable_option})

        work_type = kwargs.get("work_type")
        if work_type:
            body.update({
                "workType": {
                    "name": str(work_type)
                }
            })

        work_role = kwargs.get("work_role")
        if work_role:
            body.update({
                "workRole": {
                    "name": str(work_role)
                }
            })

        agreement = kwargs.get("agreement")
        if agreement:
            body.update({
                "agreement": {
                    "id": agreement.id,
                    "name": str(agreement)
                }
            })

        notes = kwargs.get("notes")
        if notes:
            body.update({"notes": notes})

        email_cc = kwargs.get("email_cc")
        if email_cc:
            body.update({
                "emailCc": email_cc
            })

        return self.request('post', endpoint_url, body)

    def update_time_entry(self, time_entry):
        endpoint_url = self._endpoint(
            '{}/{}'.format(self.ENDPOINT_ENTRIES, time_entry.id)
        )
        body = [{
            'op': 'replace',
            'path': 'notes',
            'value': time_entry.notes
        }]
        return self.request('patch', endpoint_url, body)


class SalesAPIClient(ConnectWiseAPIClient):
    API = 'sales'
    ENDPOINT_OPPORTUNITIES = 'opportunities'
    ENDPOINT_OPPORTUNITY_STATUSES = \
        '{}/statuses'.format(ENDPOINT_OPPORTUNITIES)
    ENDPOINT_OPPORTUNITY_TYPES = \
        '{}/types'.format(ENDPOINT_OPPORTUNITIES)
    ENDPOINT_ACTIVITIES = 'activities'
    ENDPOINT_ACTIVITY_STATUSES = '{}/statuses'.format(ENDPOINT_ACTIVITIES)
    ENDPOINT_ACTIVITY_TYPES = '{}/types'.format(ENDPOINT_ACTIVITIES)
    ENDPOINT_PROBABILITIES = 'probabilities'
    ENDPOINT_STAGES = 'stages'

    def by_id(self, opportunity_id):
        endpoint_url = '{}/{}'.format(
            self.ENDPOINT_OPPORTUNITIES, opportunity_id)
        return self.fetch_resource(endpoint_url)

    def get_activities(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_ACTIVITIES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_single_activity(self, activity_id):
        endpoint_url = '{}/{}'.format(
            self.ENDPOINT_ACTIVITIES, activity_id)
        return self.fetch_resource(endpoint_url)

    def get_activity_statuses(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_ACTIVITY_STATUSES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_activity_types(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_ACTIVITY_TYPES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_probabilities(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_PROBABILITIES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_opportunities(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_OPPORTUNITIES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_opportunity_statuses(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_OPPORTUNITY_STATUSES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_opportunity_types(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_OPPORTUNITY_TYPES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_opportunity_stages(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_STAGES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_notes(self, opportunity_id, *args, **kwargs):
        """
        Returns the notes associated with the specific opportunity.
        """
        endpoint_url = '{}/{}/notes'.format(self.ENDPOINT_OPPORTUNITIES,
                                            opportunity_id
                                            )
        return self.fetch_resource(endpoint_url, should_page=True,
                                   *args, **kwargs)

    def update_opportunity(self, obj, changed_fields):
        endpoint_url = self._endpoint(
            '{}/{}'.format(self.ENDPOINT_OPPORTUNITIES, obj.id)
        )
        return self.update_instance(obj, changed_fields, endpoint_url)

    def update_activity(self, obj, changed_fields):
        endpoint_url = self._endpoint(
            '{}/{}'.format(self.ENDPOINT_ACTIVITIES, obj.id)
        )
        return self.update_instance(obj, changed_fields, endpoint_url)


class SystemAPIClient(ConnectWiseAPIClient):
    API = 'system'

    # endpoints
    ENDPOINT_MEMBERS = 'members/'
    ENDPOINT_MEMBERS_IMAGE = 'documents/{}/download'
    ENDPOINT_MEMBERS_COUNT = 'members/count'
    ENDPOINT_CALLBACKS = 'callbacks/'
    ENDPOINT_INFO = 'info/'
    # Locations in the system API are actually territories
    ENDPOINT_LOCATIONS = 'locations/'
    ENDPOINT_OTHER = 'myCompany/other/'

    def get_connectwise_version(self):
        result = self.fetch_resource(self.ENDPOINT_INFO)
        return result.get('version', '')

    def get_members(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_MEMBERS,
                                   should_page=True, *args, **kwargs)

    def get_member_count(self):
        return self.fetch_resource(self.ENDPOINT_MEMBERS_COUNT)

    def get_territories(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_LOCATIONS,
                                   should_page=True, *args, **kwargs)

    def get_callbacks(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_CALLBACKS,
                                   should_page=True, *args, **kwargs)

    def get_mycompanyother(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_OTHER, *args, **kwargs)

    def delete_callback(self, entry_id):
        endpoint = self._endpoint(
            '{}{}'.format(self.ENDPOINT_CALLBACKS, entry_id)
        )
        return self.request(
            'delete',
            endpoint,
        )

    def create_callback(self, callback_entry):
        endpoint = self._endpoint(self.ENDPOINT_CALLBACKS)
        return self.request(
            'post',
            endpoint,
            body=callback_entry,
        )

    def get_member_by_identifier(self, identifier):
        return self.fetch_resource('members/{0}'.format(identifier))

    def get_member_image_by_photo_id(self, photo_id, username):
        """
        Return a (filename, content) tuple.

        This requires this permission:
        Companies => Manage Documents => Inquire Level: All
        """
        try:
            endpoint = self._endpoint(
                self.ENDPOINT_MEMBERS_IMAGE.format(photo_id)
            )
            logger.debug('Making GET request to {}'.format(endpoint))
            response = requests.get(
                endpoint,
                auth=self.auth,
                timeout=self.timeout,
                headers=self.get_headers(),
            )
        except requests.RequestException as e:
            logger.error('Request failed: GET {}: {}'.format(endpoint, e))
            raise ConnectWiseAPIError('{}'.format(e))

        if 200 <= response.status_code < 300:
            headers = response.headers
            content_disposition_header = headers.get('Content-Disposition',
                                                     default='')
            logger.info(
                "Got member '{}' image; size {} bytes and "
                "content-disposition header '{}'".format(
                    username,
                    len(response.content),
                    content_disposition_header
                )
            )
            attachment_filename = self._attachment_filename(
                content_disposition_header)
            return attachment_filename, response.content
        else:
            self._log_failed(response)
            return None, None

    def _attachment_filename(self, content_disposition):
        """
        Return the attachment filename from the content disposition header.

        If there's no match, return None.
        """
        m = CONTENT_DISPOSITION_RE.match(content_disposition)
        return m.group(1) if m else None


class TicketAPIMixin:
    ENDPOINT_TICKETS = 'tickets'

    def tickets_count(self, **kwargs):
        return self.fetch_resource(
            '{}/count'.format(self.ENDPOINT_TICKETS), **kwargs).get('count', 0)

    def get_ticket(self, ticket_id):
        endpoint_url = '{}/{}'.format(self.ENDPOINT_TICKETS, ticket_id)
        return self.fetch_resource(endpoint_url)

    def get_ticket_tasks(self, ticket_id, **kwargs):
        endpoint_url = '{}/{}/tasks'.format(
            self.ENDPOINT_TICKETS, ticket_id)
        return self.fetch_resource(endpoint_url, should_page=True, **kwargs)

    def create_ticket_task(self, ticket_id, **kwargs):
        endpoint_url = '{}/{}/tasks'.format(
            self.ENDPOINT_TICKETS, ticket_id)
        return self.request('post', self._endpoint(endpoint_url), kwargs)

    def update_ticket_task(self, task_id, ticket_id, **kwargs):
        endpoint_url = '{}/{}/tasks/{}'.format(
            self.ENDPOINT_TICKETS, ticket_id, task_id)
        body = self._format_patch_body(**kwargs)
        return self.request('patch', self._endpoint(endpoint_url), body)

    def delete_ticket_task(self, ticket_id, **kwargs):
        endpoint_url = '{}/{}/tasks/{}'.format(
            self.ENDPOINT_TICKETS, ticket_id, kwargs['id'])
        return self.request('delete', self._endpoint(endpoint_url))

    def get_tickets(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_TICKETS, should_page=True,
                                   *args, **kwargs)

    def update_ticket(self, ticket, changed_fields):
        endpoint_url = self._endpoint(
            '{}/{}'.format(self.ENDPOINT_TICKETS, ticket.id)
        )
        body = self._format_ticket_patch_body(ticket, changed_fields)
        return self.request('patch', endpoint_url, body)

    def create_ticket(self, ticket, changed_fields):
        endpoint_url = self._endpoint(
            '{}/'.format(self.ENDPOINT_TICKETS)
        )
        # Changed fields is useful at this point as it prevents us
        #  from sending an empty string, so the ticket is created with the
        #  defaults from CW. I don't think this is the best way to handle it
        #  though, and it should be updated to a new pattern during
        #  the quick create records milestone.
        # TODO remove changed fields to add new pattern
        body = self._format_ticket_post_body(ticket, changed_fields)
        return self.request('POST', endpoint_url, body)

    def _format_ticket_post_body(self, ticket, fields):
        # CW formats POST and PATCH very differently, thats why there are two
        #  different methods for it./
        # TODO reduce duplication between post/patch formatting after switch
        #  to synchronizers
        # TODO Extract converting fields from their DB name to their API name
        #  to their own method after switch to synchronizers
        body = {}

        for field, value in fields.items():

            if field and ticket.record_type and \
                    field in ticket.EDITABLE_FIELDS[ticket.record_type]:

                field = ticket.EDITABLE_FIELDS[ticket.record_type][field]

                if isinstance(value, datetime.datetime):
                    value = value.astimezone(
                            pytz.timezone('UTC')).strftime(
                            "%Y-%m-%dT%H:%M:%SZ")
                elif isinstance(value, models.Model):
                    value = {'id': value.id}
                else:
                    value = str(value) if value else ''

                body[field] = value

        return body

    def _format_ticket_patch_body(self, ticket, changed_fields):
        # TODO reduce duplication between post/patch formatting after switch
        #  to synchronizers
        # TODO Extract converting fields from their DB name to their API name
        #  to their own method
        body = []

        for field, value in changed_fields.items():

            if field and ticket.record_type and \
                    field in ticket.EDITABLE_FIELDS[ticket.record_type]:
                extra_field_updates = []
                field_update = {
                    'op': 'replace',
                    'path': ticket.EDITABLE_FIELDS[ticket.record_type][field],
                }

                if isinstance(value, datetime.datetime):
                    field_update.update({
                        'value': value.astimezone(
                            pytz.timezone('UTC')).strftime(
                                "%Y-%m-%dT%H:%M:%SZ")
                    })

                elif field == \
                        ticket.EDITABLE_FIELDS[ticket.record_type].get(
                            'contact') and value is None:
                    # If a contact is being cleared on a ticket, CW requires
                    # that the following fields be cleared as well.
                    contact_fields = [
                        'contactName', 'contactPhoneNumber',
                        'contactEmailAddress'
                    ]
                    field_update.update({
                        'value': ''
                    })

                    for contact_field in contact_fields:
                        extra_field_updates.append(
                            {
                                'op': 'remove',
                                'path': contact_field
                            }
                        )

                elif isinstance(value, models.Model):
                    field_update.update({
                        'value': {
                            'id': value.id,
                        }
                    })
                else:
                    field_update.update({'value': str(value) if value else ''})

                body.append(field_update)

                if extra_field_updates:
                    body.extend(extra_field_updates)

        return body

    def update_note(self, note):
        endpoint_url = self._endpoint(
            '{}/{}/notes/{}'.format(
                self.ENDPOINT_TICKETS, note.ticket.id, note.id)
        )
        body = [{
            'op': 'replace',
            'path': 'text',
            'value': note.text
        }]
        return self.request('patch', endpoint_url, body)


class ServiceAPIClient(TicketAPIMixin, ConnectWiseAPIClient):
    API = 'service'
    ENDPOINT_BOARDS = 'boards'
    ENDPOINT_PRIORITIES = 'priorities'
    ENDPOINT_LOCATIONS = 'locations'
    ENDPOINT_SLAS = 'SLAs'
    ENDPOINT_SOURCES = 'sources'

    def get_notes(self, ticket_id, *args, **kwargs):
        """
        Returns the notes associated with the specific ticket.
        """
        endpoint_url = '{}/{}/notes'.format(self.ENDPOINT_TICKETS, ticket_id)
        return self.fetch_resource(endpoint_url, should_page=True,
                                   *args, **kwargs)

    def post_note(self, target_data, **kwargs):
        endpoint_url = self._endpoint(
            '{}/{}/notes'.format(self.ENDPOINT_TICKETS, target_data['id']))

        body = {
            "detailDescriptionFlag": kwargs.get("description_flag"),
            "internalAnalysisFlag": kwargs.get("analysis_flag"),
            "resolutionFlag": kwargs.get("resolution_flag"),
            "processNotifications": kwargs.get("process_notifications"),
            "customerUpdatedFlag": kwargs.get("customer_updated_flag")
        }

        member = kwargs.get("resource")
        if member:
            body.update({
                "member": {
                    "id": member.id,
                    "identifier": member.identifier,
                    "name": str(member),
                }

            })

        contact = kwargs.get("contact")
        if contact:
            body.update({
                "contact": contact
            })

        text = kwargs.get("text")
        if text:
            body.update({"text": text})

        return self.request('post', endpoint_url, body)

    def post_merge_ticket(self, merge_data, **kwargs):
        parent_id = merge_data.get('parent_ticket_id')
        child_id = merge_data.get('child_ticket_id')
        status = merge_data.get('status')

        endpoint_url = self._endpoint(
            '{}/{}/merge'.format(self.ENDPOINT_TICKETS, parent_id))

        body = {
            "mergeTicketIds": [child_id],
            "status": {
                "id": status.id,
                "name": status.name
            }
        }
        return self.request('post', endpoint_url, body)

    def get_statuses(self, board_id, *args, **kwargs):
        """
        Returns the status types associated with the specified board.
        """
        endpoint_url = '{}/{}/statuses'.format(self.ENDPOINT_BOARDS, board_id)
        return self.fetch_resource(endpoint_url, should_page=True,
                                   *args, **kwargs)

    def get_boards(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_BOARDS, should_page=True,
                                   *args, **kwargs)

    def get_board(self, board_id):
        return self.fetch_resource('{}/{}'.format(
            self.ENDPOINT_BOARDS, board_id)
        )

    def get_priorities(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_PRIORITIES, should_page=True,
                                   *args, **kwargs)

    def get_slapriorities(self, sla_id, *args, **kwargs):
        endpoint_url = '{}/{}/priorities'.format(self.ENDPOINT_SLAS, sla_id)
        return self.fetch_resource(endpoint_url, should_page=True,
                                   *args, **kwargs)

    def get_teams(self, board_id, *args, **kwargs):
        endpoint = '{}/{}/teams/'.format(self.ENDPOINT_BOARDS, board_id)
        return self.fetch_resource(endpoint, should_page=True, *args, **kwargs)

    def get_locations(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_LOCATIONS, should_page=True,
                                   *args, **kwargs)

    def get_slas(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_SLAS, should_page=True,
                                   *args, **kwargs)

    def get_types(self, board_id, *args, **kwargs):
        endpoint_url = '{}/{}/types/'.format(self.ENDPOINT_BOARDS, board_id)
        return self.fetch_resource(endpoint_url, should_page=True,
                                   *args, **kwargs)

    def get_subtypes(self, board_id, *args, **kwargs):
        endpoint_url = '{}/{}/subtypes/'.format(self.ENDPOINT_BOARDS, board_id)
        return self.fetch_resource(endpoint_url, should_page=True,
                                   *args, **kwargs)

    def get_items(self, board_id, *args, **kwargs):
        endpoint_url = '{}/{}/items/'.format(self.ENDPOINT_BOARDS, board_id)
        return self.fetch_resource(endpoint_url, should_page=True,
                                   *args, **kwargs)

    def get_type_subtype_item_associations(self, board_id, *args, **kwargs):
        endpoint_url = '{}/{}/typeSubTypeItemAssociations/'.format(
            self.ENDPOINT_BOARDS, board_id)
        return self.fetch_resource(endpoint_url, should_page=True,
                                   *args, **kwargs)

    def get_sources(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_SOURCES, should_page=True,
                                   *args, **kwargs)


class ProjectAPIClient(TicketAPIMixin, ConnectWiseAPIClient):
    API = 'project'
    ENDPOINT_PROJECTS = 'projects/'
    ENDPOINT_PROJECT_STATUSES = 'statuses/'
    ENDPOINT_PROJECT_PHASES = 'phases/'
    ENDPOINT_PROJECT_TYPES = 'projectTypes/'
    ENDPOINT_PROJECT_TEAM_MEMBERS = 'teamMembers/'

    def get_project(self, project_id):
        endpoint_url = '{}/{}'.format(self.ENDPOINT_PROJECTS, project_id)
        return self.fetch_resource(endpoint_url)

    def get_projects(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_PROJECTS, should_page=True,
                                   *args, **kwargs)

    def get_project_statuses(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_PROJECT_STATUSES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_project_types(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_PROJECT_TYPES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_project_phases(self, project_id, *args, **kwargs):
        endpoint_url = '{}{}/{}'.format(
            self.ENDPOINT_PROJECTS, project_id, self.ENDPOINT_PROJECT_PHASES
        )
        return self.fetch_resource(endpoint_url,
                                   should_page=True,
                                   *args, **kwargs)

    def get_project_team_members(self, project_id, *args, **kwargs):
        endpoint_url = '{}{}/{}'.format(self.ENDPOINT_PROJECTS, project_id,
                                        self.ENDPOINT_PROJECT_TEAM_MEMBERS)
        return self.fetch_resource(endpoint_url,
                                   should_page=True,
                                   *args, **kwargs)

    def update_project(self, project, changed_fields):
        endpoint_url = self._endpoint(
            '{}{}'.format(self.ENDPOINT_PROJECTS, project.id)
        )
        return self.update_instance(project, changed_fields, endpoint_url)


class FinanceAPIClient(ConnectWiseAPIClient):
    API = 'finance'
    ENDPOINT_AGREEMENTS = 'agreements'

    def get_agreements(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_AGREEMENTS, should_page=True,
                                   *args, **kwargs)


class HostedAPIClient(SystemAPIClient):
    ENDPOINT_HOSTED_SETUPS = 'connectwisehostedsetups/'

    def post_hosted_tab(self, *args, **kwargs):
        endpoint_url = self._endpoint(self.ENDPOINT_HOSTED_SETUPS)

        body = {
            'screenId': kwargs.get('screen_id'),
            'description': kwargs.get('description'),
            'url': kwargs.get('url'),
            'origin': kwargs.get('origin'),
            'type': kwargs.get('type')
        }

        return self.request('post', endpoint_url, body)

    def get_hosted_tabs(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_HOSTED_SETUPS,
                                   should_page=True,
                                   *args, **kwargs)

    def delete_hosted_tab(self, hosted_tab_id):
        endpoint_url = self._endpoint(
            '{}/{}'.format(self.ENDPOINT_HOSTED_SETUPS, hosted_tab_id)
        )

        return requests.request('delete', endpoint_url, auth=self.auth)


class HostedReportAPIClient(ConnectWiseAPIClient):
    API = 'system/reports'
    ENDPOINT_HOSTED_REPORT = 'ConnectWiseHostedApiScreen/'

    def get_hosted_screen_ids(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_HOSTED_REPORT,
                                   *args, **kwargs)
