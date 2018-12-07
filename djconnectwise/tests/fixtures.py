from django.conf import settings

API_BOARD = {
    'id': 1,
    'name': 'Service A',
    'locationId': 1,
    'businessUnitId': 10,
    'inactiveFlag': False,
    'projectFlag': False
}

API_BOARD_LIST = [API_BOARD]


API_BOARD_STATUS_LIST = [
    {
        'id': 1,
        'name': 'New',
        'board': {
            'id': 1
        },
        'sortOrder': 0,
        'displayOnBoard': True,
        'inactive': False,
        'closedStatus': False
    },
    {
        'id': 2,
        'name': 'In Progress',
        'board': {
            'id': 1
        },
        'sortOrder': 1,
        'displayOnBoard': True,
        'inactive': False,
        'closedStatus': True
    },
]


API_COMPANY_STATUS = {
    "id": 1,
    "name": "Active",
    "defaultFlag": True,
    "inactiveFlag": False,
    "notifyFlag": False,
    "disallowSavingFlag": False,
    "notificationMessage": "Some message",
    "customNoteFlag": False,
    "cancelOpenTracksFlag": False
}


API_COMPANY_STATUS_LIST = [API_COMPANY_STATUS]


API_COMPANY_TYPES_LIST = [
    {
        'id': 5,
        'name': 'Partner',
        'defaultFlag': False,
        'vendorFlag': False,
        '_info': {
            'lastUpdated': '2015-08-21T20:22:06Z',
            'updatedBy': None
        }
    }
]


API_COMPANY = {
    'id': 2,
    'identifier': 'YourCompany',
    'name': 'TestCompany',
    'status': API_COMPANY_STATUS,
    'type': API_COMPANY_TYPES_LIST[0],
    'addressLine1': None,
    'addressLine2': None,
    'city': None,
    'state': None,
    'zip': None,
    'country': None,
    'phoneNumber': '1450994900',
    'faxNumber': '',
    'website': 'www.YourCompany.com',
    'territoryId': 1,
    'marketId': 23,
    'accountNumber': '',
    'defaultContact': {
        'id': 77,
        'name': 'Bob Dobbs',
        '_info': {
            'contact_href': 'https: //some-host.com/v4_6_release/' +
                            'apis/3.0/company/contacts/77'
        }
    },
    'dateAcquired': '2002-08-20T18: 04: 26Z',
    'sicCode': None,
    'parentCompany': None,
    'annualRevenue': 0.0,
    'numberOfEmployees': None,
    'ownershipType': None,
    'timeZone': {
        'id': 1,
        'name': 'US Eastern',
        '_info': None
    },
    'leadSource': None,
    'leadFlag': False,
    'unsubscribeFlag': False,
    'calendarId': None,
    'userDefinedField1': None,
    'userDefinedField2': None,
    'userDefinedField3': None,
    'userDefinedField4': None,
    'userDefinedField5': None,
    'userDefinedField6': None,
    'userDefinedField7': None,
    'userDefinedField8': None,
    'userDefinedField9': None,
    'userDefinedField10': None,
    'vendorIdentifier': None,
    'taxIdentifier': None,
    'taxCode': {
        'id': 11,
        'name': 'State',
        '_info': {
            'taxCode_href': 'https: //some-host.com/v4_6_release/apis/3.0/finance/taxCodes/11'
        }
    },
    'billingTerms': {
        'id': 2,
        'name': 'Net 10 days',
        '_info': None
    },
    'invoiceTemplate': None,
    'pricingSchedule': None,
    'companyEntityType': None,
    'billToCompany': {
        'id': 2,
        'identifier': 'YourCompany',
        'name': 'TestCompany',
        '_info': {
            'company_href': 'https: //some-host.com/v4_6_release/apis/3.0/company/companies/2'
        }
    },
    'billingSite': None,
    'billingContact': None,
    'invoiceDeliveryMethod': {
        'id': 1,
        'name': 'Mail',
        '_info': None
    },
    'invoiceToEmailAddress': None,
    'invoiceCCEmailAddress': None,
    'deletedFlag': False,
    'dateDeleted': None,
    'deletedBy': None,
    'mobileGuid': '4d48fc9e-2e9a-43a6-a85d-f1996723459f',
    'currency': None,
    'territoryManager': None,
    '_info': {
        'lastUpdated': '2015-12-24T22: 08: 22Z',
        'updatedBy': 'omnicorp'
    },
    'customFields': None,
}

API_COMPANY_LIST = [API_COMPANY]

