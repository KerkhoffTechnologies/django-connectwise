import os
from mock import patch

from datetime import datetime, date, time
import json
import responses

from . import fixtures
from django.utils import timezone

CW_MEMBER_IMAGE_FILENAME = 'AnonymousMember.png'


def create_mock_call(method_name, return_value, side_effect=None):
    """Utility function for mocking the specified function or method"""
    _patch = patch(method_name, side_effect=side_effect)
    mock_get_call = _patch.start()

    if not side_effect:
        mock_get_call.return_value = return_value

    return mock_get_call, _patch


def company_api_get_contacts(return_value):
    method_name = 'djconnectwise.api.CompanyAPIClient.get_contacts'
    return create_mock_call(method_name, return_value)


def company_api_get_communication_types(return_value):
    method_name = 'djconnectwise.api.CompanyAPIClient.get_communication_types'
    return create_mock_call(method_name, return_value)


def company_api_get_contact_communications(return_value):
    method_name = 'djconnectwise.api.CompanyAPIClient.' \
                  'get_contact_communications'
    return create_mock_call(method_name, return_value)


def company_info_get_company_info_call(return_value):
    method_name = 'djconnectwise.api.CompanyInfoManager.get_company_info'
    return create_mock_call(method_name, return_value)


def company_api_get_call(return_value):
    method_name = 'djconnectwise.api.CompanyAPIClient.get_companies'
    return create_mock_call(method_name, return_value)


def company_api_by_id_call(return_value, raised=None):
    method_name = 'djconnectwise.api.CompanyAPIClient.by_id'
    return create_mock_call(method_name, return_value, side_effect=raised)


def company_api_get_company_statuses_call(return_value, raised=None):
    method_name = 'djconnectwise.api.CompanyAPIClient.get_company_statuses'
    return create_mock_call(method_name, return_value, side_effect=raised)


def company_api_get_company_types_call(return_value, raised=None):
    method_name = 'djconnectwise.api.CompanyAPIClient.get_company_types'
    return create_mock_call(method_name, return_value, side_effect=raised)


def projects_api_get_project_statuses_call(return_value, raised=None):
    method_name = 'djconnectwise.api.ProjectAPIClient.get_project_statuses'
    return create_mock_call(method_name, return_value, side_effect=raised)


def projects_api_get_project_types_call(return_value, raised=None):
    method_name = 'djconnectwise.api.ProjectAPIClient.get_project_types'
    return create_mock_call(method_name, return_value, side_effect=raised)


def projects_api_get_project_phases_call(return_value, raised=None):
    method_name = 'djconnectwise.api.ProjectAPIClient.get_project_phases'
    return create_mock_call(method_name, return_value, side_effect=raised)


def project_api_get_projects_call(return_value):
    method_name = 'djconnectwise.api.ProjectAPIClient.get_projects'
    return create_mock_call(method_name, return_value)


def project_api_get_project_call(return_value, raised=None):
    method_name = 'djconnectwise.api.ProjectAPIClient.get_project'
    return create_mock_call(method_name, return_value, side_effect=raised)


def project_api_get_team_members_call(return_value):
    method_name = 'djconnectwise.api.ProjectAPIClient.get_project_team_members'
    return create_mock_call(method_name, return_value)


def _project_api_tickets_call(page=1, page_size=25, conditions=[]):
    return_value = []
    test_date = date(1948, 5, 14)
    test_time = time(12, 0, 0, tzinfo=timezone.get_current_timezone())
    test_datetime = datetime.combine(test_date, test_time)
    conditions.append('lastUpdated>' + timezone.localtime(
        value=test_datetime).isoformat()
                      )
    if page == 1:
        return_value = [fixtures.API_PROJECT_TICKET]

    return return_value


def project_api_tickets_call():
    method_name = 'djconnectwise.api.TicketAPIMixin.get_tickets'
    mock_call, _patch = create_mock_call(
        method_name,
        None,
        side_effect=_project_api_tickets_call)
    return mock_call, _patch


def project_api_tickets_test_command(return_value):
    method_name = 'djconnectwise.api.TicketAPIMixin.get_tickets'
    mock_call, _patch = create_mock_call(method_name, return_value)
    return mock_call, _patch


def sales_api_by_id_call(return_value, raised=None):
    method_name = 'djconnectwise.api.SalesAPIClient.by_id'
    return create_mock_call(method_name, return_value, side_effect=raised)


def sales_api_get_opportunities_call(return_value, raised=None):
    method_name = 'djconnectwise.api.SalesAPIClient.get_opportunities'
    return create_mock_call(method_name, return_value, side_effect=raised)


def sales_api_get_opportunity_statuses_call(return_value, raised=None):
    method_name = 'djconnectwise.api.SalesAPIClient.get_opportunity_statuses'
    return create_mock_call(method_name, return_value, side_effect=raised)


