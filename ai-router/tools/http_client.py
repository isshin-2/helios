"""
HELIOS — Safe HTTP / REST Request Client Tool
Allows agents to make controlled HTTP requests (GET, POST, PUT, DELETE, HEAD)
to test APIs, fetch JSON data, query local endpoints, or verify webhooks.
"""

import httpx
from typing import Tuple, Dict, Any, Optional, List
from pydantic import BaseModel, Field
from tools.base import BaseTool
from security.permissions import PermissionManager

class HttpClientInput(BaseModel):
    url: str = Field(..., description="Target URL (e.g. 'http://localhost:8000/health' or 'https://api.github.com').")
    method: str = Field(default="GET", description="HTTP method: 'GET', 'POST', 'PUT', 'DELETE', 'HEAD'.")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Optional custom HTTP headers.")
    json_body: Optional[Dict[str, Any]] = Field(default=None, description="Optional JSON payload for POST/PUT requests.")
    timeout: Optional[float] = Field(default=15.0, description="Request timeout in seconds (default: 15.0).")

class HttpClientTool(BaseTool):
    """
    Standard HTTP client tool with timeout control and safe payload parsing.
    """
    def __init__(self, permission_manager: Optional[PermissionManager] = None):
        self.permission_manager = permission_manager

    @property
    def name(self) -> str:
        return "http_client"

    @property
    def aliases(self) -> List[str]:
        return ["HttpClientTool", "http_request"]

    @property
    def description(self) -> str:
        return (
            "Make safe HTTP requests (GET, POST, etc.) to query local services, "
            "inspect REST APIs, test webhooks, or fetch status endpoints."
        )

    @property
    def input_schema(self) -> type[BaseModel]:
        return HttpClientInput

    @property
    def requires_permission(self) -> bool:
        return False

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        url = kwargs.get("url", "").strip()
        method = kwargs.get("method", "GET").upper().strip()
        headers = kwargs.get("headers") or {}
        json_body = kwargs.get("json_body")
        timeout = float(kwargs.get("timeout") or 15.0)

        if not url:
            return ("Error: 'url' parameter is required.", self.name)

        if not (url.startswith("http://") or url.startswith("https://")):
            return ("Error: 'url' must start with http:// or https://", self.name)

        # Restrict dangerous internal cloud metadata IPs
        blocked_hosts = ["169.254.169.254", "metadata.google.internal"]
        if any(b in url for b in blocked_hosts):
            return ("Error: Target URL is restricted by safety policy.", self.name)

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_body
                )
                status = response.status_code
                content_type = response.headers.get("content-type", "")

                try:
                    body_text = response.text
                except Exception:
                    body_text = f"<Binary data: {len(response.content)} bytes>"

                # Truncate response body if excessive
                if len(body_text) > 4000:
                    body_text = body_text[:4000] + f"\n\n... [truncated {len(body_text) - 4000} characters] ..."

                summary = (
                    f"**HTTP {method} {url} -> Status {status}**\n"
                    f"- Content-Type: {content_type}\n"
                    f"- Body:\n```\n{body_text}\n```"
                )
                return (summary, self.name)
        except httpx.TimeoutException:
            return (f"Error: HTTP request to {url} timed out after {timeout}s.", self.name)
        except Exception as e:
            return (f"Error performing HTTP request: {e}", self.name)