API_MEMBER = {
    'adminFlag': False,
    'allowExpensesEnteredAgainstCompaniesFlag': True,
    'allowInCellEntryOnTimeSheet': False,
    'billableForecast': 75.0,
    'calendar': None,
    'calendarSyncIntegrationFlag': False,
    'country': None,
    'dailyCapacity': 8.0,
    'daysTolerance': 1,
    'defaultDepartmentId': 10,
    'defaultEmail': 'Office',
    'defaultLocationId': 2,
    'defaultPhone': 'Office',
    'disableOnlineFlag': False,
    'enableLdapAuthenticationFlag': False,
    'enableMobileFlag': False,
    'enableMobileGpsFlag': False,
    'enterTimeAgainstCompanyFlag': True,
    'expenseApprover': {
        'id': 176,
        'identifier': 'User1',
        'name': 'Training User1',
        '_info': {
            'member_href': 'https://some-host.com/v4_6_release/apis/3.0/system/members/176'
        }
    },
    'firstName': 'Training',
    'hideMemberInDispatchPortalFlag': False,
    'hireDate': '1800-01-01T08:00:00Z',
    'homeEmail': None,
    'homeExtension': None,
    'homePhone': None,
    'hourlyCost': 0.0,
    'hourlyRate': None,
    'id': 176,
    'identifier': 'User1',
    'inactiveDate': None,
    'inactiveFlag': False,
    'includeInUtilizationReportingFlag': False,
    'lastLogin': '2017-02-07T07:37:47Z',
    'lastName': 'User1',
    'licenseClass': 'F',
    'mapiName': None,
    'middleInitial': None,
    'minimumHours': 8.0,
    'mobileEmail': None,
    'mobileExtension': None,
    'mobilePhone': None,
    'notes': '',
    'officeEmail': 'test@test.com',
    'officeExtension': None,
    'officePhone': '555-121-2121',
    'photo': {
        'id': 267,
        'name': 'pexels-photo-119705-square-resized.jpg',
        '_info': {
            'filename': 'pexels-photo-119705-square-resized.jpg',
            'document_href': 'https://example.com/v4_6_release/apis/3.0/system/documents/267',
            'documentDownload_href': 'https://example.com/v4_6_release/apis/3.0/system/documents/267/download'
        }
    },
    'projectDefaultBoard': None,
    'projectDefaultDepartmentId': None,
    'projectDefaultLocationId': None,
    'reportsTo': None,
    'requireExpenseEntryFlag': False,
    'requireStartAndEndTimeOnTimeEntryFlag': False,
    'requireTimeSheetEntryFlag': False,
    'restrictDefaultSalesTerritoryFlag': False,
    'restrictDefaultWarehouseBinFlag': False,
    'restrictDefaultWarehouseFlag': False,
    'restrictDepartmentFlag': False,
    'restrictLocationFlag': False,
    'restrictProjectDefaultDepartmentFlag': False,
    'restrictProjectDefaultLocationFlag': False,
    'restrictScheduleFlag': False,
    'restrictServiceDefaultDepartmentFlag': False,
    'restrictServiceDefaultLocationFlag': False,
    'salesDefaultLocationId': 39,
    'scheduleCapacity': 8.0,
    'scheduleDefaultDepartmentId': 10,
    'scheduleDefaultLocationId': 2,
    'securityLevel': 'Corporate',
    'securityLocationId': 38,
    'securityRole': {
        'id': 63,
        'name': 'Admin',
        '_info': None
    },
    'serviceDefaultBoard': {
        'id': 1,
        'name': 'Tampa Office/Services',
        '_info': {
            'board_href': 'https://some-host.com/v4_6_release/apis/3.0/service/boards/1'
        }
    },
    'serviceDefaultDepartmentId': 10,
    'serviceDefaultLocationId': 2,
    'serviceLocation': None,
    'serviceTeams': [
        25,
        26,
        28
    ],
    'timeApprover': {
        'id': 176,
        'identifier': 'User1',
        'name': 'Training User1',
        '_info': {
            'member_href': 'https://some-host.com/v4_6_release/apis/3.0/system/members/176'
        }
    },
    'timeReminderEmailFlag': False,
    'timeSheetStartDate': '2009-04-16T07:00:00Z',
    'timeZone': {
        'id': 4,
        'name': 'US Pacific',
        '_info': None
    },
    'title': None,
    'type': None,
    'vendorNumber': None,
    'warehouse': None,
    'warehouseBin': None,
    'workRole': {
        'id': 11,
        'name': 'System Engineer',
        '_info': None
    },
    'workType': None,
    '_info': {
        'lastUpdated': '2015-08-24T19:50:10Z',
        'updatedBy': 'User1',
    }
}

API_MEMBER_LIST = [API_MEMBER]


API_MEMBER_COUNT = {
    'count': len(API_MEMBER_LIST)
}


API_SERVICE_NOTE_LIST = [
    {
        'id': 3,
        'ticketId': 69,
        'text': 'Some Text On This Note',
        'detailDescriptionFlag': True,
        'internalAnalysisFlag': False,
        'resolutionFlag': False,
        'member': API_MEMBER,
        'dateCreated': '2010-09-18T17:10:37Z',
        'createdBy': 'helpdesk2',
        'internalFlag': True,
        'externalFlag': False,
        '_info': {
            'lastUpdated': '2010-09-18T17:10:37Z',
            'updatedBy': 'helpdesk2'
        }
    }
]


API_SALES_OPPORTUNITY_NOTE_LIST = [
    {
         'id': 43,
         'opportunityId': 2,
         'text': "Some text on this note",
         '_info': {
             'lastUpdated': '2015-12-24T22:08:22Z'
         }
    }
]


