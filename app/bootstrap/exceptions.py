<<<<<<< HEAD
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
=======
class BootstrapError(Exception):
    """应用启动阶段的基础异常。"""


class WorkspaceLayoutError(BootstrapError):
    """工作区目录结构不合法。"""
>>>>>>> 549c716 (Finish the basic code framework)
