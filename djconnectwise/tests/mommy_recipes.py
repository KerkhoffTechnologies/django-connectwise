from itertools import cycle

from model_mommy.recipe import Recipe, seq
from djconnectwise.models import ConnectWiseBoard, BoardStatus, \
    TicketPriority, Ticket, Company, Member, Project

import names

connectwise_board = Recipe(ConnectWiseBoard,
    name=seq('Board #'),
)

member = Recipe(Member,
    identifier=seq('user'),
    first_name=lambda: names.get_first_name(),
    last_name=lambda: names.get_last_name(),
)

project = Recipe(Project,
    name=seq('Project #'),
)

company = Recipe(Company,
    name=seq('Company #'),
    identifier=seq('company'),
)

ticket_priority = Recipe(TicketPriority,
    name=seq('Priority #'),
)

ticket_statuses_names = [
    'New',
    'In Progress',
    'Scheduled',
    'Blocked',
    'Completed',
    'Waiting For Client',
    'Closed',
]
ticket_status = Recipe(BoardStatus,
    name=cycle(ticket_statuses_names),
    sort_order=seq(''),
)

ticket = Recipe(
    Ticket,
    summary=seq('Summary #'),
)
