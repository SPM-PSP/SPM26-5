import os
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

# --------------------- 抽象接口 ---------------------
class DatabaseInterface(ABC):
    """数据库操作统一接口，所有具体实现必须继承此类"""
    @abstractmethod
    def query(self, sql: str, params=None) -> List[Dict]:
        pass

    @abstractmethod
    def execute(self, sql: str, params=None) -> int:
        pass

    @abstractmethod
    def close(self):
        pass

    # 业务方法接口
    @abstractmethod
    def get_all_references(self, user_id: Optional[str] = None) -> List[Dict]:
        pass

    @abstractmethod
    def get_notes_by_reference(self, ref_id: str) -> List[Dict]:
        pass

    @abstractmethod
    def get_citations_for_reference(self, ref_id: str) -> List[Dict]:
        pass

    @abstractmethod
    def get_note_detail(self, note_id: str) -> Optional[Dict]:
        pass

    @abstractmethod
    def get_reference_detail(self, ref_id: str) -> Optional[Dict]:
        pass


# --------------------- 便捷工具函数（通过接口调用）---------------------
def fetch_all_references(db: DatabaseInterface, user_id: str = None):
    return db.get_all_references(user_id)

def fetch_notes_by_reference(db: DatabaseInterface, ref_id: str):
    return db.get_notes_by_reference(ref_id)

# ... 可根据需要继续添加更多工具函数，它们都只依赖接口


# --------------------- 工厂函数（入口）---------------------
def connect_to_database() -> DatabaseInterface:
    """
    从环境变量读取配置，创建并返回已连接的 DatabaseInterface 实例。
    实际返回的是 connection.DatabaseManager 对象。
    """
    from .connection import DatabaseManager      # 延迟导入避免循环依赖
    config = {
        "host": os.environ.get("AGNI_DB_HOST", "localhost"),
        "port": int(os.environ.get("AGNI_DB_PORT", 3306)),
        "user": os.environ.get("AGNI_DB_USER", "root"),
        "password": os.environ.get("AGNI_DB_PASSWORD", ""),
        "database": os.environ.get("AGNI_DB_NAME", "agni"),
    }
    db = DatabaseManager(**config)
    db.connect()
    return db