import pymysql
from pymysql.cursors import DictCursor
from .tool import DatabaseInterface          # 导入接口

class DatabaseManager(DatabaseInterface):
    """MySQL 数据库管理器，实现了 DatabaseInterface"""

    def __init__(self, host, port, user, password, database):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.connection = None

    def connect(self):
        self.connection = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset='utf8mb4',
            cursorclass=DictCursor,
            autocommit=True
        )

    def close(self):
        if self.connection and self.connection.open:
            self.connection.close()

    def query(self, sql, params=None):
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def execute(self, sql, params=None):
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.rowcount

    # --- 业务方法实现 ---
    def get_all_references(self, user_id=None):
        if user_id:
            sql = "SELECT ref_id, title, authors, year, doi, file_path FROM reference WHERE user_id = %s"
            return self.query(sql, (user_id,))
        return self.query("SELECT ref_id, title, authors, year, doi, file_path FROM reference")

    def get_notes_by_reference(self, ref_id):
        sql = "SELECT note_id, title, content FROM note WHERE ref_id = %s"
        return self.query(sql, (ref_id,))

    def get_citations_for_reference(self, ref_id):
        sql = """
            SELECT c.cite_index, n.note_id, n.title, n.ref_id AS note_belongs_to_ref
            FROM citation c
            JOIN note n ON c.note_id = n.note_id
            WHERE c.ref_id = %s
            ORDER BY c.cite_index
        """
        return self.query(sql, (ref_id,))

    def get_note_detail(self, note_id):
        sql = "SELECT * FROM note WHERE note_id = %s"
        result = self.query(sql, (note_id,))
        return result[0] if result else None

    def get_reference_detail(self, ref_id):
        sql = "SELECT * FROM reference WHERE ref_id = %s"
        result = self.query(sql, (ref_id,))
        return result[0] if result else None