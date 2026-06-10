import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from django.conf import settings
from django.core.cache import cache

_logger = logging.getLogger(__name__)


@dataclass
class DrupalMessagingClientError(Exception):
    status_code: int
    code: str
    message: str = ""


class DrupalMessagingClient:
    """Client for Drupal messaging endpoints used by the sales API."""

    _TOKEN_CACHE_KEY = "drupal_messaging:oauth_access_token:v1"

    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    @staticmethod
    def _build_safe_url(base_url: str, path: str) -> str:
        """Build a URL safely from configured base URL and relative path."""
        if not isinstance(path, str) or not path.strip():
            raise ValueError("Path must be a non-empty string.")

        candidate = path.strip()
        if "://" in candidate or candidate.startswith("//"):
            raise ValueError("Absolute URLs are not allowed.")

        segments = [segment for segment in candidate.split("/") if segment != ""]
        if any(segment in {".", ".."} for segment in segments):
            raise ValueError("Path traversal segments are not allowed.")

        base = base_url.rstrip("/") + "/"
        full = urljoin(base, "/".join(segments))

        base_parsed = urlparse(base)
        full_parsed = urlparse(full)
        if (base_parsed.scheme, base_parsed.netloc) != (
            full_parsed.scheme,
            full_parsed.netloc,
        ):
            raise ValueError("Resolved URL escaped configured base URL.")

        return full

    def _extract_error_message(self, response: requests.Response) -> str:
        """Extract human-readable message from an upstream response payload."""
        try:
            payload = response.json()
        except ValueError:
            return ""

        if isinstance(payload, dict):
            return str(payload.get("message") or payload.get("detail") or "")
        return ""

    def _get_access_token(self) -> str:
        """Get OAuth access token from cache or Drupal token endpoint."""
        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        cached_token = cache.get(self._TOKEN_CACHE_KEY)
        if cached_token:
            self._access_token = cached_token
            # Cache timeout is authoritative, keep in-memory token for this process.
            self._token_expires_at = now + 60
            return cached_token

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "grant_type": "client_credentials",
            "client_id": settings.DRUPAL_SEARCH_API_CLIENT_ID,
            "client_secret": settings.DRUPAL_SEARCH_API_CLIENT_SECRET,
        }

        try:
            response = requests.post(
                settings.DRUPAL_SEARCH_API_TOKEN_URL,
                data=payload,
                headers=headers,
                timeout=settings.DRUPAL_SEARCH_API_TIMEOUT,
                verify=settings.DRUPAL_SEARCH_API_VERIFY_SSL,
            )
        except requests.RequestException as exc:
            raise DrupalMessagingClientError(
                status_code=503,
                code="temporary_failure",
                message="Unable to fetch Drupal OAuth token.",
            ) from exc

        if response.status_code >= 400:
            raise DrupalMessagingClientError(
                status_code=response.status_code,
                code="oauth_failed",
                message=self._extract_error_message(response)
                or "Drupal OAuth request failed.",
            )

        token_payload = response.json()
        access_token = token_payload.get("access_token")
        if not access_token:
            raise DrupalMessagingClientError(
                status_code=502,
                code="oauth_invalid_response",
                message="OAuth response missing access_token.",
            )

        expires_in = int(token_payload.get("expires_in", 3600))
        cache_timeout = max(expires_in - 30, 1)
        self._access_token = access_token
        self._token_expires_at = now + cache_timeout
        cache.set(self._TOKEN_CACHE_KEY, access_token, timeout=cache_timeout)
        return access_token

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        expected_statuses: Tuple[int, ...] = (200,),
    ) -> Dict[str, Any]:
        """Perform a request against Drupal messaging API with bounded retries."""
        url = self._build_safe_url(settings.DRUPAL_SEARCH_API_BASE_URL, path)
        retries = max(int(getattr(settings, "DRUPAL_SEARCH_API_RETRY_COUNT", 2)), 0)

        for attempt in range(retries + 1):
            try:
                token = self._get_access_token()
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                }
                response = requests.request(
                    method,
                    url,
                    headers=headers,
                    timeout=settings.DRUPAL_SEARCH_API_TIMEOUT,
                    json=payload,
                    verify=settings.DRUPAL_SEARCH_API_VERIFY_SSL,
                )
            except requests.RequestException as exc:
                if attempt < retries:
                    continue
                raise DrupalMessagingClientError(
                    status_code=503,
                    code="temporary_failure",
                    message="Drupal request failed due to network error.",
                ) from exc

            if response.status_code in expected_statuses:
                return response.json()

            if response.status_code >= 500:
                if attempt < retries:
                    continue
                raise DrupalMessagingClientError(
                    status_code=503,
                    code="temporary_failure",
                    message="Drupal messaging API temporary failure.",
                )

            if response.status_code == 404:
                raise DrupalMessagingClientError(
                    status_code=404,
                    code="not_found",
                    message=self._extract_error_message(response),
                )
            if response.status_code in {401, 403}:
                raise DrupalMessagingClientError(
                    status_code=response.status_code,
                    code="forbidden",
                    message=self._extract_error_message(response),
                )
            if response.status_code == 400:
                raise DrupalMessagingClientError(
                    status_code=400,
                    code="invalid_request",
                    message=self._extract_error_message(response),
                )

            raise DrupalMessagingClientError(
                status_code=response.status_code,
                code="upstream_error",
                message=self._extract_error_message(response),
            )

        raise DrupalMessagingClientError(
            status_code=503,
            code="temporary_failure",
            message="Drupal messaging API temporary failure.",
        )

    def get_thread(self, application_id: int) -> Dict[str, Any]:
        """Fetch message thread for a specific application."""
        return self._request(
            method="GET",
            path=f"applications/{application_id}/messages",
            expected_statuses=(200,),
        )

    def post_sales_reply(self, application_id: int, body: str) -> Dict[str, Any]:
        """Create a salesperson message for a specific application."""
        if not isinstance(body, str) or not body.strip():
            raise DrupalMessagingClientError(
                status_code=400,
                code="empty_body",
                message="Message body cannot be empty.",
            )

        return self._request(
            method="POST",
            path=f"applications/{application_id}/messages",
            payload={"body": body, "sender_role": "sales"},
            expected_statuses=(200, 201),
        )