def sales_api_get_opportunity_types_call(return_value, raised=None):
    method_name = 'djconnectwise.api.SalesAPIClient.get_opportunity_types'
    return create_mock_call(method_name, return_value, side_effect=raised)


def sales_api_get_opportunity_stages_call(return_value, raised=None):
    method_name = 'djconnectwise.api.SalesAPIClient.get_opportunity_stages'
    return create_mock_call(method_name, return_value, side_effect=raised)


def sales_api_get_sales_probabilities_call(return_value, raised=None):
    method_name = 'djconnectwise.api.SalesAPIClient.get_probabilities'
    return create_mock_call(method_name, return_value, side_effect=raised)


def schedule_api_get_schedule_types_call(return_value, raised=None):
    method_name = 'djconnectwise.api.ScheduleAPIClient.get_schedule_types'
    return create_mock_call(method_name, return_value, side_effect=raised)


def schedule_api_get_schedule_statuses_call(return_value, raised=None):
    method_name = 'djconnectwise.api.ScheduleAPIClient.get_schedule_statuses'
    return create_mock_call(method_name, return_value, side_effect=raised)


def schedule_api_get_schedule_entries_call(return_value, raised=None):
    method_name = 'djconnectwise.api.ScheduleAPIClient.get_schedule_entries'
    return create_mock_call(method_name, return_value, side_effect=raised)


def schedule_api_get_schedule_entry_call(return_value, raised=None):
    method_name = 'djconnectwise.api.ScheduleAPIClient.get_schedule_entry'
    return create_mock_call(method_name, return_value, side_effect=raised)


def schedule_api_get_calendars_call(return_value, raised=None):
    method_name = 'djconnectwise.api.ScheduleAPIClient.get_calendars'
    return create_mock_call(method_name, return_value, side_effect=raised)


def schedule_api_get_holidays_call(return_value, raised=None):
    method_name = 'djconnectwise.api.ScheduleAPIClient.get_holidays'
    return create_mock_call(method_name, return_value, side_effect=raised)


def schedule_api_get_holiday_lists_call(return_value, raised=None):
    method_name = 'djconnectwise.api.ScheduleAPIClient.get_holiday_lists'
    return create_mock_call(method_name, return_value, side_effect=raised)


def time_api_get_time_entries_call(return_value, raised=None):
    method_name = 'djconnectwise.api.TimeAPIClient.get_time_entries'
    return create_mock_call(method_name, return_value, side_effect=raised)


def sales_api_get_activities_call(return_value, raised=None):
    method_name = 'djconnectwise.api.SalesAPIClient.get_activities'
    return create_mock_call(method_name, return_value, side_effect=raised)


def sales_api_get_activities_statuses_call(return_value, raised=None):
    method_name = 'djconnectwise.api.SalesAPIClient.get_activity_statuses'
    return create_mock_call(method_name, return_value, side_effect=raised)


def sales_api_get_activities_types_call(return_value, raised=None):
    method_name = 'djconnectwise.api.SalesAPIClient.get_activity_types'
    return create_mock_call(method_name, return_value, side_effect=raised)


def sales_api_get_single_activity_call(return_value, raised=None):
    method_name = 'djconnectwise.api.SalesAPIClient.get_single_activity'
    return create_mock_call(method_name, return_value, side_effect=raised)


def _service_api_tickets_call(page=1, page_size=25, conditions=[]):
    return_value = []
    test_date = date(1948, 5, 14)
    test_time = time(12, 0, 0, tzinfo=timezone.get_current_timezone())
    test_datetime = datetime.combine(test_date, test_time)
    conditions.append('lastUpdated>' + timezone.localtime(
        value=test_datetime).isoformat()
        )
    if page == 1:
        return_value = [fixtures.API_SERVICE_TICKET]
    return return_value


def service_api_tickets_call():
    method_name = 'djconnectwise.api.TicketAPIMixin.get_tickets'
    mock_call, _patch = create_mock_call(
        method_name,
        None,
        side_effect=_service_api_tickets_call)
    return mock_call, _patch


def _service_api_get_ticket_call(ticket_id):
    return fixtures.API_SERVICE_TICKET_MAP.get(ticket_id)


def service_api_get_ticket_call(raised=None):
    method_name = 'djconnectwise.api.TicketAPIMixin.get_ticket'
    mock_call, _patch = create_mock_call(
        method_name,
        None,
        side_effect=raised if raised else _service_api_get_ticket_call)
    return mock_call, _patch


def service_api_get_boards_call(return_value):
    method_name = 'djconnectwise.api.ServiceAPIClient.get_boards'
    return create_mock_call(method_name, return_value)


def service_api_update_ticket_call(return_value):
    method_name = 'djconnectwise.api.ServiceAPIClient.update_ticket'
    return create_mock_call(method_name, return_value)


def service_api_get_statuses_call(return_value):
    method_name = 'djconnectwise.api.ServiceAPIClient.get_statuses'
    return create_mock_call(method_name, return_value)