API_PROJECT_STATUSES = [
    {
        'id': 1,
        'name': 'Open',
        'defaultFlag': True,
        'inactiveFlag': False,
        'noTimeFlag': False,
        'closedFlag': False,
        '_info': {
            'lastUpdated': '2001-01-08T18:05:13Z',
            'updatedBy': None
        }
    },
    {
        'id': 2,
        'name': 'Closed',
        'defaultFlag': False,
        'inactiveFlag': False,
        'noTimeFlag': True,
        'closedFlag': True,
        '_info': {
            'lastUpdated': '2001-01-08T18:05:21Z',
            'updatedBy': None
        }
    },
    {
        'id': 3,
        'name': 'On-Hold',
        'defaultFlag': False,
        'inactiveFlag': False,
        'noTimeFlag': True,
        'closedFlag': False,
        '_info': {
            'lastUpdated': '2001-01-08T18:05:40Z',
            'updatedBy': None
        }
    },
    {
        'id': 6,
        'name': '>Closed',
        'defaultFlag': False,
        'inactiveFlag': False,
        'noTimeFlag': True,
        'closedFlag': True,
        '_info': {
            'lastUpdated': '2017-08-30T19:25:43Z',
            'updatedBy': 'User1'
        }
    }
]


API_PROJECT = {
    'id': 5,
    '_info': {
        'lastUpdated': '2005-05-27T17:30:19Z',
        'updatedBy': 'User10'
    },
    'actualEnd': '2005-08-24T00:00:00Z',
    'actualHours': 8.03,
    'actualStart': '2005-08-24T00:00:00Z',
    'billExpenses': 'Billable',
    'billingAmount': 0,
    'billingAttention': '',
    'billingMethod': 'ActualRates',
    'billingRateType': 'WorkRole',
    'billProducts': 'Billable',
    'billProjectAfterClosedFlag': False,
    'billTime': 'Billable',
    'billUnapprovedTimeAndExpense': False,
    'board': API_BOARD,
    'budgetAnalysis': 'ActualHours',
    'budgetFlag': False,
    'budgetHours': 91.5,
    'businessUnitId': 10,
    'company': API_COMPANY,
    'contact': {
        'id': 70,
        'name': 'Gregg Kegle',
        '_info': {
            'contact_href': 'https://some-host.com/v4_6_release/apis/3.0/company/contacts/70'
        }
    },
    'customerPO': '',
    'description': '\n',
    'currency': {
        'id': 7,
        'symbol': '$',
        'isoCode': 'USD',
        'name': 'US Dollars',
        '_info': {
            'currency_href': 'https://some-host.com/v4_6_release/apis/3.0/finance/currencies/7'
        }
    },
    'downpayment': 0,
    'estimatedEnd': '2005-12-30T00:00:00Z',
    'estimatedExpenseRevenue': 0,
    'estimatedHours': 0,
    'estimatedProductRevenue': 0,
    'estimatedStart': '2005-05-02T00:00:00Z',
    'estimatedTimeRevenue': 0,
    'expenseApprover': API_MEMBER,
    'includeDependenciesFlag': False,
    'includeEstimatesFlag': False,
    'locationId': 2,
    'manager': API_MEMBER,
    'name': 'Financial System Implementation',
    'restrictDownPaymentFlag': False,
    'scheduledHours': 13.95,
    'shipToCompany': API_COMPANY,
    'shipToSite': {
        'id': 28,
        'name': 'Main',
        '_info': {
            'site_href': 'https://some-host.com/v4_6_release/apis/3.0/company/companies/24/sites/28'
        }
    },
    'site': {
        'id': 28,
        'name': 'Main',
        '_info': {
            'site_href': 'https://some-host.com/v4_6_release/apis/3.0/company/companies/24/sites/28'
        }
    },
    'status': API_PROJECT_STATUSES[0],
    'timeApprover': API_MEMBER,
    'type': {
        'id': 8,
        'name': 'Implementations'
    },
    'doNotDisplayInPortalFlag': False,
    'estimatedTimeCost': 0,
    'estimatedExpenseCost': 0,
    'estimatedProductCost': 0
}

API_PROJECT_LIST = [API_PROJECT]

API_SERVICE_LOCATION = {
    'id': 1,
    'name': 'On-Site',
    'where': None,
    'defaultFlag': True,
    '_info': {'lastUpdated': '2001-06-05T16:53:55Z', 'updatedBy': 'SumGuy'}
}

API_SERVICE_LOCATION_LIST = [API_SERVICE_LOCATION]


API_SERVICE_PRIORITY = {
    'id': 4,
    'name': 'Priority 3 - Normal Response',
    'sortOrder': 6,
    'color': 'blue',
    '_info': {
        'priority_href': 'https://some-host.com/v4_6_release/apis/3.0/service/priorities/4',
        'image_href': 'https://some-host.com/v4_6_release/'
            'apis/3.0/service/priorities/4/image?lm=2005-05-27T14:58:21Z'
    }
}
# Under unknown circumstances, a CW instance might just give id and name
# fields.
API_SERVICE_PRIORITY_LIMITED = {
    'id': 5,
    'name': 'Priority 2 - Quick Response',
}


API_SERVICE_PRIORITY_LIST = [API_SERVICE_PRIORITY_LIMITED, API_SERVICE_PRIORITY]


