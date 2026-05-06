# Agni DTO Contracts

本文档用于冻结阶段一到阶段三的基础接口契约。
原则：先冻结对象形状，再推进各模块实现。
任何跨模块调用，优先传 DTO 或明确的 command 对象，不直接传散乱 dict。

---

## 1. 启动与上下文

### AppConfig
位置：`app/bootstrap/config.py`

职责：
- 提供应用级基础配置
- 用于 QApplication 初始化

当前字段：
- `app_name: str`
- `organization_name: str`

### WorkspaceConfig
位置：`app/bootstrap/config.py`

职责：
- 统一描述工作区路径
- 供 bootstrap / service / storage 共用

当前字段：
- `workspace_root: Path`
- `notes_dir: Path`
- `attachments_dir: Path`
- `exports_dir: Path`
- `agni_dir: Path`
- `db_path: Path`
- `state_path: Path`
- `cache_dir: Path`

### AppContext
位置：`app/bootstrap/app_context.py`

职责：
- 保存当前工作区上下文
- 为后续 service / controller / main window 装配预留入口

当前字段：
- `workspace_root: Path`
- `db_path: Path`
- `note_service: Any | None`
- `search_service: Any | None`
- `reference_service: Any | None`

---

## 2. 工作区 DTO

### WorkspaceDTO
位置：`app/domain/dto/workspace_dto.py`

职责：
- 提供工作区对象的轻量表示
- 可供 UI / service / debug 输出使用

字段：
- `root_path: str`
- `notes_path: str`
- `attachments_path: str`
- `exports_path: str`
- `db_path: str`

### WorkspaceStatsDTO
位置：`app/domain/dto/workspace_dto.py`

职责：
- 提供工作区统计信息
- 后续可在状态栏或设置页展示

字段：
- `note_count: int`
- `attachment_count: int`

---

## 3. 笔记 DTO

### NoteDTO
位置：`app/domain/dto/note_dto.py`

职责：
- 表示完整笔记对象
- 供 service / repository / controller 传递

字段：
- `note_id: str`
- `title: str`
- `rel_path: str`
- `markdown: str`
- `updated_at: str`

### SaveNoteCommand
位置：`app/domain/dto/note_dto.py`

职责：
- 封装保存笔记时需要的输入
- 避免 save 接口直接接收多个散乱参数

字段：
- `note_id: str`
- `title: str`
- `markdown: str`

### NoteListItemDTO
位置：`app/domain/dto/note_dto.py`

职责：
- 提供笔记列表展示所需的轻量信息
- 供左侧 note list 使用

字段：
- `note_id: str`
- `title: str`
- `rel_path: str`
- `updated_at: str`

---

## 4. 阶段一接口边界

阶段一先冻结以下边界，不允许越界：

- `main.py` 负责解析参数、调用 bootstrap、启动 QApplication、显示主窗口
- `bootstrap/*` 负责工作区路径解析、目录补齐、上下文创建
- `ui/*` 不直接操作 sqlite，不直接写 SQL
- `editor/*` 不直接保存 markdown 文件，不直接写数据库
- `storage/*` 不 import UI 层对象
- `controller` 负责 UI 到 service 的中介
- `service` 负责业务流程
- `repository / storage` 负责持久化

---

## 5. 当前阶段约定

阶段一的目标不是做完整功能，而是保证：

- 项目可启动
- 工作区目录可自动补齐
- 主窗口可显示
- 中央编辑器可输入
- 测试 `test_workspace_bootstrap.py` 可通过

---

## 6. 后续扩展原则

后续增加 SearchDTO / LinkDTO / ReferenceDTO / PdfDTO / CitationDTO 时，遵循以下规则：

1. 先定义 DTO 文件和字段
2. 再定义 service 接口
3. 再接 controller
4. 最后接 UI 展示

禁止跳过契约直接在 UI 或 repository 中硬写临时字段。