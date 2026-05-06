class AgniError(Exception):
    """Base exception for user-facing application errors."""


class WorkspaceError(AgniError):
    """Raised when a workspace cannot be validated or initialized."""


class WorkspaceValidationError(WorkspaceError):
    """Raised when the workspace path itself is invalid."""


class WorkspaceInitializationError(WorkspaceError):
    """Raised when the workspace bootstrap process fails."""


class StartupError(AgniError):
    """Raised when the application cannot finish startup."""
