import os
import re
import time
import json
import base64
import html
import html.parser as HTMLParser
# try:
#     import html.parser as HTMLParser
# except ImportError:
#     import HTMLParser
import requests
import hashlib
import shutil

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-b", "--buildtype", type=str, help="Use latest daily build (d/daily, p/production)")
parser.add_argument("-v", "--majorversion", type=str, help="Major version (18.0, 19.0, etc)")

_args, other_args = parser.parse_known_args()

only_production = True
if _args.buildtype:
    if _args.buildtype in ['d', 'daily']:
        print("get daily build")
        only_production = False
    elif _args.buildtype in ['p', 'production']:
        print("get production build")
        only_production = True

if not _args.majorversion:
    raise ValueError("--majorversion must be defined")

majorversion = str(float(_args.majorversion))

# Code that provides convenient Python wrappers to call into the API:

def service(
        access_token_url, client_id, client_secret_key, endpoint_url,
        access_token=None, access_token_expiry_time=None):
    if (access_token is None or
            access_token_expiry_time is None or
            access_token_expiry_time < time.time()):
        access_token, access_token_expiry_time = (
            get_access_token_and_expiry_time(
                access_token_url, client_id, client_secret_key))

    return _Service(
        endpoint_url, access_token, access_token_expiry_time)


class _Service(object):
    def __init__(
            self, endpoint_url, access_token, access_token_expiry_time):
        self.endpoint_url = endpoint_url
        self.access_token = access_token
        self.access_token_expiry_time = access_token_expiry_time

    def __getattr__(self, attr_name):
        return _APIFunction(attr_name, self)


class _APIFunction(object):
    def __init__(self, function_name, service):
        self.function_name = function_name
        self.service = service

    def __getattr__(self, attr_name):
        # This isn't actually an API function, but a family of them.  Append
        # the requested function name to our name.
        return _APIFunction(
            "{0}.{1}".format(self.function_name, attr_name), self.service)

    def __call__(self, *args, **kwargs):
        return call_api_with_access_token(
            self.service.endpoint_url, self.service.access_token,
            self.function_name, args, kwargs)

#---------------------------------------------------------------------------
# Code that implements authentication and raw calls into the API:


def get_access_token_and_expiry_time(
        access_token_url, client_id, client_secret_key):
    """Given an API client (id and secret key) that is allowed to make API
    calls, return an access token that can be used to make calls.
    """
    response = requests.post(
        access_token_url,
        headers={
            "Authorization": u"Basic {0}".format(
                base64.b64encode(
                    "{0}:{1}".format(
                        client_id, client_secret_key
                    ).encode()
                ).decode('utf-8')
            ),
        })
    if response.status_code != 200:
        raise AuthorizationError(
            response.status_code,
            "{0}: {1}".format(
                response.status_code,
                _extract_traceback_from_response(response)))

    response_json = response.json()
    access_token_expiry_time = time.time() - 2 + response_json["expires_in"]
    return response_json["access_token"], access_token_expiry_time


class AuthorizationError(Exception):
    """Raised from the client if the server generated an error while generating
    an access token.
    """
    def __init__(self, http_code, message):
        super(AuthorizationError, self).__init__(message)
        self.http_code = http_code


def call_api_with_access_token(
        endpoint_url, access_token, function_name, args, kwargs):
    """Call into the API using an access token that was returned by
    get_access_token.
    """
    response = requests.post(
        endpoint_url,
        headers={
            "Authorization": "Bearer " + access_token,
        },
        data=dict(
            json=json.dumps([function_name, args, kwargs]),
        ))
    if response.status_code == 200:
        return response.json()

    raise APIError(
        response.status_code,
        "{0}".format(_extract_traceback_from_response(response)))


class APIError(Exception):
    """Raised from the client if the server generated an error while calling
    into the API.
    """
    def __init__(self, http_code, message):
        super(APIError, self).__init__(message)
        self.http_code = http_code


def _extract_traceback_from_response(response):
    """Helper function to extract a traceback from the web server response
    if an API call generated a server-side exception
    """
    error_message = response.text
    if response.status_code != 500:
        return error_message

    traceback = ""
    for line in error_message.split("\n"):
        if len(traceback) != 0 and line == "</textarea>":
            break
        if line == "Traceback:" or len(traceback) != 0:
            traceback += line + "\n"

    if len(traceback) == 0:
        traceback = error_message

    return html.unescape(traceback)




# def query():
if __name__ == '__main__':
    # Relevant part of the example starts here.

    # This service object retrieve a token using your Application ID and secret
    service = service(
        access_token_url="https://www.sidefx.com/oauth2/application_token",
        client_id=os.environ.get('sesi_client_id'),
        client_secret_key=os.environ.get('sesi_client_secret_key'),
        endpoint_url="https://www.sidefx.com/api/",
    )
    # Retrieve the daily builds list, if you want the latest production
    # you can skip this step
    releases_list = service.download.get_daily_builds_list(
        product='houdini', version=majorversion, platform='linux', only_production=only_production)

    latest_build=releases_list[0]['build']

    latest_release = service.download.get_daily_build_download(
        product='houdini', version=majorversion, build=latest_build, platform='linux')

    query = ( latest_release['filename'], latest_release['download_url'] )

    # return query
    print('File: {}'.format( latest_release['filename'] ) )
    print('URL: {}'.format( latest_release['download_url'] ) )
    filename=latest_release['filename']
    build=re.match('houdini-(.*)-.*', filename).groups()[0]
    print('Build: {}'.format( build ) )
    print('Hash: {}'.format( latest_release['hash'] ) )
    print('Size: {}'.format( latest_release['size'] ) )
    # print latest_release

    # # Download the file
    # local_filename = 'houdini_download/' + latest_release['filename']
    # r = requests.get(latest_release['download_url'], stream=True)
    # if r.status_code == 200:
    #     with open(local_filename, 'wb') as f:
    #         r.raw.decode_content = True
    #         shutil.copyfileobj(r.raw, f)
    # else:
    #     raise Exception('Error downloading file!')

    # # Verify the file checksum is matching
    # file_hash = hashlib.md5()
    # with open(local_filename, 'rb') as f:
    #     for chunk in iter(lambda: f.read(4096), b''):
    #         file_hash.update(chunk)
    # if file_hash.hexdigest() != latest_release['hash']:
    #     raise Exception('Checksum does not match!')
