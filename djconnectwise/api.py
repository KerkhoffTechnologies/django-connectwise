import logging
import re

import requests
from retrying import retry

from django.conf import settings
from django.core.cache import cache
from djconnectwise.utils import RequestSettings


class ConnectWiseAPIError(Exception):
    """Raise this, not request exceptions."""
    pass


class ConnectWiseAPIClientError(ConnectWiseAPIError):
    """
    Raise this to indicate any http error that falls within the
    4xx class of http status codes.
    """
    pass


class ConnectWiseRecordNotFoundError(ConnectWiseAPIClientError):
    """The record was not found."""
    pass


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


class CompanyInfoManager:
    COMPANYINFO_PATH = '/login/companyinfo/connectwise'

    def get_company_info(self, server_url):
        company_endpoint = '{0}{1}'.format(server_url, self.COMPANYINFO_PATH)

        try:
            logger.debug('Making GET request to {}'.format(company_endpoint))
            response = requests.get(company_endpoint)
            if 200 <= response.status_code < 300:
                return response.json()
            else:
                raise ConnectWiseAPIError(response.content)
        except requests.RequestException as e:
            raise ConnectWiseAPIError(
                'CompanyInfo request failed: GET {}: {}'.format(
                    company_endpoint, e
                )
            )

    def fetch_api_codebase(self, server_url, force_fetch=True):
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
                company_info_json = self.get_company_info(server_url)
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
        api_public_key=None,
        api_private_key=None,
    ):
        if not company_id:
            company_id = settings.CONNECTWISE_CREDENTIALS['company_id']
        if not server_url:
            server_url = settings.CONNECTWISE_SERVER_URL
        if not api_public_key:
            api_public_key = settings.CONNECTWISE_CREDENTIALS['api_public_key']
        if not api_private_key:
            api_private_key = settings.CONNECTWISE_CREDENTIALS[
                'api_private_key'
            ]

        if not self.API:
            raise ValueError('API not specified')

        self.info_manager = CompanyInfoManager()
        self.api_public_key = api_public_key
        self.api_private_key = api_private_key
        self.server_url = server_url
        self.auth = (
            '{0}+{1}'.format(company_id, self.api_public_key),
            '{0}'.format(self.api_private_key),
        )

        self.request_settings = RequestSettings().get_settings()
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

    def build_api_base_url(self, force_fetch):
        api_codebase, codebase_updated = \
            self.info_manager.fetch_api_codebase(
                self.server_url, force_fetch=force_fetch
            )

        self.api_base_url = '{0}/{1}apis/3.0/{2}/'.format(
            self.server_url,
            api_codebase,
            self.API,
        )

        return codebase_updated

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

                if 'conditions' in params:
                    logger.debug('Conditions: {}'.format(
                        params['conditions']))
                    conditions_str = "conditions=" + params['conditions']
                    # URL encode needed characters
                    conditions_str = conditions_str.replace("+", "%2B")
                    conditions_str = conditions_str.replace(" ", "+")
                else:
                    conditions_str = ""

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
                    timeout=self.timeout
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
                raise ConnectWiseAPIClientError(response.content)

            else:
                self._log_failed(response)
                raise ConnectWiseAPIError(response.content)

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

    def request(self, method, endpoint_url, body):
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
            )
        except requests.RequestException as e:
            logger.error(
                'Request failed: {} {}: {}'.format(method, endpoint_url, e)
            )
            raise ConnectWiseAPIError('{}'.format(e))

        if 200 <= response.status_code < 300:
            return response.json()
        else:
            self._log_failed(response)
            raise ConnectWiseAPIError(response.content)


class ProjectAPIClient(ConnectWiseAPIClient):
    API = 'project'
    ENDPOINT_PROJECTS = 'projects/'

    def get_project(self, project_id):
        endpoint_url = '{}/{}'.format(self.ENDPOINT_PROJECTS, project_id)
        return self.fetch_resource(endpoint_url)

    def get_projects(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_PROJECTS, should_page=True,
                                   *args, **kwargs)


class CompanyAPIClient(ConnectWiseAPIClient):
    API = 'company'
    ENDPOINT_COMPANIES = 'companies'
    ENDPOINT_COMPANY_STATUSES = '{}/statuses'.format(ENDPOINT_COMPANIES)

    def by_id(self, company_id):
        endpoint_url = '{}/{}'.format(self.ENDPOINT_COMPANIES, company_id)
        return self.fetch_resource(endpoint_url)

    def get_companies(self, *args, **kwargs):
        if 'conditions' in kwargs:
            kwargs['params'] = {
                'conditions': self.prepare_conditions(kwargs['conditions'])
            }
        return self.fetch_resource(self.ENDPOINT_COMPANIES, should_page=True,
                                   *args, **kwargs)

    def get_company_statuses(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_COMPANY_STATUSES,
                                   should_page=True,
                                   *args, **kwargs)