API_SERVICE_TEAM_LIST = [
    {
        '_info': {'lastUpdated': '2017-02-14T18:21:15Z', 'updatedBy': 'User1'},
        'boardId': 1,
        'businessUnitId': 10,
        'defaultFlag': True,
        'id': 25,
        'locationId': 2,
        'members': [179, 176, 181, 183, 185],
        'name': 'Windows Team',
        'notifyOnTicketDelete': False,
        'teamLeader': {'_info': {'member_href': 'https://some-host.com/v4_6_release/apis/3.0/system/members/186'},
                       'id': 186,
                       'identifier': 'User10',
                       'name': 'Training User10'}},
    {
        '_info': {'lastUpdated': '2017-02-14T18:20:31Z', 'updatedBy': 'User1'},
        'boardId': 1,
        'businessUnitId': 10,
        'defaultFlag': False,
        'id': 26,
        'locationId': 2,
        'members': [202, 191, 189, 193, 195],
        'name': 'Network Team',
        'notifyOnTicketDelete': False,
        'teamLeader': {'_info': {'member_href': 'https://some-host.com/v4_6_release/apis/3.0/system/members/186'},
                       'id': 186,
                       'identifier': 'User10',
                       'name': 'Training User10'}},
    {
        '_info': {'lastUpdated': '2017-02-14T18:20:13Z', 'updatedBy': 'User1'},
        'boardId': 1,
        'businessUnitId': 10,
        'defaultFlag': False,
        'id': 27,
        'locationId': 2,
        'members': [180, 178, 187, 186, 182, 184],
        'name': 'Linux Team',
        'notifyOnTicketDelete': False,
        'teamLeader': {'_info': {'member_href': 'https://some-host.com/v4_6_release/apis/3.0/system/members/189'},
                       'id': 189,
                       'identifier': 'User13',
                       'name': 'Training User13'}
    }
]


API_SCHEDULE_HOLIDAY_LIST = {
    'id': 1,
    'name': 'Standard Holiday List'
}


API_SCHEDULE_HOLIDAY_LIST_LIST = [API_SCHEDULE_HOLIDAY_LIST]


API_SCHEDULE_HOLIDAY = {
    'id': 1,
    'name': 'Veritably Enjoyable Holiday',
    'allDayFlag': False,
    'date': '2018-11-23',
    'timeStart': '08:00:00',
    'timeEnd': '17:00:00',
    'holidayList': API_SCHEDULE_HOLIDAY_LIST
}


API_SCHEDULE_HOLIDAY_MODEL_LIST = [API_SCHEDULE_HOLIDAY]


API_SCHEDULE_CALENDAR = {
    'id': 1,
    'name': 'Standard Calendar',
    'mondayStartTime': '08:00:00',
    'mondayEndTime': '17:00:00',
    'tuesdayStartTime': '08:00:00',
    'tuesdayEndTime': '17:00:00',
    'wednesdayStartTime': '08:00:00',
    'wednesdayEndTime': '17:00:00',
    'thursdayStartTime': '08:00:00',
    'thursdayEndTime': '17:00:00',
    'fridayStartTime': '08:00:00',
    'fridayEndTime': '17:00:00',
    'saturdayStartTime': None,
    'saturdayEndTime': None,
    'sundayStartTime': None,
    'sundayEndTime': None,
    'holidayList': API_SCHEDULE_HOLIDAY_LIST
}


API_SCHEDULE_CALENDAR_LIST = [API_SCHEDULE_CALENDAR]


API_SYSTEM_OTHER = {
    'id': 1,
    'defaultCalendar': API_SCHEDULE_CALENDAR
}


API_SYSTEM_OTHER_LIST = [API_SYSTEM_OTHER]


API_SERVICE_SLA = {
    'id': 3,
    'name': 'Standard SLA',
    'defaultFlag': True,
    'respondHours': 5,
    'planWithin': 10,
    'resolutionHours': 24,
    'basedOn': 'Custom',
    'customCalendar': API_SCHEDULE_CALENDAR
}


API_SERVICE_SLA_LIST = [API_SERVICE_SLA]


API_SERVICE_SLA_PRIORITY = {
    'id': 5,
    'sla': API_SERVICE_SLA,
    'priority': API_SERVICE_PRIORITY,
    'respondHours': 5,
    'planWithin': 10,
    'resolutionHours': 24
}


API_SERVICE_SLA_PRIORITY_LIST = [API_SERVICE_SLA_PRIORITY]


API_TYPE = {
    'id': 8,
    'name': 'Admin',
    'category': 'Reactive',
    'defaultFlag': False,
    'inactiveFlag': False,
    'requestForChangeFlag': False,
    'board': API_BOARD,
    'location': {
        'id': 2,
        'name': 'Tampa Office',
        '_info': {
            'location_href': 'https://connectwise.kerkhofftech.ca/v4_6_release/apis/3.0/system/locations/2'
        }
    },
    'department': {
        'id': 13,
        'identifier': 'Admin',
        'name': 'Admin',
        '_info': {
            'department_href': 'https://connectwise.kerkhofftech.ca/v4_6_release/apis/3.0/system/departments/13'
        }
    },
    '_info': {
        'lastUpdated': '2017-02-14T21:59:30Z',
        'updatedBy': 'User1'
    }
}

API_TYPE_LIST = [API_TYPE]


API_SUBTYPE = {
    'id': 1,
    'name': 'Repair',
    'inactiveFlag': False,
    'typeAssociationIds': [
        30,
        31
    ],
    'board': API_BOARD,
    '_info': {
        'lastUpdated': '2018-09-14T17:24:15Z',
        'updatedBy': 'User1'
    }
}

API_SUBTYPE_LIST = [API_SUBTYPE]


API_ITEM = {
    'id': 2,
    'name': 'Fix it',
    'inactiveFlag': False,
    'board': API_BOARD,
    '_info': {
        'lastUpdated': '2018-09-14T17:29:23Z',
        'updatedBy': 'User1'
    }
}

