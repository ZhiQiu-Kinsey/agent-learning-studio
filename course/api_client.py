"""Send a Bailian chat-completion request over raw HTTP; the key goes into the header, never the body."""

import json
import urllib.error
import urllib.request

from course.i18n import SOURCE_LOCALE
from course.locales import texts_for


class ProviderHTTPError(RuntimeError):
    """The provider answered with an HTTP error; the status code is kept so lessons can record it honestly."""

    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def send_bailian(request_body, api_key, timeout_seconds=60, *, locale=SOURCE_LOCALE):
    """Send a request body that has already been recorded; web runs and the CLI share this transport."""
    from local_config import API_URL

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:2000]
        # Never resend automatically: a retry could be billed twice.
        raise ProviderHTTPError(
            texts_for(locale).bailian_http_error.format(status=error.code, detail=detail),
            error.code,
        ) from None
    except urllib.error.URLError as error:
        raise RuntimeError(
            texts_for(locale).bailian_unreachable.format(reason=error.reason)
        ) from None
