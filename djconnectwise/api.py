import logging
import requests

from django.conf import settings


logger = logging.getLogger(__name__)


class ConnectWiseAPIClient(object):
    API = None

    def __init__(
        self,
        company_id=settings.CONNECTWISE_CREDENTIALS['company_id'],
        integrator_login_id=settings.CONNECTWISE_CREDENTIALS[
            'integrator_login_id'],
        integrator_password=settings.CONNECTWISE_CREDENTIALS[
            'integrator_password'],
        url=settings.CONNECTWISE_SERVER_URL,
        api_public_key=settings.CONNECTWISE_CREDENTIALS['api_public_key'],
        api_private_key=settings.CONNECTWISE_CREDENTIALS['api_private_key'],
        api_codebase=settings.CONNECTWISE_CREDENTIALS['api_codebase']
    ):  # TODO - kwarg should be changed to server_url

        if not self.API:
            raise ValueError('API not specified')

        self.url = url
        self.company_id = company_id
        self.integrator_login_id = integrator_login_id
        self.integrator_password = integrator_password
        self.api_public_key = api_public_key
        self.api_private_key = api_private_key
        self.api_codebase = api_codebase


class ConnectWiseRESTAPIClient(ConnectWiseAPIClient):

    def __init__(self, *args, **kwargs):
        super(ConnectWiseRESTAPIClient, self).__init__(*args, **kwargs)
        self.url = '{0}/{1}/apis/3.0/{2}/'.format(
            self.url,
            self.api_codebase,
            self.API,
        )

        self.auth = ('{0}+{1}'.format(self.company_id, self.api_public_key),
                     '{0}'.format(self.api_private_key),)

    def _endpoint(self, path):
        return '{0}{1}'.format(self.url, path)

    def _log_failed(self, response):
        logger.info('FAILED API CALL: {0} - {1} - {2}'.format(
            response.url, response.status_code, response.content))

    def fetch_resource(self, endpoint_url, params=None):
        """
        A convenience method for issuing a request to the
        specified REST endpoint
        """
        if not params:
            params = {}

        response = requests.get(
            self._endpoint(endpoint_url),
            params=params,
            auth=self.auth
        )

        if 200 <= response.status_code < 300:
            return response.json()
        else:
            self._log_failed(response)


class ProjectAPIClient(ConnectWiseRESTAPIClient):
    API = 'project'

    def get_projects(self):
        return self.fetch_resource('projects/')


class SystemAPIClient(ConnectWiseRESTAPIClient):
    API = 'system'

    def get_connectwise_version(self):
        return self.fetch_resource('info/').get('version', '')

    def get_members(self):
        response_json = self.get_member_count()

        if len(response_json) == 1:
            per_page = response_json['count']
        else:
            per_page = 1000  # max 1000

        return self.fetch_resource('members/?pageSize=' + str(per_page))

    def get_member_count(self):
        return self.fetch_resource('members/count')

    def get_callbacks(self):
        return self.fetch_resource('callbacks/')

    def delete_callback(self, entry_id):
        response = requests.request(
            'delete',
            self._endpoint('callbacks/{0}'.format(entry_id)),
            auth=self.auth
        )
        response.raise_for_status()
        return response

    def create_callback(self, callback_entry):
        response = requests.request(
            'post',
            self._endpoint('callbacks/'),
            json=callback_entry,
            auth=self.auth
        )

        if 200 <= response.status_code < 300:
            return response.json()
        else:
            self._log_failed(response)

        return {}

    def update_callback(self, callback_entry):
        response = requests.request(
            'put',
            self._endpoint('callbacks/{0}'.format(callback_entry.entry_id)),
            json=callback_entry,
            auth=self.auth
        )

        return response

    def get_member_by_identifier(self, identifier):
        return self.fetch_resource('members/{0}'.format(identifier))

    def get_member_image_by_identifier(self, identifier):

        response = requests.get(
            self._endpoint('members/{0}/image'.format(identifier)),
            auth=self.auth
        )

        if 200 <= response.status_code < 300:
            return response.content
        else:
            self._log_failed(response)
        return {}


class CompanyAPIRestClient(ConnectWiseRESTAPIClient):
    API = 'company'
    ENDPOINT_URL = 'companies'

    def get_company_by_id(self, company_id):
        endpoint_url = '{}/{}'.format(self.ENDPOINT_URL,
                                      company_id)
        return self.fetch_resource(endpoint_url)

    def get(self):
        return self.fetch_resource(self.ENDPOINT_URL)


class ServiceAPIRestClient(ConnectWiseRESTAPIClient):
    API = 'service'

    def __init__(self, *args, **kwargs):
        self.extra_conditions = None
        if 'extra_conditions' in kwargs:
            self.extra_conditions = kwargs.pop('extra_conditions')

        super(ServiceAPIRestClient, self).__init__(*args, **kwargs)

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
        return self.fetch_resource('tickets/count', params).get('count', 0)

    def get_ticket(self, ticket_id):
        endpoint_url = 'tickets/{}'.format(ticket_id)
        return self.fetch_resource(endpoint_url)

    def get_tickets(self, page=0, page_size=25):
        params = dict(
            page=page,
            pageSize=page_size,
            conditions=self.get_conditions()
        )

        return self.fetch_resource('tickets', params=params)

    def update_ticket(self, ticket):
        response = requests.request(
            'put',
            self._endpoint('tickets/{}'.format(ticket['id'])),
            params=dict(id=ticket['id'], body=ticket),
            json=ticket,
            auth=self.auth
        )

        return response

    def get_statuses(self, board_id):
        """
        Returns the status types associated with the
        specified board id
        """
        endpoint_url = 'boards/{}/statuses'.format(board_id)

        return self.fetch_resource(endpoint_url)

    def get_boards(self):
        return self.fetch_resource('boards')

    def get_board(self, board_id):
        return self.fetch_resource('boards/{}'.format(board_id))