API_ITEM_LIST = [API_ITEM]


API_SERVICE_TICKET = {
    'id': 69,
    'summary': 'Schedule and Execute Conversion',
    'recordType': 'ProjectTicket',
    'board': {
        'id': 1,
        'name': 'Service A',
        '_info': {
            'board_href': 'https://some-host.com/v4_6_release/apis/3.0/service/boards/1'
        }
    },
    'status': {
        'id': 1,
        'name': 'New',
        '_info': {
            'status_href': 'https://some-host.com/v4_6_release/apis/3.0/service/boards/1/statuses/1'
        }
    },
    'project': API_PROJECT,
    'phase': {
        'id': 8,
        'name': 'Solution Implementation',
        '_info': {
            'phase_href': 'https://some-host.com/v4_6_release/apis/3.0/project/projects/5/phases/8'
        }
    },
    'wbsCode': '10.2',
    'company': API_COMPANY,
    'site': {
        'id': 28,
        'name': 'Main',
        '_info': {
            'site_href': 'https://some-host.com/v4_6_release/apis/3.0/company/companies/24/sites/28'
        }
    },
    'siteName': None,
    'addressLine1': '140 S. Village Ave.',
    'addressLine2': '8th Floor',
    'city': 'Tampa',
    'stateIdentifier': 'FL',
    'zip': '33880',
    'country': None,
    'contact': {
        'id': 70,
        'name': 'Gregg Kegle',
        '_info': {
            'contact_href': 'https://some-host.com/v4_6_release/apis/3.0/company/contacts/70'
        }
    },
    'contactName': 'Gregg Kegle',
    'contactPhoneNumber': '8135156666',
    'contactPhoneExtension': None,
    'contactEmailAddress': 'gregg.kegle@wildeagle.com',
    'type': API_TYPE_LIST[0],
    'subType': API_SUBTYPE_LIST[0],
    'item': API_ITEM_LIST[0],
    'team': API_SERVICE_TEAM_LIST[0],
    'owner': API_MEMBER,
    'priority': API_SERVICE_PRIORITY,
    'locationId': 999,  # This is unknown, but it's *not* the service location.
    'serviceLocation': {
        'id': API_SERVICE_LOCATION['id'],
        'name': API_SERVICE_LOCATION['name']
    },
    'source': {
        'id': 2,
        'name': 'Phone',
        '_info': {
            'source_href': 'https://some-host.com/v4_6_release/apis/3.0/service/sources/2'
        }
    },
    'requiredDate': "2017-03-03T00:00:00Z",
    'budgetHours': None,
    'opportunity': None,
    'agreement': None,
    'severity': 'Medium',
    'impact': 'Medium',
    'externalXRef': None,
    'poNumber': None,
    'knowledgeBaseCategoryId': None,
    'knowledgeBaseSubCategoryId': None,
    'allowAllClientsPortalView': False,
    'customerUpdatedFlag': False,
    'automaticEmailContactFlag': False,
    'automaticEmailResourceFlag': False,
    'automaticEmailCcFlag': False,
    'automaticEmailCc': None,
    'contactEmailLookup': None,
    'processNotifications': None,
    'closedDate': None,
    'closedBy': None,
    'closedFlag': False,
    'dateEntered': '2005-05-27T17:30:19Z',
    'enteredBy': 'User10',
    'actualHours': None,
    'approved': True,
    'subBillingMethod': None,
    'subBillingAmount': None,
    'subDateAccepted': None,
    'dateResolved': None,
    'dateResplan': None,
    'dateResponded': None,
    'resolveMinutes': 0,
    'resPlanMinutes': 0,
    'respondMinutes': 0,
    'isInSla': False,
    'knowledgeBaseLinkId': None,
    'resources': 'User1',
    'parentTicketId': None,
    'hasChildTicket': False,
    'knowledgeBaseLinkType': None,
    'billTime': 'NoDefault',
    'billExpenses': 'Billable',
    'billProducts': 'Billable',
    'predecessorType': None,
    'predecessorId': None,
    'predecessorClosedFlag': None,
    'lagDays': None,
    'lagNonworkingDaysFlag': None,
    'estimatedStartDate': None,
    'duration': None,
    'businessUnitId': 10,
    'mobileGuid': 'c5882071-79ac-4149-9088-3af3196a22f7',
    'sla': API_SERVICE_SLA,
    '_info': {
        'lastUpdated': '2016-03-08T21:59:20Z',
        'updatedBy': 'User1',
        'activities_href': 'https://some-host.com/v4_6_release/apis/3.0/service/tickets/69/activities',
        'timeentries_href': 'https://some-host.com/v4_6_release/apis/3.0/service/tickets/69/timeentries',
        'scheduleentries_href': 'https://some-host.com/v4_6_release/apis/3.0/service/tickets/69/scheduleentries',
        'documents_href': 'https://some-host.com/v4_6_release/apis/3.0/service/tickets/69/documents',
        'products_href': 'https://some-host.com/v4_6_release/apis/3.0/service/tickets/69/products',
        'configurations_href': 'https://some-host.com/v4_6_release/apis/3.0/service/tickets/69/configurations',
        'tasks_href': 'https://some-host.com/v4_6_release/apis/3.0/service/tickets/69/tasks',
        'notes_href': 'https://some-host.com/v4_6_release/apis/3.0/service/tickets/69/notes'
    },
    'customFields': None
}


