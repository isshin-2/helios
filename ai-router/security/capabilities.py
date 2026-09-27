from enum import Enum, auto

class Capability(Enum):
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    TERMINAL_EXECUTE = "terminal_execute"
    NETWORK_ACCESS = "network_access"
    SYSTEM_ADMIN = "system_admin"
    BROWSER_CONTROL = "browser_control"

class CapabilityToken:
    def __init__(self, capability: Capability, resource: str):
        self.capability = capability
        self.resource = resource

    def __repr__(self):
        return f"CapabilityToken({self.capability.name}, {self.resource})"
