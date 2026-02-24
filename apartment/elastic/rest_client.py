import logging
import time
from typing import Any, Dict, Optional

import requests
from django.conf import settings

_logger = logging.getLogger(__name__)


# TODO: implement access token caching and refresh from database
class DrupalSearchClient:
    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _get_access_token(self) -> Optional[str]:
        token_url = settings.DRUPAL_SEARCH_API_TOKEN_URL
        client_id = settings.DRUPAL_SEARCH_API_CLIENT_ID
        client_secret = settings.DRUPAL_SEARCH_API_CLIENT_SECRET

        if not token_url or not client_id or not client_secret:
            return None

        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "rest_client",
        }

        response = requests.post(
            token_url,
            data=data,
            headers=headers,
            timeout=settings.DRUPAL_SEARCH_API_TIMEOUT,
            verify=settings.DRUPAL_SEARCH_API_VERIFY_SSL,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ValueError("OAuth token response missing access_token")
        expires_in = int(payload.get("expires_in", 3600))
        self._access_token = token
        # Refresh a bit early to avoid edge timing failures.
        self._token_expires_at = now + max(expires_in - 30, 0)
        return token

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Dict:
        base_url = settings.DRUPAL_SEARCH_API_BASE_URL.rstrip("/")
        url = f"{base_url}/{path.lstrip('/')}"
        request_params: Dict[str, Any] = dict(params or {})
        request_params = self._normalize_pagination_params(request_params)
        headers = {
            "Accept": "application/json",
            "Accept-Language": settings.LANGUAGE_CODE,
        }
        token = self._get_access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        request_timeout = (
            timeout if timeout is not None else settings.DRUPAL_SEARCH_API_TIMEOUT
        )

        import logging

        _logger = logging.getLogger(__name__)
        _logger.debug(
            "DrupalSearchClient GET request: url=%s, params=%s, headers=%s, timeout=%s",
            url,
            request_params,
            {k: v for k, v in headers.items() if k != "Authorization"},
            request_timeout,
        )

        response = requests.get(
            url,
            params=request_params,
            headers=headers,
            timeout=request_timeout,
            verify=settings.DRUPAL_SEARCH_API_VERIFY_SSL,
        )

        if response.status_code >= 400:
            _logger.error(
                "Drupal search API request failed: %s %s (%s)",
                response.status_code,
                url,
                response.text,
            )
        response.raise_for_status()
        return response.json()

    def _normalize_pagination_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        size_value = params.pop("limit", None)
        if size_value is not None and "size" not in params:
            params["size"] = size_value

        if "page" in params:
            params.pop("offset", None)
            return params

        offset_value = params.pop("offset", None)
        if offset_value is None:
            return params

        if "size" in params:
            try:
                size = int(params["size"])
                offset = int(offset_value)
            except (TypeError, ValueError):
                params["from"] = offset_value
                return params
            if size > 0:
                params["page"] = max(1, (offset // size) + 1)
                return params

        if "from" not in params:
            params["from"] = offset_value
        return params