def service_api_get_priorities_call(return_value):
    method_name = 'djconnectwise.api.ServiceAPIClient.get_priorities'
    return create_mock_call(method_name, return_value)


def service_api_get_teams_call(return_value):
    method_name = 'djconnectwise.api.ServiceAPIClient.get_teams'
    return create_mock_call(method_name, return_value)


def service_api_get_notes_call(return_value):
    method_name = 'djconnectwise.api.ServiceAPIClient.get_notes'
    return create_mock_call(method_name, return_value)


def service_api_get_slas_call(return_value):
    method_name = 'djconnectwise.api.ServiceAPIClient.get_slas'
    return create_mock_call(method_name, return_value)


def service_api_get_sla_priorities_call(return_value):
    method_name = 'djconnectwise.api.ServiceAPIClient.get_slapriorities'
    return create_mock_call(method_name, return_value)


def service_api_get_types_call(return_value):
    method_name = 'djconnectwise.api.ServiceAPIClient.get_types'
    return create_mock_call(method_name, return_value)


def service_api_get_subtypes_call(return_value):
    method_name = 'djconnectwise.api.ServiceAPIClient.get_subtypes'
    return create_mock_call(method_name, return_value)


def service_api_get_items_call(return_value):
    method_name = 'djconnectwise.api.ServiceAPIClient.get_items'
    return create_mock_call(method_name, return_value)


def service_api_get_type_subtype_item_associations_call(return_value):
    method_name = \
        'djconnectwise.api.ServiceAPIClient.get_type_subtype_item_associations'
    return create_mock_call(method_name, return_value)


def sales_api_get_opportunity_notes_call(return_value):
    method_name = 'djconnectwise.api.SalesAPIClient.get_notes'
    return create_mock_call(method_name, return_value)


def service_api_get_locations_call(return_value):
    method_name = 'djconnectwise.api.ServiceAPIClient.get_locations'
    return create_mock_call(method_name, return_value)


def system_api_get_connectwise_version_call(return_value):
    method_name = 'djconnectwise.api.SystemAPIClient.get_connectwise_version'
    return create_mock_call(method_name, return_value)


def system_api_get_members_call(return_value):
    method_name = 'djconnectwise.api.SystemAPIClient.get_members'
    return create_mock_call(method_name, return_value)


def system_api_get_member_image_by_photo_id_call(return_value):
    method_name = 'djconnectwise.api.SystemAPIClient.' \
                  + 'get_member_image_by_photo_id'

    return create_mock_call(method_name, return_value)


def system_api_get_member_count_call(return_value):
    method_name = 'djconnectwise.api.SystemAPIClient.get_members'
    return create_mock_call(method_name, return_value)


def system_api_create_callback_call(return_value):
    method_name = 'djconnectwise.api.SystemAPIClient.create_callback'
    return create_mock_call(method_name, return_value)


def system_api_delete_callback_call(return_value):
    method_name = 'djconnectwise.api.SystemAPIClient.delete_callback'
    return create_mock_call(method_name, return_value)


def system_api_get_callbacks_call(return_value):
    method_name = 'djconnectwise.api.SystemAPIClient.get_callbacks'
    return create_mock_call(method_name, return_value)


def system_api_get_territories_call(return_value):
    method_name = 'djconnectwise.api.SystemAPIClient.get_territories'
    return create_mock_call(method_name, return_value)


def system_api_get_other_call(return_value):
    method_name = 'djconnectwise.api.SystemAPIClient.get_mycompanyother'
    return create_mock_call(method_name, return_value)


def cw_api_fetch_resource_call(return_value):
    method_name = 'djconnectwise.api.ConnectWiseAPIClient.fetch_resource'
    return create_mock_call(method_name, return_value)


def get(url, data, headers=None, status=200):
    """Set up requests mock for given URL and JSON-serializable data."""
    get_raw(url, json.dumps(data), "application/json", headers, status=status)


def time_api_get_work_types_call(return_value):
    method_name = 'djconnectwise.api.TimeAPIClient.get_work_types'
    return create_mock_call(method_name, return_value)


def time_api_get_work_roles_call(return_value):
    method_name = 'djconnectwise.api.TimeAPIClient.get_work_roles'
    return create_mock_call(method_name, return_value)


def finance_api_get_agreements_call(return_value):
    method_name = 'djconnectwise.api.FinanceAPIClient.get_agreements'
    return create_mock_call(method_name, return_value)


def get_raw(url, data, content_type="application/octet-stream", headers=None,
            status=200):
    """Set up requests mock for given URL."""
    responses.add(
        responses.GET,
        url,
        body=data,
        status=status,
        content_type=content_type,
        adding_headers=headers,
    )


def get_member_avatar():
    """Return the avatar image data in the tests directory."""
    cw_member_image_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        CW_MEMBER_IMAGE_FILENAME
    )
    with open(cw_member_image_path, 'rb') as anonymous_image_file:
        return anonymous_image_file.read()
