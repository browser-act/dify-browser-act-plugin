from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from browseract.client import BrowserActClient
from browseract.errors import BrowserActError


class BrowserActProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            BrowserActClient(credentials.get("api_key")).validate_credentials()
        except BrowserActError as error:
            raise ToolProviderCredentialValidationError(str(error)) from None