API_SERVICE_TICKET_LIST = [API_SERVICE_TICKET]


API_SERVICE_TICKET_MAP = {
    t['id']: t
    for t in API_SERVICE_TICKET_LIST
}


API_CW_VERSION = {
    'version': 'v2.0'
}


API_SYSTEM_CALLBACK_ENTRY = {
    'id': 0,
    'description': 'maxLength = 100',
    'url': 'http://localhost',
    'objectId': 0,
    'type': 'Sample string',
    'level': 'Sample string',
    'memberId': API_MEMBER['id'],
    'inactiveFlag': False,
    '_info ': {'lastUpdated': '', 'updatedBy': ''}
}


API_SYSTEM_TERRITORY = {
    'id': 1,
    'name': 'Some Territory'
}


API_SYSTEM_TERRITORY_LIST = [API_SYSTEM_TERRITORY]


API_SALES_OPPORTUNITY_TYPE = {
    'id': 2,
    'description': 'Application Development',
    'inactiveFlag': False,
    '_info': {'lastUpdated': '2002-03-15T19:16:52Z', 'updatedBy': 'Arnie'}
}


API_SALES_OPPORTUNITY_TYPES = [
    API_SALES_OPPORTUNITY_TYPE
]


API_SALES_PROBABILITY = {
    'id': 5,
    'probability': 50,
    '_info': {
        'lastUpdated': '2010-06-19T15:50:07Z',
        'updatedBy': 'abellini'
    }
}

API_SALES_PROBABILITY_LIST = [API_SALES_PROBABILITY]


API_SALES_OPPORTUNITY_STATUSES = [
  {'_info':
         {'lastUpdated': '2000-12-28T19:35:17Z', 'updatedBy': None},
   'closedFlag': False,
   'dateEntered': '2000-12-28T19:35:17Z',
   'defaultFlag': True,
   'enteredBy': 'CONVERSION',
   'id': 1,
   'inactiveFlag': False,
   'lostFlag': False,
   'name': 'Open',
   'wonFlag': False},
  {'_info': {'lastUpdated': '2000-12-28T19:35:32Z', 'updatedBy': None},
   'closedFlag': True,
   'dateEntered': '2000-12-28T19:35:32Z',
   'defaultFlag': False,
   'enteredBy': 'CONVERSION',
   'id': 2,
   'inactiveFlag': False,
   'lostFlag': False,
   'name': 'Won',
   'wonFlag': True},
  {'_info': {'lastUpdated': '2000-12-28T19:35:50Z', 'updatedBy': None},
   'closedFlag': True,
   'dateEntered': '2000-12-28T19:35:50Z',
   'defaultFlag': False,
   'enteredBy': 'CONVERSION',
   'id': 3,
   'inactiveFlag': False,
   'lostFlag': True,
   'name': 'Lost',
   'wonFlag': False},
  {'_info': {'lastUpdated': '2003-10-06T14:48:18Z', 'updatedBy': 'zAdmin'},
   'closedFlag': True,
   'dateEntered': '2003-10-06T14:48:18Z',
   'defaultFlag': False,
   'enteredBy': 'zAdmin',
   'id': 4,
   'inactiveFlag': False,
   'lostFlag': False,
   'name': 'No decision',
   'wonFlag': False}
]


API_SALES_OPPORTUNITY_STAGE = {
    '_info': None,
    'id': 8,
    'name': '3.Quote'
    }


API_SALES_OPPORTUNITY_STAGES = [API_SALES_OPPORTUNITY_STAGE]


