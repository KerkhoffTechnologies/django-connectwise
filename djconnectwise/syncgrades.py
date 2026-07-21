"""
SyncGrade and SyncGrades are a copy of djpsa.sync.grades. They don't
need to be migrated when ConnectWiseSyncGrades is migrated.
"""
from djconnectwise import sync


class SyncGrade:
    description = ""
    synchronizers = []
    # For app to describe the frequency of use. (ie "Every 5 minutes.")
    schedule = ""

    def __init__(self, description=None, synchronizers=None):
        self.description = description
        self.synchronizers = \
            synchronizers if synchronizers is not None else []


class SyncGrades:
    """
    Define grades of synchronizers.

    The result of operational+configuration+slow grades+ludicrous slow
    should be all the synchronizers.
    """
    def __init__(self, *args, **kwargs):
        self.filter_cb = kwargs.pop('filter_cb', None)
        self.grades = {
            'partial': SyncGrade(
                """Resources that are useful to keep up-to-date at high
                   frequency and can be retrieved by limiting to those
                   which have changed recently.""",
                []
            ),
            # Synchronizers for resources that change throughout a typical
            # day. For example, tickets, service calls, notes, etc.
            # Exclude resources that can potentially take a very long time
            # to sync.
            'operational': SyncGrade(
                """Resources that change throughout a day.""",
                []
            ),
            # Synchronizers for resources that change infrequently- such as
            # on a weekly or monthly basis. For example, ticket types,
            # statuses, priorities, etc.
            'configuration': SyncGrade(
                """Resources that change infrequently.""",
                []
            ),
            # Synchronizers for resources that can potentially take a very long
            # time to sync. For example, notes, time entries, etc.
            'slow': SyncGrade(
                """Resources that can take a long time to retrieve.""",
                []
            ),
            # Synchronizers for resources that can take an unbelievable
            # amount of time to sync, so much it makes you cry.
            'ludicrous_slow': SyncGrade(
                """Resources that can take an unbelievable amount of time
                   to retrieve.""",
                []
            ),
        }

    def get_grade(self, grade_key):
        grade = self.grades.get(grade_key)
        if grade and self.filter_cb:
            grade = self.filter_cb(grade)
        return grade


class ConnectWiseSyncGrades(SyncGrades):
    def __init__(self, *args, **kwargs):
        super(ConnectWiseSyncGrades, self).__init__(*args, **kwargs)
        # Don't sync classes that use BoardChildSynchronizer in partial
        # because that results in a request per board and some
        # customers have a lot of boards.
        self.grades['partial'].synchronizers = [
            sync.MemberSynchronizer,
            sync.CompanySynchronizer,
            sync.AgreementTypeSynchronizer,
            sync.AgreementSynchronizer,
            sync.ContactSynchronizer,
            sync.ProjectSynchronizer,
            sync.ServiceTicketSynchronizer,
            sync.ProjectTicketSynchronizer,
            sync.ActivitySynchronizer,
            sync.OpportunitySynchronizer,
            sync.TimeEntrySynchronizer,
            sync.ScheduleEntriesSynchronizer
        ]
        self.grades['operational'].synchronizers = [
            sync.MemberSynchronizer,
            sync.CompanySynchronizer,
            sync.ProjectSynchronizer,
            sync.ProjectPhaseSynchronizer,
            sync.ServiceTicketSynchronizer,
            sync.ProjectTicketSynchronizer,
            sync.ActivitySynchronizer,
            sync.OpportunitySynchronizer,
            sync.ScheduleEntriesSynchronizer,
        ]
        self.grades['configuration'].synchronizers = [
            sync.WorkTypeSynchronizer,
            sync.WorkRoleSynchronizer,
            sync.TerritorySynchronizer,
            sync.SystemLocationSynchronizer,
            sync.SalesProbabilitySynchronizer,
            sync.CompanyTypeSynchronizer,
            sync.CompanyNoteTypesSynchronizer,
            sync.CompanyStatusSynchronizer,
            sync.CompanyTeamRoleSynchronizer,
            sync.LocationSynchronizer,
            sync.ScheduleTypeSynchronizer,
            sync.ScheduleStatusSynchronizer,
            sync.CommunicationTypeSynchronizer,
            sync.BoardSynchronizer,
            sync.DepartmentSynchronizer,
            sync.StandardNoteSynchronizer,
            sync.BoardStatusSynchronizer,
            sync.TeamSynchronizer,
            sync.ItemSynchronizer,
            sync.TypeSynchronizer,
            sync.SubTypeSynchronizer,
            sync.PrioritySynchronizer,
            sync.HolidayListSynchronizer,
            sync.HolidaySynchronizer,
            sync.CalendarSynchronizer,
            sync.MyCompanyOtherSynchronizer,
            sync.AgreementTypeSynchronizer,
            sync.AgreementSynchronizer,
            sync.ContactSynchronizer,
            sync.SourceSynchronizer,
            sync.ProjectTypeSynchronizer,
            sync.ProjectStatusSynchronizer,
            sync.ProjectRoleSynchronizer,
            sync.ProjectUDFSynchronizer,
            sync.OpportunityStageSynchronizer,
            sync.OpportunityStatusSynchronizer,
            sync.OpportunityTypeSynchronizer,
            sync.OpportunityUDFSynchronizer,
            sync.ActivityStatusSynchronizer,
            sync.ActivityTypeSynchronizer,
            sync.ActivityUDFSynchronizer,
            sync.TicketUDFSynchronizer,
            sync.TimeEntrySynchronizer,
        ]
        self.grades['slow'].synchronizers = [
            sync.ServiceNoteSynchronizer,
            sync.OpportunityNoteSynchronizer,
            sync.CompanyTeamSynchronizer,
            sync.CompanySiteSynchronizer,
            sync.ServiceTicketTaskSynchronizer,
            sync.ProjectTicketTaskSynchronizer,
            sync.TypeSubTypeItemAssociationSynchronizer,
            sync.ProjectTeamMemberSynchronizer,
        ]
        self.grades['ludicrous_slow'].synchronizers = [
            sync.ContactCommunicationSynchronizer,
        ]
