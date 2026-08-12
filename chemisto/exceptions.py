"""Exceptions raised by Chemisto's internal modules.

Every exception here is caught somewhere in the REPL and turned into a
clean Rich error message - none of them should ever surface as a raw
Python traceback to the user.
"""
from __future__ import annotations


class ChemistoError(Exception):
    """Base class for all recoverable Chemisto errors."""


class GatewayError(ChemistoError):
    """Raised when the gateway cannot be reached or returns an error."""


class GatewayConnectionError(GatewayError):
    """The gateway process could not be reached at all."""


class GatewayTimeoutError(GatewayError):
    """The gateway did not respond within the configured timeout."""


class GatewayHTTPError(GatewayError):
    """The gateway responded with an HTTP error status."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class GatewayResponseError(GatewayError):
    """The gateway responded with invalid or unexpected JSON."""


class FileContextError(ChemistoError):
    """Raised when a file cannot be added as context."""


class CommandExecutionError(ChemistoError):
    """Raised when a /run command cannot even be started."""


class SessionError(ChemistoError):
    """Raised when the local session file cannot be read or written."""
