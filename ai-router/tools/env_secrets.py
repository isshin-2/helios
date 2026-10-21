"""
HELIOS — Safe Environment & Configuration Auditing Tool
Inspects environment variables and .env configuration while enforcing strict
secret redaction for keys, tokens, and credentials.
"""

import os
from typing import Tuple, Optional, List
from pydantic import BaseModel, Field
from tools.base import BaseTool
from security.permissions import PermissionManager
from core.secret_redactor import redact

class EnvSecretsInput(BaseModel):
    variable_name: Optional[str] = Field(
        default=None,
        description="Optional name of a specific environment variable to query (e.g. 'OLLAMA_HOST', 'PAIR_HOST')."
    )
    show_keys_only: Optional[bool] = Field(
        default=True,
        description="If true, returns only the names of defined variables and their status, preventing value leakage."
    )

class EnvSecretsTool(BaseTool):
    """
    Safely inspect environment flags, hosts, and configuration state with redacting defense.
    """
    def __init__(self, permission_manager: Optional[PermissionManager] = None):
        self.permission_manager = permission_manager

    @property
    def name(self) -> str:
        return "env_secrets"

    @property
    def aliases(self) -> List[str]:
        return ["EnvSecretsTool", "env_audit"]

    @property
    def description(self) -> str:
        return (
            "Safely inspect active environment variables, configuration parameters, "
            "and service hosts with automatic redaction of confidential secrets."
        )

    @property
    def input_schema(self) -> type[BaseModel]:
        return EnvSecretsInput

    @property
    def requires_permission(self) -> bool:
        return False

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        var_name = kwargs.get("variable_name")
        show_keys_only = kwargs.get("show_keys_only", True)

        if var_name:
            val = os.environ.get(var_name)
            if val is None:
                return (f"Environment variable '{var_name}' is NOT set.", self.name)
            
            # Check if variable name indicates sensitive secret
            sensitive_indicators = ["KEY", "SECRET", "TOKEN", "PASSWORD", "AUTH", "CREDENTIAL", "PRIVATE"]
            if any(ind in var_name.upper() for ind in sensitive_indicators):
                masked = f"{val[:4]}...{val[-4:]}" if len(val) > 8 else "***REDACTED***"
                return (f"{var_name} is set: {masked} (length: {len(val)})", self.name)
            
            # Apply global redactor
            safe_val = redact(val)
            return (f"{var_name} = {safe_val}", self.name)

        # Listing mode
        helios_related = []
        general = []
        for k in sorted(os.environ.keys()):
            if any(term in k.upper() for term in ["HELIOS", "PAIR", "OLLAMA", "HIKARI", "SOLSTICE", "MODEL", "PORT", "HOST"]):
                helios_related.append(k)
            else:
                general.append(k)

        lines = ["**Active HELIOS & Service Configuration Keys:**"]
        for k in helios_related:
            if show_keys_only:
                lines.append(f"- `{k}` (set)")
            else:
                val = os.environ.get(k, "")
                if any(ind in k.upper() for ind in ["KEY", "SECRET", "TOKEN", "PASSWORD"]):
                    val_str = "***REDACTED***"
                else:
                    val_str = redact(val[:60])
                lines.append(f"- `{k}` = {val_str}")

        lines.append(f"\n*Total general system environment variables defined: {len(general)}*")
        return ("\n".join(lines), self.name)
