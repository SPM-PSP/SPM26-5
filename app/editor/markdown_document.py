"""
app/editor/markdown_document.py

Markdown 文档会话对象。
阶段二增强版：
1. 维护当前笔记 Markdown 原文；
2. 维护编辑会话状态（是否修改、光标位置、文件 mtime、会话状态）；
3. 维护保存相关状态（last_saved_text、last_saved_time、version）；
4. 为 note_editor_widget / note_controller / note_service 提供统一数据接口；
5. 不直接负责数据库写入和关系解析，仅负责编辑器侧文档状态管理。
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import hashlib
import re


SESSION_STATUS_IDLE = "idle"
SESSION_STATUS_EDITING = "editing"
SESSION_STATUS_SAVED = "saved"
SESSION_STATUS_SAVE_FAILED = "save_failed"
SESSION_STATUS_EXTERNAL_MODIFIED = "external_modified"


@dataclass(slots=True)
class HeadingItem:
    """Markdown 标题项，用于后续大纲面板。"""

    level: int
    title: str
    line_number: int
    anchor: str


@dataclass(slots=True)
class MarkdownDocument:
    """
    编辑器文档对象 / 会话对象。
    """

    note_id: str | None = None
    title: str = ""
    file_path: str | None = None
    raw_text: str = ""
    is_dirty: bool = False
    cursor_position: int = 0
    file_mtime: float | None = None
    session_status: str = SESSION_STATUS_IDLE
    created_time: datetime = field(default_factory=datetime.now)
    updated_time: datetime = field(default_factory=datetime.now)
    last_saved_time: datetime | None = None
    last_saved_text: str = ""
    version: int = 0

    def get_text(self) -> str:
        """返回当前 Markdown 原文。"""
        return self.raw_text

    def set_text(self, text: str, *, mark_dirty: bool = True) -> None:
        """
        设置全文内容。
        """
        text = text or ""
        if text == self.raw_text:
            return

        self.raw_text = text
        self.updated_time = datetime.now()

        if mark_dirty:
            self.is_dirty = self.raw_text != self.last_saved_text
            self.session_status = SESSION_STATUS_EDITING if self.is_dirty else SESSION_STATUS_SAVED

    def set_title(self, title: str) -> None:
        """更新文档标题。"""
        title = title or ""
        if title == self.title:
            return

        self.title = title
        self.updated_time = datetime.now()
        self.is_dirty = True
        self.session_status = SESSION_STATUS_EDITING

    def append_text(self, text: str) -> None:
        """在文末追加文本。"""
        if not text:
            return
        self.raw_text += text
        self.is_dirty = self.raw_text != self.last_saved_text
        self.updated_time = datetime.now()
        self.session_status = SESSION_STATUS_EDITING

    def insert_text(self, index: int, text: str) -> None:
        """在指定位置插入文本。"""
        if not text:
            return

        index = max(0, min(index, len(self.raw_text)))
        self.raw_text = self.raw_text[:index] + text + self.raw_text[index:]
        self.cursor_position = index + len(text)
        self.is_dirty = self.raw_text != self.last_saved_text
        self.updated_time = datetime.now()
        self.session_status = SESSION_STATUS_EDITING

    def replace_range(self, start: int, end: int, text: str) -> None:
        """替换指定范围文本。"""
        start = max(0, start)
        end = max(start, end)
        end = min(end, len(self.raw_text))

        self.raw_text = self.raw_text[:start] + (text or "") + self.raw_text[end:]
        self.cursor_position = start + len(text or "")
        self.is_dirty = self.raw_text != self.last_saved_text
        self.updated_time = datetime.now()
        self.session_status = SESSION_STATUS_EDITING

    def clear(self) -> None:
        """清空文档内容。"""
        self.raw_text = ""
        self.cursor_position = 0
        self.is_dirty = self.raw_text != self.last_saved_text
        self.updated_time = datetime.now()
        self.session_status = SESSION_STATUS_EDITING

    def update_cursor_position(self, position: int) -> None:
        """更新光标位置。"""
        self.cursor_position = max(0, position)

    def restore_cursor_position(self) -> int:
        """返回可用于重开文档时恢复的光标位置。"""
        return max(0, min(self.cursor_position, len(self.raw_text)))

    def mark_dirty(self) -> None:
        """手动标记文档为已修改。"""
        self.is_dirty = True
        self.updated_time = datetime.now()
        self.session_status = SESSION_STATUS_EDITING

    def reset_dirty(self) -> None:
        """清除未保存标记。"""
        self.is_dirty = False

    def has_unsaved_changes(self) -> bool:
        """判断当前是否存在未保存内容。"""
        return self.title != "" and (self.is_dirty or self.raw_text != self.last_saved_text) or (
            self.title == "" and (self.is_dirty or self.raw_text != self.last_saved_text)
        )

    def set_file_mtime(self, file_mtime: float | None) -> None:
        """同步文件修改时间。"""
        self.file_mtime = file_mtime

    def mark_saved(
        self,
        *,
        file_mtime: float | None = None,
        version: int | None = None,
    ) -> None:
        """
        保存成功后调用。
        """
        now = datetime.now()
        self.is_dirty = False
        self.last_saved_time = now
        self.last_saved_text = self.raw_text
        self.updated_time = now
        self.session_status = SESSION_STATUS_SAVED

        if file_mtime is not None:
            self.file_mtime = file_mtime

        if version is not None:
            self.version = version

    def restore_after_save(
        self,
        *,
        file_mtime: float | None = None,
        version: int | None = None,
    ) -> None:
        """
        保存成功后的统一状态回写入口。
        """
        self.mark_saved(file_mtime=file_mtime, version=version)

    def mark_save_failed(self) -> None:
        """保存失败时调用。"""
        self.session_status = SESSION_STATUS_SAVE_FAILED
        self.updated_time = datetime.now()

    def mark_external_modified(self) -> None:
        """检测到文件被外部修改时调用。"""
        self.session_status = SESSION_STATUS_EXTERNAL_MODIFIED
        self.updated_time = datetime.now()

    def bind_file_path(self, file_path: str | Path) -> None:
        """绑定文档文件路径。"""
        self.file_path = str(file_path)

    def load_from_text(
        self,
        text: str,
        *,
        note_id: str | None = None,
        title: str | None = None,
        file_path: str | Path | None = None,
        file_mtime: float | None = None,
        version: int | None = None,
        cursor_position: int | None = None,
    ) -> None:
        """
        从已有文本载入文档内容。
        打开笔记时可直接调用。
        """
        self.raw_text = text or ""
        self.note_id = note_id if note_id is not None else self.note_id
        self.title = title if title is not None else self.title

        if file_path is not None:
            self.file_path = str(file_path)

        self.file_mtime = file_mtime
        if version is not None:
            self.version = version

        self.cursor_position = max(0, cursor_position or 0)
        self.is_dirty = False
        self.last_saved_text = self.raw_text
        self.last_saved_time = datetime.now()
        self.session_status = SESSION_STATUS_IDLE
        self.updated_time = datetime.now()

    def detect_external_modification(self, current_mtime: float | None) -> bool:
        """
        检查文件是否被外部修改。
        """
        if self.file_mtime is None or current_mtime is None:
            return False

        modified = current_mtime > self.file_mtime
        if modified:
            self.mark_external_modified()
        return modified

    def compute_content_hash(self) -> str:
        """返回当前内容的 sha256 摘要，可用于简单比较或去重。"""
        return hashlib.sha256(self.raw_text.encode("utf-8")).hexdigest()

    def get_plain_text(self) -> str:
        """
        返回简化纯文本。
        """
        text = self.raw_text
        text = re.sub(r"`{1,3}.*?`{1,3}", "", text, flags=re.DOTALL)
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
        text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
        text = re.sub(r"\[\[(.*?)(\|.*?)?\]\]", r"\1", text)
        text = re.sub(r"\[@([^\]]+)\]", r"\1", text)
        return text.strip()

    def extract_headings(self) -> list[HeadingItem]:
        """
        提取 Markdown 标题，供后续大纲面板使用。
        """
        headings: list[HeadingItem] = []

        for line_number, line in enumerate(self.raw_text.splitlines(), start=1):
            match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if not match:
                continue

            level = len(match.group(1))
            title = match.group(2).strip()
            anchor = self._build_heading_anchor(title)

            headings.append(
                HeadingItem(
                    level=level,
                    title=title,
                    line_number=line_number,
                    anchor=anchor,
                )
            )

        return headings

    def get_title_from_content(self) -> str:
        """
        从文档内容推断标题。
        """
        for heading in self.extract_headings():
            if heading.level == 1:
                return heading.title

        for line in self.raw_text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:80]

        return "Untitled"

    def to_save_payload(self) -> dict[str, Any]:
        """
        提供给 note_service.save_note() 的轻量载荷。
        """
        return {
            "note_id": self.note_id,
            "title": self.title or self.get_title_from_content(),
            "file_path": self.file_path,
            "markdown_content": self.raw_text,
            "cursor_position": self.cursor_position,
            "version": self.version,
            "updated_time": self.updated_time.isoformat(),
        }

    def to_open_payload(self) -> dict[str, Any]:
        """
        提供给打开/重载流程使用的轻量载荷。
        """
        return {
            "note_id": self.note_id,
            "title": self.title,
            "file_path": self.file_path,
            "cursor_position": self.cursor_position,
            "file_mtime": self.file_mtime,
            "version": self.version,
        }

    def to_dict(self) -> dict[str, Any]:
        """序列化为调试/日志友好的字典。"""
        return {
            "note_id": self.note_id,
            "title": self.title,
            "file_path": self.file_path,
            "raw_text": self.raw_text,
            "is_dirty": self.is_dirty,
            "cursor_position": self.cursor_position,
            "file_mtime": self.file_mtime,
            "session_status": self.session_status,
            "created_time": self.created_time.isoformat(),
            "updated_time": self.updated_time.isoformat(),
            "last_saved_time": (
                self.last_saved_time.isoformat() if self.last_saved_time else None
            ),
            "last_saved_text": self.last_saved_text,
            "version": self.version,
        }

    @classmethod
    def create_empty(
        cls,
        *,
        note_id: str | None = None,
        title: str = "",
        file_path: str | Path | None = None,
    ) -> "MarkdownDocument":
        """创建空文档。"""
        return cls(
            note_id=note_id,
            title=title,
            file_path=str(file_path) if file_path is not None else None,
            raw_text="",
            is_dirty=False,
            cursor_position=0,
            session_status=SESSION_STATUS_IDLE,
            last_saved_text="",
        )

    @staticmethod
    def _build_heading_anchor(title: str) -> str:
        """
        构建简易标题锚点。
        """
        anchor = title.strip().lower()
        anchor = re.sub(r"[^\w\u4e00-\u9fff\s-]", "", anchor)
        anchor = re.sub(r"\s+", "-", anchor)
        anchor = re.sub(r"-{2,}", "-", anchor)
        return anchor.strip("-")