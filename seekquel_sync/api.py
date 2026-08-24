import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from calibre_plugins.seekquel_sync import __version__
from calibre_plugins.seekquel_sync.log import note

USER_AGENT = f'Seekquel-Calibre/{__version__} (+https://seekquel.app)'

CONNECT_TIMEOUT = 30
UPLOAD_TIMEOUT = 60
POLL_TIMEOUT = 10

COVER_FIELD = 'cover'
CRLF = '\r\n'


class SeekquelError(Exception):
    def __init__(self, message, status=None, code=None):
        super().__init__(message)
        self.status = status
        self.code = code


class SeekquelUnreachable(SeekquelError):
    pass


class SeekquelApi:
    def __init__(self, base_url, key=None):
        self.base_url = (base_url or '').rstrip('/')
        self.key = key

    def is_configured(self):
        return bool(self.base_url and self.key)

    def healthcheck(self):
        return self._request('GET', '/healthcheck', authenticated=False)

    def start_pairing(self, device_name, platform):
        return self._request('POST', '/pair/start', body={
            'device_name': device_name,
            'platform': platform,
        }, authenticated=False)

    def poll_pairing(self, device_code):
        return self._request(
            'POST',
            '/pair/poll',
            body={'device_code': device_code},
            authenticated=False,
            timeout=POLL_TIMEOUT,
        )

    def report_device(self, device_name, platform, app_version):
        return self._request('PUT', '/device', body={
            'device_name': device_name,
            'platform': platform,
            'app_version': app_version,
        })

    def push_library(self, books, library_uuid=None):
        return self._request('POST', '/library', body={
            'library_uuid': library_uuid,
            'books': books,
        }, timeout=UPLOAD_TIMEOUT)

    def pull_library(self, since=None):
        query = {'since': since} if since else None

        return self._request('GET', '/library', query=query)

    def upload_cover(self, book_uuid, filename, content):
        boundary = uuid.uuid4().hex
        body = self._multipart(boundary, COVER_FIELD, filename, content)

        return self._request(
            'POST',
            f'/books/{urllib.parse.quote(book_uuid)}/cover',
            raw=body,
            content_type=f'multipart/form-data; boundary={boundary}',
            timeout=UPLOAD_TIMEOUT,
        )

    def search_books(self, term):
        return self._request('GET', '/books/search', query={'q': term})

    def _multipart(self, boundary, field, filename, content):
        prologue = (
            '--' + boundary + CRLF
            + 'Content-Disposition: form-data; name="' + field + '"; filename="'
            + Path(filename).name + '"' + CRLF
            + 'Content-Type: application/octet-stream' + CRLF + CRLF
        ).encode('utf-8')

        epilogue = (CRLF + '--' + boundary + '--' + CRLF).encode('utf-8')

        return prologue + content + epilogue

    def _request(
        self,
        method,
        path,
        body=None,
        query=None,
        authenticated=True,
        timeout=CONNECT_TIMEOUT,
        raw=None,
        content_type=None,
    ):
        if not self.base_url:
            raise SeekquelError('No Seekquel address is set.')

        url = self.base_url + path

        if query:
            url += '?' + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})

        payload = raw if raw is not None else (json.dumps(body).encode('utf-8') if body is not None else None)

        request = urllib.request.Request(url, data=payload, method=method)
        request.add_header('Accept', 'application/json')
        request.add_header('User-Agent', USER_AGENT)

        if payload is not None:
            request.add_header('Content-Type', content_type or 'application/json')

        if authenticated:
            if not self.key:
                raise SeekquelError('This library is not connected to Seekquel yet.')

            request.add_header('Authorization', 'Bearer ' + self.key)

        started = time.monotonic()

        try:
            with urllib.request.urlopen(request, timeout=timeout, context=self._ssl_context()) as response:
                body = self._decode(response.read())
                note(f'{method} {path} -> {response.status} in {time.monotonic() - started:.1f}s')

                return body
        except urllib.error.HTTPError as error:
            refusal = self._from_http_error(error)
            note(f'{method} {path} -> {error.code} {refusal.code or ""} {refusal}')

            raise refusal from error
        except urllib.error.URLError as error:
            note(f'{method} {path} -> could not reach {self.base_url}: {error.reason}')

            raise SeekquelUnreachable(f'Could not reach {self.base_url}: {error.reason}') from error
        except (TimeoutError, ssl.SSLError, OSError) as error:
            note(f'{method} {path} -> could not reach {self.base_url}: {error}')

            raise SeekquelUnreachable(f'Could not reach {self.base_url}: {error}') from error

    def _ssl_context(self):
        if self.base_url.startswith('http://'):
            return None

        return ssl.create_default_context()

    def _from_http_error(self, error):
        try:
            payload = self._decode(error.read())
        except Exception:
            payload = {}

        details = payload.get('error') if isinstance(payload, dict) else None

        if isinstance(details, dict):
            return SeekquelError(details.get('message') or error.reason, error.code, details.get('code'))

        message = payload.get('message') if isinstance(payload, dict) else None

        return SeekquelError(message or (f'{error.code} {error.reason}'), error.code)

    def _decode(self, raw):
        if not raw:
            return {}

        return json.loads(raw.decode('utf-8'))