class ScheduleAPIClient(ConnectWiseAPIClient):
    API = 'schedule'
    ENDPOINT_ENTRIES = 'entries'
    ENDPOINT_SCHEDULE_TYPES = 'types'
    ENDPOINT_SCHEDULE_STATUSES = 'statuses'

    def get_schedule_statuses(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_SCHEDULE_STATUSES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_schedule_types(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_SCHEDULE_TYPES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_schedule_entries(self, *args, **kwargs):
        if 'conditions' in kwargs:
            kwargs['params'] = {
                'conditions': self.prepare_conditions(kwargs['conditions'])
            }
        return self.fetch_resource(self.ENDPOINT_ENTRIES,
                                   should_page=True,
                                   *args, **kwargs)

    def get_schedule_entry(self, entry_id):
        endpoint_url = '{}/{}'.format(self.ENDPOINT_ENTRIES, entry_id)
        return self.fetch_resource(endpoint_url)


class SalesAPIClient(ConnectWiseAPIClient):
    API = 'sales'
    ENDPOINT_OPPORTUNITIES = 'opportunities'
    ENDPOINT_OPPORTUNITY_STATUSES = \
        '{}/statuses'.format(ENDPOINT_OPPORTUNITIES)
    ENDPOINT_OPPORTUNITY_TYPES = \
        '{}/types'.format(ENDPOINT_OPPORTUNITIES)
    ENDPOINT_ACTIVITIES = 'activities'

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
    ENDPOINT_MEMBERS_IMAGE = 'members/{}/image'
    ENDPOINT_MEMBERS_COUNT = 'members/count'
    ENDPOINT_CALLBACKS = 'callbacks/'
    ENDPOINT_INFO = 'info/'

    def get_connectwise_version(self):
        result = self.fetch_resource(self.ENDPOINT_INFO)
        return result.get('version', '')

    def get_members(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_MEMBERS,
                                   should_page=True, *args, **kwargs)

    def get_member_count(self):
        return self.fetch_resource(self.ENDPOINT_MEMBERS_COUNT)

    def get_callbacks(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_CALLBACKS,
                                   should_page=True, *args, **kwargs)

    def delete_callback(self, entry_id):
        try:
            endpoint = self._endpoint(
                '{}{}'.format(self.ENDPOINT_CALLBACKS, entry_id)
            )
            logger.debug('Making DELETE request to {}'.format(endpoint))
            response = requests.request(
                'delete',
                endpoint,
                auth=self.auth,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            logger.error('Request failed: DELETE {}: {}'.format(endpoint, e))
            raise ConnectWiseAPIError('{}'.format(e))

        response.raise_for_status()
        return response

    def create_callback(self, callback_entry):
        try:
            endpoint = self._endpoint(self.ENDPOINT_CALLBACKS)
            logger.debug('Making POST request to {}'.format(endpoint))
            response = requests.request(
                'post',
                endpoint,
                json=callback_entry,
                auth=self.auth,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            logger.error('Request failed: POST {}: {}'.format(endpoint, e))
            raise ConnectWiseAPIError('{}'.format(e))

        if 200 <= response.status_code < 300:
            return response.json()
        else:
            self._log_failed(response)
            raise ConnectWiseAPIError(response.content)

    def update_callback(self, callback_entry):
        try:
            endpoint = self._endpoint(
                'callbacks/{0}'.format(callback_entry.entry_id)
            )
            logger.debug('Making PUT request to {}'.format(endpoint))
            response = requests.request(
                'put',
                endpoint,
                json=callback_entry,
                auth=self.auth,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            logger.error('Request failed: PUT {}: {}'.format(endpoint, e))
            raise ConnectWiseAPIError('{}'.format(e))

        if 200 <= response.status_code < 300:
            return response.json()
        else:
            self._log_failed(response)
            raise ConnectWiseAPIError(response.content)

    def get_member_by_identifier(self, identifier):
        return self.fetch_resource('members/{0}'.format(identifier))

    def get_member_image_by_identifier(self, identifier):
        """
        Return a (filename, content) tuple.
        """
        try:
            endpoint = self._endpoint(
                self.ENDPOINT_MEMBERS_IMAGE.format(identifier)
            )
            logger.debug('Making GET request to {}'.format(endpoint))
            response = requests.get(
                endpoint,
                auth=self.auth,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            logger.error('Request failed: GET {}: {}'.format(endpoint, e))
            raise ConnectWiseAPIError('{}'.format(e))

        if 200 <= response.status_code < 300:
            headers = response.headers
            content_disposition_header = headers.get('Content-Disposition',
                                                     default='')
            msg = "Got member '{}' image; size {} bytes " \
                "and content-disposition header '{}'"

            logger.info(msg.format(
                identifier,
                len(response.content),
                content_disposition_header
            ))
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
        if 'conditions' in kwargs:
            kwargs['params'] = {
                'conditions': self.prepare_conditions(kwargs['conditions'])
            }
        return self.fetch_resource(self.ENDPOINT_TICKETS, should_page=True,
                                   *args, **kwargs)

    def update_ticket_status(self, ticket_id, closed_flag, status):
        """
        Update the ticket's closedFlag and status on the server.
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
        return self.request('patch', endpoint_url, body)

    def get_statuses(self, board_id, *args, **kwargs):
        """
        Returns the status types associated with the specified board.
        """
        endpoint_url = '{}/{}/statuses'.format(self.ENDPOINT_BOARDS, board_id)
        if 'conditions' in kwargs:
            kwargs['params'] = {
                'conditions': self.prepare_conditions(kwargs['conditions'])
            }
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

    def get_teams(self, board_id, *args, **kwargs):
        endpoint = '{}/{}/teams/'.format(self.ENDPOINT_BOARDS, board_id)
        return self.fetch_resource(endpoint, should_page=True, *args, **kwargs)

    def get_locations(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_LOCATIONS, should_page=True,
                                   *args, **kwargs)
