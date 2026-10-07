"""Small loopback client for the locally built red-side adapter."""
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class GameAPIError(RuntimeError):
    def __init__(self, message, *, status=None, details=None):
        super().__init__(message)
        self.status, self.details = status, details


class RedSide:
    def __init__(self, base="http://127.0.0.1:8765"):
        self.base = base

    def session_identity(self):
        from bridge.native_identity import IdentityError, session_identity
        try:
            return session_identity()
        except IdentityError as error:
            raise GameAPIError(str(error)) from error

    def request(self, path, method="GET", body=None, *, expected_session=None):
        data = None if body is None else json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
        if expected_session is not None:
            from bridge.native_identity import IdentityError, session_token
            try:
                headers["X-CrimsonMC-Session"] = session_token(expected_session)
            except IdentityError as error:
                raise GameAPIError(str(error)) from error
        req = Request(self.base + path, data=data, method=method,
                      headers=headers)
        try:
            with urlopen(req, timeout=4) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                details = json.load(error)
            raise GameAPIError(f"{error.code}: {details}", status=error.code, details=details) from error

    def ground(self, x, y, z, length=20):
        _, result = self.request("/api/prototype/ground-probe", "POST",
                                 {"x": x, "y": y, "z": z, "length": length})
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            status, hit = self.request(f"/api/prototype/ground-result?ticket={result['ticket']}")
            if status != 202:
                if hit.get("state") != "hit":
                    raise GameAPIError("No physical ground hit; placement was discarded")
                return hit
            time.sleep(0.04)
        raise GameAPIError("Ground probe did not finish; placement was discarded")
