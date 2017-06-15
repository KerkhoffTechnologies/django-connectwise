import logging

from django.conf import settings
from djconnectwise.utils import RequestSettings
import re
import requests
from retrying import retry


class ConnectWiseAPIError(Exception):
    """Raise this, not request exceptions."""
    pass


class ConnectWiseRecordNotFoundError(ConnectWiseAPIError):
    """The record was not found."""
    pass


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


class ConnectWiseAPIClient(object):
    API = None

    def __init__(
        self,
        company_id=None,
        server_url=None,
        api_public_key=None,
        api_private_key=None,
        api_codebase=None
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
        if not api_codebase:
            api_codebase = settings.CONNECTWISE_CREDENTIALS['api_codebase']
        if not self.API:
            raise ValueError('API not specified')

        self.api_public_key = api_public_key
        self.api_private_key = api_private_key
        self.api_codebase = api_codebase

        self.server_url = '{0}/{1}/apis/3.0/{2}/'.format(
            server_url,
            self.api_codebase,
            self.API,
        )

        self.auth = ('{0}+{1}'.format(company_id, self.api_public_key),
                     '{0}'.format(self.api_private_key),)

        self.request_settings = RequestSettings().get_settings()
        self.timeout = self.request_settings['timeout']

    def _endpoint(self, path):
        return '{0}{1}'.format(self.server_url, path)

    def _log_failed(self, response):
        logger.error('FAILED API CALL: {0} - {1} - {2}'.format(
            response.url, response.status_code, response.content))

    def fetch_resource(self, endpoint_url, params=None, should_page=False,
                       retry_counter=None,
                       *args, **kwargs):
        """
        A convenience method for issuing a request to the
        specified REST endpoint.

        Note: retry_counter is used specifically for testing.
        It is a dict in the form {'count': 0} that is passed in
        to verify the number of attempts that were made.
        """
        @retry(stop_max_attempt_number=self.request_settings['max_attempts'],
               wait_exponential_multiplier=RETRY_WAIT_EXPONENTIAL_MULTAPPLIER,
               wait_exponential_max=RETRY_WAIT_EXPONENTIAL_MAX)
        def _fetch_resource(endpoint_url, params=None, should_page=False,
                            retry_counter=None,
                            *args, **kwargs):

            if retry_counter:
                retry_counter['count'] += 1

            if not params:
                params = {}

            if should_page:
                params['pageSize'] = kwargs.get('page_size',
                                                CW_RESPONSE_MAX_RECORDS)
                params['page'] = kwargs.get('page', CW_DEFAULT_PAGE)
            try:
                endpoint = self._endpoint(endpoint_url)
                logger.debug('Making GET request to {}'.format(endpoint))
                response = requests.get(
                    endpoint,
                    params=params,
                    auth=self.auth,
                    timeout=self.timeout,
                )
            except requests.RequestException as e:
                logger.error('Request failed: GET {}: {}'.format(endpoint, e))
                raise ConnectWiseAPIError('{}'.format(e))

            if 200 <= response.status_code < 300:
                return response.json()
            if response.status_code == 404:
                msg = 'Resource {} was not found.'.format(response.url)
                logger.warning(msg)
                raise ConnectWiseRecordNotFoundError(msg)
            else:
                self._log_failed(response)
                raise ConnectWiseAPIError(response.content)

        return _fetch_resource(endpoint_url, params=params,
                               should_page=should_page,
                               *args, **kwargs)


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
                'conditions': kwargs['conditions']
            }
        return self.fetch_resource(self.ENDPOINT_COMPANIES, should_page=True,
                                   *args, **kwargs)

    def get_company_statuses(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_COMPANY_STATUSES,
                                   should_page=True,
                                   *args, **kwargs)


class SalesAPIClient(ConnectWiseAPIClient):
    API = 'sales'
    ENDPOINT_OPPORTUNITIES = 'opportunities'
    ENDPOINT_OPPORTUNITY_STATUSES = \
        '{}/statuses'.format(ENDPOINT_OPPORTUNITIES)
    ENDPOINT_OPPORTUNITY_TYPES = \
        '{}/types'.format(ENDPOINT_OPPORTUNITIES)

    def by_id(self, opportunity_id):
        endpoint_url = '{}/{}'.format(
            self.ENDPOINT_OPPORTUNITIES, opportunity_id)
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

    def __init__(self, *args, **kwargs):
        self.extra_conditions = None
        if 'extra_conditions' in kwargs:
            self.extra_conditions = kwargs.pop('extra_conditions')

        super().__init__(*args, **kwargs)

    def get_conditions(self):
        default_conditions = settings.DJCONNECTWISE_DEFAULT_TICKET_CONDITIONS

        condition_list = [c for c in [
            default_conditions, self.extra_conditions] if c]
        conditions = ''

        for condition in condition_list:
            condition = '({})'.format(condition)
            if conditions:
                condition = ' AND {}'.format(condition)
            conditions += condition
        return conditions

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
        params = dict(
            conditions=self.get_conditions()
        )
        return self.fetch_resource(self.ENDPOINT_TICKETS, should_page=True,
                                   params=params, *args, **kwargs)

    def update_ticket_status(self, ticket_id, closed_flag, status):
        """
        Update the ticket's closedFlag and status on the server.
        """
        # Yeah, this schema is a bit bizarre. See CW docs at
        # https://developer.connectwise.com/Manage/Developer_Guide#Patch
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
        try:
            endpoint = self._endpoint(
                '{}/{}'.format(self.ENDPOINT_TICKETS, ticket_id)
            )
            logger.debug('Making PATCH request to {}'.format(endpoint))
            response = requests.patch(
                endpoint,
                json=body,
                auth=self.auth,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            logger.error('Request failed: PATCH {}: {}'.format(endpoint, e))
            raise ConnectWiseAPIError('{}'.format(e))

        if 200 <= response.status_code < 300:
            return response.json()
        else:
            self._log_failed(response)
            raise ConnectWiseAPIError(response.content)

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

    def get_teams(self, board_id, *args, **kwargs):
        endpoint = '{}/{}/teams/'.format(self.ENDPOINT_BOARDS, board_id)
        return self.fetch_resource(endpoint, should_page=True, *args, **kwargs)

    def get_locations(self, *args, **kwargs):
        return self.fetch_resource(self.ENDPOINT_LOCATIONS, should_page=True,
                                   *args, **kwargs)
