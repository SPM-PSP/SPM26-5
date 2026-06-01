from database.tool import connect_to_database, initialize_database


def test_initialize_database_creates_expected_tables(tmp_path):
    db_path = tmp_path / "workspace" / ".agni" / "agni.db"

    initialize_database(db_path)

    with connect_to_database(db_path) as connection:
        table_rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
        ).fetchall()
        table_names = {str(row["name"]) for row in table_rows}
        version_row = connection.execute(
            "SELECT value FROM app_metadata WHERE key = 'workspace_version'"
        ).fetchone()
        notes_columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(notes)").fetchall()
        }
        references_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(references_catalog)").fetchall()
        }

    assert "notes" in table_names
    assert "note_links" in table_names
    assert "references_catalog" in table_names
    assert "pdf_annotations" in table_names
    assert "citations_catalog" in table_names
    assert "object_planets" in table_names
    assert "notes_fts" in table_names
    assert "tags_json" in notes_columns
    assert "tags_json" in references_columns
    assert version_row is not None
    assert str(version_row["value"]) == "2"


def test_initialize_database_is_idempotent(tmp_path):
    db_path = tmp_path / "workspace" / ".agni" / "agni.db"

    initialize_database(db_path)
    initialize_database(db_path)

    with connect_to_database(db_path) as connection:
        version_rows = connection.execute(
            "SELECT COUNT(*) AS count FROM migration_version WHERE version = 2"
        ).fetchone()

    assert version_rows is not None
    assert int(version_rows["count"]) == 1
