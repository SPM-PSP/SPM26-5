class BootstrapError(Exception):
    """应用启动阶段的基础异常。"""


class WorkspaceLayoutError(BootstrapError):
    """工作区目录结构不合法。"""