API_SALES_OPPORTUNITY = {
    '_info': {'lastUpdated': '2016-10-12T19:24:07Z',
              'notes_href': 'https://some-host.com/v4_6_release/apis/3.0/sales/opportunities/2/notes',
              'updatedBy': 'TaxUpdate'},
    'billToCompany':
        {'_info': {'company_href': 'https://some-host.com/v4_6_release/apis/3.0/company/companies/8'},
         'id': 8,
         'identifier': 'AngryFoxCo',
         'name': 'Angry Fox, Co.'},
    'billToContact': {'_info': {'contact_href': 'https://some-host.com/v4_6_release/apis/3.0/company/contacts/20'},
                      'id': 20,
                      'name': 'Flin Storts'},
    'billToSite': {'_info': {'site_href': 'https://some-host.com/v4_6_release/apis/3.0/company/companies/8/sites/7'},
                   'id': 7,
                   'name': 'Main'},
    'billingTerms': {'_info': None, 'id': 2, 'name': 'Net 10 days'},
    'businessUnitId': 10,
    'campaign': {'_info': {'campaign_href': 'https://some-host.com/v4_6_release/apis/3.0/marketing/campaigns/3'},
                 'id': 3,
                 'name': 'Partner Referral'},
    'closedBy': API_MEMBER,
    'closedDate': '2005-09-09T19:53:52Z',
    'company': API_COMPANY,
    'contact': {'_info': {'contact_href': 'https://some-host.com/v4_6_release/apis/3.0/company/contacts/20'},
                'id': 20,
                'name': 'Flin Storts'},
    'customFields': None,
    'customerPO': None,
    'dateBecameLead': '2005-09-09T19:53:52Z',
    'expectedCloseDate': '2006-01-06T00:00:00Z',
    'id': 2,
    'locationId': 2,
    'name': 'Develop Executive Reporting System',
    'notes': '',
    'pipelineChangeDate': '2005-12-23T19:16:21Z',
    'primarySalesRep': API_MEMBER,
    'priority': {'_info': None, 'id': 7, 'name': 'Clear Flag'},
    'probability': API_SALES_PROBABILITY,
    'rating': {'_info': {'rating_href': 'https://some-host.com/v4_6_release/apis/3.0/sales/opportunities/ratings/4'},
               'id': 4,
               'name': 'Hot'},
    'secondarySalesRep': API_MEMBER,
    'shipToCompany': API_COMPANY,
    'shipToContact': {'_info': {'contact_href': 'https://some-host.com/v4_6_release/apis/3.0/company/contacts/20'},
                      'id': 20,
                      'name': 'Flin Storts'},
    'shipToSite': {'_info': {'site_href': 'https://some-host.com/v4_6_release/apis/3.0/company/companies/8/sites/7'},
                   'id': 7,
                   'name': 'Main'},
    'site': {'_info': {'site_href': 'https://some-host.com/v4_6_release/apis/3.0/company/companies/8/sites/7'},
             'id': 7,
             'name': 'Main'},
    'source': 'Microsoft sent to us',
    'stage': {'_info': None, 'id': 8, 'name': '3.Quote'},
    'status': {'_info': {'status_href': 'https://some-host.com/v4_6_release/apis/3.0/sales/opportunities/statuses/1'},
               'id': 1,
               'name': 'Open'},
    'taxCode': {'_info': {'taxCode_href': 'https://some-host.com/v4_6_release/apis/3.0/finance/taxCodes/11'},
                'id': 11,
                'name': 'State'},
    'totalSalesTax': 0.0,
    'type': API_SALES_OPPORTUNITY_TYPE,
}

API_SALES_OPPORTUNITIES = [
    API_SALES_OPPORTUNITY,
]


API_SALES_ACTIVITY = {
    'id': 47,
    'name': 'Stage Change from 1.Prospect to 2.Qualification',
    'type': {
        'id': 3,
        'name': 'Historical Entry',
        '_info': {
            'type_href': 'https://example.com/v4_6_release/apis/3.0/sales/activities/types/3'
        }
    },
    'company': API_COMPANY,
    'contact': {
        'id': 20,
        'name': 'Flin Storts',
        '_info': {
            'contact_href': 'https://example.com/v4_6_release/apis/3.0/company/contacts/20'
        }
    },
    'phoneNumber': '8139888241',
    'email': 'test@test.com',
    'status': {
        'id': 4,
        'name': '1-High',
        '_info': {
            'status_href': 'https://example.com/v4_6_release/apis/3.0/sales/activities/statuses/4'
        }
    },
    'opportunity': API_SALES_OPPORTUNITY,
    'ticket': None,
    'agreement': None,
    'campaign': None,
    'notes': 'Stage Change from 1.Prospect to 2.Qualification',
    'dateStart': '2016-03-06',
    # 'dateEnd': None,                  # ConnectWise 2017.5 removed null values
    'assignedBy': {
        'id': 196,
        'identifier': 'User20',
        'name': 'Training User20',
        '_info': {
            'member_href': 'https://example.com/v4_6_release/apis/3.0/system/members/196'
        }
    },
    'assignTo': API_MEMBER,
    'scheduleStatus': {
        'id': 1,
        'name': 'Tentative',
        '_info': {
            'status_href': 'https://example.com/v4_6_release/apis/3.0/schedule/statuses/1'
        }
    },
    'reminder': {
        'id': 1,
        'name': '0 minutes',
        '_info': None
    },
    'where': None,'2015-11-30T19:53:52Z'
    'notifyFlag': False,
    'mobileGuid': '3a5828b8-a72c-4130-898b-b5aafbf98e46',
    '_info': {
        'lastUpdated': '2017-08-04T20:05:52Z',
        'updatedBy': 'User1'
    },
    'customFields': None
}

API_SALES_ACTIVITIES = [
    API_SALES_ACTIVITY,
]

API_COMPANY_INFO = {
    'CompanyName': 'foobar',
    'Codebase': 'v2017_3/',
    'VersionCode': 'v2017.3',
    'VersionNumber': 'v4.6.47174',
    'CompanyID': 'CW',
    'IsCloud': True
}

API_SCHEDULE_SALES_TYPE = {
    'id': 1,
    'name': 'Sales',
    'identifier': 'C',
    'chargeCode': None,
    'where': API_SERVICE_LOCATION,
    'systemFlag': False,
    '_info': {
        'lastUpdated': '2002-01-23T19:47:30Z',
        'updatedBy': 'JBelanger'
    }
}

API_SCHEDULE_SERVICE_TYPE = {
    'id': 4,
    'name': 'Service',
    'identifier': 'S',
    'chargeCode': None,
    'where': API_SERVICE_LOCATION,
    'systemFlag': False,
    '_info': {
        'lastUpdated': '2002-01-23T19:47:30Z',
        'updatedBy': 'JBelanger'
    }
}

API_SCHEDULE_TYPE_LIST = [
    API_SCHEDULE_SALES_TYPE,
    API_SCHEDULE_SERVICE_TYPE
]

