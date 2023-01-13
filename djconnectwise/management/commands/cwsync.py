from collections import OrderedDict

from djconnectwise import sync, api
from djconnectwise.api import ConnectWiseSecurityPermissionsException
from djconnectwise.utils import DjconnectwiseSettings

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext_lazy as _

OPTION_NAME = 'connectwise_object'


class Command(BaseCommand):
    help = str(_('Synchronize the specified object with the Connectwise API'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # This can be replaced with a single instantiation of an OrderedDict
        # using kwargs in Python 3.6. But we need Python 3.5 compatibility for
        # now.
        # See https://www.python.org/dev/peps/pep-0468/.

        synchronizers = (
            ('member', sync.MemberSynchronizer, _('Member')),
            ('work_type', sync.WorkTypeSynchronizer,
             _('Work Type')),
            ('work_role', sync.WorkRoleSynchronizer,
             _('Work Role')),
            ('board', sync.BoardSynchronizer, _('Board')),
            ('team', sync.TeamSynchronizer, _('Team')),
            ('board_status', sync.BoardStatusSynchronizer, _('Board Status')),
            ('priority', sync.PrioritySynchronizer, _('Priority')),
            ('project_status', sync.ProjectStatusSynchronizer,
             _('Project Status')),
            ('project_type', sync.ProjectTypeSynchronizer,
             _('Project Type')),
            ('project', sync.ProjectSynchronizer, _('Project')),
            ('project_phase', sync.ProjectPhaseSynchronizer,
             _('Project Phase')),
            ('territory', sync.TerritorySynchronizer,
             _('Territory')),
            ('company_status', sync.CompanyStatusSynchronizer,
             _('Company Status')),
            ('company_type', sync.CompanyTypeSynchronizer, _('Company Type')),
            ('company', sync.CompanySynchronizer, _('Company')),
            ('communication_type', sync.CommunicationTypeSynchronizer,
             _('Communication Type')),
            ('contact', sync.ContactSynchronizer, _('Contact')),
            ('contact_communication',
             sync.ContactCommunicationSynchronizer,
             _('Contact Communication')),
            ('location', sync.LocationSynchronizer, _('Location')),
            ('opportunity_status', sync.OpportunityStatusSynchronizer,
             _('Opportunity Status')),
            ('opportunity_stage', sync.OpportunityStageSynchronizer,
             _('Opportunity Stage')),
            ('opportunity_type', sync.OpportunityTypeSynchronizer,
             _('Opportunity Type')),
            ('sales_probability', sync.SalesProbabilitySynchronizer,
             _('Sales Probability')),
            ('opportunity', sync.OpportunitySynchronizer,
             _('Opportunity')),
            ('holiday_list', sync.HolidayListSynchronizer,
             _('Holiday List')),
            ('holiday', sync.HolidaySynchronizer,
             _('Holiday')),
            ('calendar', sync.CalendarSynchronizer,
             _('Calendar')),
            ('company_other', sync.MyCompanyOtherSynchronizer,
             _('Company Other')),
            ('sla', sync.SLASynchronizer,
             _('Sla')),
            ('sla_priority', sync.SLAPrioritySynchronizer,
             _('Sla Priority')),
            ('type', sync.TypeSynchronizer,
             _('Type')),
            ('sub_type', sync.SubTypeSynchronizer,
             _('Sub Type')),
            ('item', sync.ItemSynchronizer,
             _('Item')),
            ('type_subtype_item_association',
             sync.TypeSubTypeItemAssociationSynchronizer,
             _('Type Subtype Item Association')),
            ('ticket', sync.ServiceTicketSynchronizer, _('Ticket')),
            ('project_ticket', sync.ProjectTicketSynchronizer,
             _('Project Ticket')),
            ('agreement', sync.AgreementSynchronizer,
             _('Agreement')),
            ('activity_status', sync.ActivityStatusSynchronizer,
             _('Activity Status')),
            ('activity_type', sync.ActivityTypeSynchronizer,
             _('Activity Type')),
            ('activity', sync.ActivitySynchronizer,
             _('Activity')),
            ('schedule_type', sync.ScheduleTypeSynchronizer,
             _('Schedule Type')),
            ('schedule_status', sync.ScheduleStatusSynchronizer,
             _('Schedule Status')),
            ('schedule_entry', sync.ScheduleEntriesSynchronizer,
             _('Schedule Entry')),
            ('project_team_member', sync.ProjectTeamMemberSynchronizer,
             _('Project Team Member')),
            ('source', sync.SourceSynchronizer,
             _('Source')),
            ('ticket_udf', sync.TicketUDFSynchronizer, _('Ticket UDF')),
            ('project_udf', sync.ProjectUDFSynchronizer, _('Project UDF')),
            ('activity_udf', sync.ActivityUDFSynchronizer, _('Activity UDF')),
            ('opportunity_udf', sync.OpportunityUDFSynchronizer,
             _('Opportunity UDF')),
        )

        settings = DjconnectwiseSettings().get_settings()
        if settings['sync_time_and_note_entries']:
            synchronizers = synchronizers + (
                ('service_note', sync.ServiceNoteSynchronizer,
                 _('Service Note')),
                ('opportunity_note', sync.OpportunityNoteSynchronizer,
                 _('Opportunity Note')),
                ('time_entry', sync.TimeEntrySynchronizer,
                 _('Time Entry'))
            )

        self.synchronizer_map = OrderedDict()
        for name, synchronizer, obj_name in synchronizers:
            self.synchronizer_map[name] = (synchronizer, obj_name)

    def add_arguments(self, parser):
        parser.add_argument(OPTION_NAME, nargs='?', type=str)
        parser.add_argument('--full',
                            action='store_true',
                            dest='full',
                            default=False)

    def sync_by_class(self, sync_class, obj_name, full_option=False):
        synchronizer = sync_class(full=full_option)

        created_count, updated_count, skipped_count, deleted_count = \
            synchronizer.sync()

        msg = _('{} Sync Summary - Created: {}, Updated: {}, Skipped: {}')
        fmt_msg = msg.format(obj_name, created_count, updated_count,
                             skipped_count)

        if full_option:
            msg = _('{} Sync Summary - Created: {}, Updated: {}, '
                    'Skipped: {}, Deleted: {}')
            fmt_msg = msg.format(obj_name, created_count, updated_count,
                                 skipped_count, deleted_count)

        self.stdout.write(fmt_msg)

    def handle(self, *args, **options):
        sync_classes = []
        connectwise_object_arg = options[OPTION_NAME]
        full_option = options.get('full', False)

        if connectwise_object_arg:
            object_arg = connectwise_object_arg
            sync_tuple = self.synchronizer_map.get(object_arg)

            if sync_tuple:
                sync_classes.append(sync_tuple)
            else:
                msg = _('Invalid CW object {}, '
                        'choose one of the following: \n{}')
                options_txt = ', '.join(self.synchronizer_map.keys())
                msg = msg.format(sync_tuple, options_txt)
                raise CommandError(msg)
        else:
            sync_classes = self.synchronizer_map.values()

        failed_classes = 0
        error_messages = ''

        for sync_class, obj_name in sync_classes:
            try:
                self.sync_by_class(sync_class, obj_name,
                                   full_option=full_option)
            except ConnectWiseSecurityPermissionsException as e:
                msg = 'Failed to sync {}: {}'.format(obj_name, e)
                self.stderr.write(msg)
                error_messages += '{}\n'.format(msg)
            except api.ConnectWiseAPIError as e:
                msg = 'Failed to sync {}: {}'.format(obj_name, e)
                self.stderr.write(msg)
                error_messages += '{}\n'.format(msg)
                failed_classes += 1

        if failed_classes > 0:
            msg = '{} class{} failed to sync.\n'.format(
                failed_classes,
                '' if failed_classes == 1 else 'es',
            )
            msg += 'Errors:\n'
            msg += error_messages
            raise CommandError(msg)
