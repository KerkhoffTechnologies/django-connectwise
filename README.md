# django-connectwise

Django app for working with ConnectWise. Defines models (tickets,
members, companies, etc.) and callbacks.

## Requirements

-  Python 3.5
-  Django 2.0

Other versions may work; we haven't tried.

## Installation

From PyPI:

    pip install django-connectwise

From source:

    git clone git@github.com:KerkhoffTechnologies/django-connectwise.git
    cd django-connectwise
    python setup.py install

## Usage

1. Add to INSTALLED_APPS

    ```
    INSTALLED_APPS = [
        ...
        'djconnectwise',
        ...
    ]
    ```

1. Add to `urls.py`:

    ```
    re_path(
        r'^callback/',  # This can be whatever you want.
        include('djconnectwise.urls', namespace='connectwise')
    ),
    ```

1. Add to settings:

    ```
    CONNECTWISE_SERVER_URL = 'https://connectwise.example.com'
    CONNECTWISE_CREDENTIALS = {
        'company_id': 'your company ID',
        'api_public_key': 'your API user public key',
        'api_private_key': 'your API user private key',
    }
    CONNECTWISE_TICKET_PATH = 'v4_6_release/services/system_io/router/openrecord.rails'
    def djconnectwise_configuration():
        return {
            'timeout': 30.0,  # Network timeout in seconds
            'batch_size': 50,  # Number of records to fetch in each request
            'max_attempts': 3,  # Number of times to make a request before failing
            'callback_url': '{}?id='.format(
                reverse('connectwise:callback')
            ),
            'callback_host': '{}://{}'.format(
                'http' if DEBUG else 'https',
                'djconnectwise-host.example.com'
            ),
        }
    DJCONNECTWISE_CONF_CALLABLE = djconnectwise_configuration
    ```

    For ConnectWise Cloud users, `CONNECTWISE_SERVER_URL` can be just i.e. `https://na.myconnectwise.net`- the library changes to the `api-region` domain automatically.
      
    The `DJCONNECTWISE_CONF_CALLABLE` function should return a dictionary with the fields shown above. It's a callable so that it can fetch settings at runtime- for example from [Constance](https://github.com/jazzband/django-constance) settings.
1. Sync objects with this management command: `cwsync`. This will take a very long time if there are many objects to fetch.
1. Register your callbacks with the management command: `callbacks_registered`
1. Use standard Django model signals to see when objects change.
1. To control how user avatar thumbnails are stored, add settings from 
   [easy-thumbnails](https://easy-thumbnails.readthedocs.io/en/stable/ref/settings/).

To de-register your callbacks, use the `callbacks_deleted` management command.

## Testing

Prepare your environment:

```
pip install --upgrade -r requirements_test.txt
```

Try one of:

    ./runtests.py
    python setup.py test
    make test

## Contributing

- Fork this repo
- Make a branch
- Make your improvements

    Making migrations? Run:

    ```
    ./makemigrations.py
    ```

- Run the tests (see above)
- Make a pull request

## License

MIT

## Copyright

© 2017 Kerkhoff Technologies Inc.