API_SCHEDULE_STATUS = {
    'id': 2,
    'name': 'Firm',
    'defaultFlag': True,
    'showAsTentativeFlag': False,
    '_info': {
        'lastUpdated': '2001-04-30T18:48:51Z',
        'updatedBy': None
    }
}

API_SCHEDULE_STATUS_LIST = [API_SCHEDULE_STATUS]

API_SCHEDULE_ENTRY_FOR_TICKET = {
    'id': 11,
    'objectId': 69,
    'name': 'Set up new Workstation for Gregg',
    'member': API_MEMBER,
    'where': API_SERVICE_LOCATION,
    'dateStart': '2005-05-02T12:00:00Z',
    'dateEnd': '2005-05-02T16:00:00Z',
    'reminder': {
        'id': 4,
        'name': '15 minutes',
        '_info': None
    },
    'status': API_SCHEDULE_STATUS,
    'type': API_SCHEDULE_SERVICE_TYPE,
    'span': None,
    'doneFlag': False,
    'acknowledgedFlag': False,
    'ownerFlag': False,
    'allowScheduleConflictsFlag': None,
    'addMemberToProjectFlag': None,
    'projectRoleId': None,
    'mobileGuid': '4cafb36f-418f-4f91-a6f1-e7fbdba87fd5',
    'closeDate': '2015-11-19T18:57:55Z',
    'hours': 4,
    '_info': {
        'lastUpdated': '2015-11-19T18:57:55Z',
        'updatedBy': 'kanban'
    }
}

API_SCHEDULE_ENTRY_FOR_ACTIVITY = {
    'id': 112,
    'objectId': 47,
    'name': 'Key Pool, Co. / Testing rates',
    'member': {
        'id': 176,
        'identifier': 'User1',
        'name': 'Peter Thompson (User1)',
        '_info': {
            'member_href': 'https://example.com/v4_6_release/apis/3.0/system/members/176'
        }
    },
    'where': API_SERVICE_LOCATION,
    'dateStart': '2006-10-17T15:00:00Z',
    'dateEnd': '2006-10-17T16:00:00Z',
    'reminder': {
        'id': 3,
        'name': '10 minutes'
    },
    'status': API_SCHEDULE_STATUS,
    'type': API_SCHEDULE_SALES_TYPE,
    'doneFlag': True,
    'acknowledgedFlag': True,
    'ownerFlag': False,
    'mobileGuid': 'b5009399-041d-4ce8-84ed-75e6e673cf13',
    'hours': 1,
    '_info': {
        'lastUpdated': None,
        'updatedBy': 'User1',
        'objectMobileGuid': '8122b270-56b3-4c90-a671-90fd306aaa33'
    }
}

API_SCHEDULE_ENTRIES = [API_SCHEDULE_ENTRY_FOR_TICKET,
                        API_SCHEDULE_ENTRY_FOR_ACTIVITY]

API_TIME_ENTRY = {
    'id': 2,
    'company': API_COMPANY,
    'chargeToId': 69,
    'chargeToType': 'ServiceTicket',
    'member': API_MEMBER,
    'locationId': 2,
    'businessUnitId': 10,
    'workType': {
        'id': 3,
        'name': 'Regular',
        '_info': {
            'workType_href': 'https://connectwise.kerkhofftech.ca/v4_6_release/apis/3.0/system/workTypes/3'
        }
    },
    'workRole': {
        'id': 11,
        'name': 'System Engineer',
        '_info': {
            'workRole_href': 'https://connectwise.kerkhofftech.ca/v4_6_release/apis/3.0/time/workRoles/11'
        }
    },
    'agreement': {
        'id': 3,
        'name': 'Retainer Agreement for Big Design',
        '_info': {
            'agreement_href': 'https://connectwise.kerkhofftech.ca/v4_6_release/apis/3.0/finance/agreements/3'
        }
    },

    'timeStart': '2005-05-16T08:00:00Z',
    'timeEnd': '2005-05-16T10:00:00Z',
    'actualHours': 2,
    'billableOption': 'Billable',
    'notes': 'server was infected with the Code Red worm.  It has been patched and rebooted.',
    'addToDetailDescriptionFlag': False,
    'addToInternalAnalysisFlag': False,
    'addToResolutionFlag': False,
    'emailResourceFlag': False,
    'emailContactFlag': False,
    'emailCcFlag': False,
    'hoursBilled': 2,
    'enteredBy': 'user10',
    'dateEntered': '2005-05-16T08:00:00Z',
    'invoice': {
        'id': 4,
        'identifier': '3',
        '_info': {
            'invoice_href': 'https://connectwise.kerkhofftech.ca/v4_6_release/apis/3.0/finance/invoices/4'
        }
    },
    'mobileGuid': '6fd34162-0856-4bc1-80ae-c3dccd89357a',
    'hourlyRate': 100,
    'timeSheet': {
        'id': 2,
        'name': '2005-05-14 to 2005-05-20',
        '_info': {
            'timeSheet_href': 'https://connectwise.kerkhofftech.ca/v4_6_release/apis/3.0/time/sheets/2'
        }
    },
    'status': 'Billed',
    '_info': {
        'lastUpdated': '2017-10-17T18:33:20Z',
        'updatedBy': 'CONVERSION',
        'chargeToMobileGuid': '3b9552a5-e8ef-4a68-8124-bbd2c7baf112'
        }
}

API_TIME_ENTRY_LIST = [API_TIME_ENTRY]
