from mock import patch


def company_api_get_call(return_value):
    get_method = 'djconnectwise.api.CompanyAPIRestClient.get'
    get_patch = patch(get_method)
    mock_get_call = get_patch.start()
    mock_get_call.return_value = return_value
    return mock_get_call, get_patch
