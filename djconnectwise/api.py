import logging
import re
import json
import pytz
from urllib.parse import urlparse

import requests
from retrying import retry

from django.conf import settings
from django.core.cache import cache
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
        self.api_base_url = None  # This will be set to the base URL for this
        # particular API-
        # i.e. https://connectwise.example.com/v4_6_release/apis/3.0/service/

        self.build_api_base_url(force_fetch=False)

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

    def build_api_base_url(self, force_fetch):
        api_codebase, codebase_updated = \
            self.info_manager.fetch_api_codebase(
                self.server_url, self.company_id, force_fetch=force_fetch
            )

        self.api_base_url = '{0}/{1}apis/3.0/{2}/'.format(
            self.server_url,
            api_codebase,
            self.API,
        )

        return codebase_updated

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
                logger.info(" URL: {}".format(response.url))

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
                    codebase_updated = self.build_api_base_url(
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


class ProjectAPIClient(ConnectWiseAPIClient):
    API = 'project'
    ENDPOINT_PROJECTS = 'projects/'
    ENDPOINT_PROJECT_STATUSES = 'statuses/'

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


class CompanyAPIClient(ConnectWiseAPIClient):
    API = 'company'
    ENDPOINT_COMPANIES = 'companies'
    ENDPOINT_COMPANY_STATUSES = '{}/statuses'.format(ENDPOINT_COMPANIES)
    ENDPOINT_COMPANY_TYPES = '{}/types'.format(ENDPOINT_COMPANIES)

    def by_id(self, company_id):
        endpoint_url = '{}/{}'.format(self.ENDPOINT_COMPANIES, company_id)
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

    def post_schedule_entry(self, *args, **kwargs):
        endpoint_url = self._endpoint(self.ENDPOINT_ENTRIES)

        body = {
                    "objectId": kwargs.get("objectId"),
                    "member": {
                        "id": kwargs.get("resource").id,
                        "identifier": kwargs.get("resource").identifier,
                        "name": str(kwargs.get("resource")),
                    },
                    "type": {
                        "id": kwargs.get("scheduleType").id,
                        "identifier": kwargs.get("scheduleType").identifier,
                    }
                }
        return self.request('post', endpoint_url, body)

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

    def update_opportunity_stage(self, obj_id, stage):
        """
        Update the opportunities' stage on the server.
        """
        # Yeah, this schema is a bit bizarre. See CW docs at
        # https://developer.connectwise.com/Manage/Developer_Guide#Patch
        endpoint_url = self._endpoint(
            '{}/{}'.format(self.ENDPOINT_OPPORTUNITIES, obj_id)
        )
        body = [
            {
                'op': 'replace',
                'path': 'stage',
                'value': {
                    'id': stage.id,
                    'name': stage.name,
                },
            },
        ]
        return self.request('patch', endpoint_url, body)


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


class ServiceAPIClient(ConnectWiseAPIClient):
    API = 'service'
    ENDPOINT_TICKETS = 'tickets'
    ENDPOINT_BOARDS = 'boards'
    ENDPOINT_PRIORITIES = 'priorities'
    ENDPOINT_LOCATIONS = 'locations'
    ENDPOINT_SLAS = 'SLAs'

    def tickets_count(self):
        params = dict(
            conditions=self.get_conditions(),
        )
        return self.fetch_resource(
            '{}/count'.format(self.ENDPOINT_TICKETS), params
        ).get('count', 0)

    def get_ticket(self, ticket_id):
        endpoint_url = '{}/{}'.format(self.ENDPOINT_TICKETS, ticket_id)
        return self.fetch_resource(endpoint_url)

    def get_tickets(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_TICKETS, should_page=True,
                                   *args, **kwargs)

    def update_ticket(self, ticket_id, closed_flag, priority, status):
        """
        Update the ticket's closedFlag and priority or status on the server.
        """
        # Yeah, this schema is a bit bizarre. See CW docs at
        # https://developer.connectwise.com/Manage/Developer_Guide#Patch
        endpoint_url = self._endpoint(
            '{}/{}'.format(self.ENDPOINT_TICKETS, ticket_id)
        )
        body = [
            {
                'op': 'replace',
                'path': 'closedFlag',
                'value': closed_flag
            },
            {
                'op': 'replace',
                'path': 'status',
                'value': {
                    'id': status.id,
                    'name': status.name,
                },
            },
        ]

        if priority:
            priority_body = {
                'op': 'replace',
                'path': 'priority',
                'value': {
                    'id': priority.id,
                    'name': priority.name,
                },
            }
            body.append(priority_body)

        return self.request('patch', endpoint_url, body)

    def get_notes(self, ticket_id, *args, **kwargs):
        """
        Returns the notes associated with the specific ticket.
        """
        endpoint_url = '{}/{}/notes'.format(self.ENDPOINT_TICKETS, ticket_id)
        return self.fetch_resource(endpoint_url, should_page=True,
                                   *args, **kwargs)

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
