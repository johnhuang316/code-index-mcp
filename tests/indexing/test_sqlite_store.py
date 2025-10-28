from code_index_mcp.indexing.sqlite_store import (
    SCHEMA_VERSION,
    SQLiteIndexStore,
    SQLiteSchemaMismatchError,
)


def test_initialize_schema_creates_tables(tmp_path):
    db_path = tmp_path / "index.db"
    store = SQLiteIndexStore(str(db_path))

    store.initialize_schema()

    assert db_path.exists()
    with store.connect() as conn:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"metadata", "files", "symbols"} <= tables
        schema_version = store.get_metadata(conn, "schema_version")
        assert schema_version == SCHEMA_VERSION


def test_schema_mismatch_raises(tmp_path):
    db_path = tmp_path / "index.db"
    store = SQLiteIndexStore(str(db_path))
    store.initialize_schema()

    # Manually tamper schema version
    with store.connect() as conn:
        conn.execute(
            "UPDATE metadata SET value = ? WHERE key = 'schema_version'",
            ("0",),
        )

    try:
        store.initialize_schema()
    except SQLiteSchemaMismatchError:
        pass
    else:
        raise AssertionError("Expected schema mismatch to raise error")


def test_set_and_get_metadata_roundtrip(tmp_path):
    db_path = tmp_path / "index.db"
    store = SQLiteIndexStore(str(db_path))
    store.initialize_schema()

    with store.connect() as conn:
        store.set_metadata(conn, "project_path", "/tmp/test-project")
        conn.commit()

    with store.connect() as conn:
        assert store.get_metadata(conn, "project_path") == "/tmp/test-project"
