from app.bootstrap.startup import bootstrap_workspace


def test_note_search_matches_tags(tmp_path):
    workspace_root = tmp_path / "demo_workspace"
    ctx = bootstrap_workspace(workspace_root)

    create_result = ctx.note_controller.create_note(
        workspace_root,
        "Research Log",
        "# Research Log\n\nTags: alpha, beta\n\nThis note tracks experiments.",
    )
    assert create_result["success"]

    search_result = ctx.search_controller.search_notes(workspace_root, "alpha")
    assert search_result["success"]
    results = tuple(search_result["data"].get("results", ()))
    assert any(
        item.get("object_kind") == "note" and item.get("title") == "Research Log"
        for item in results
    )


def test_reference_import_file_supports_tags_and_search(tmp_path):
    workspace_root = tmp_path / "demo_workspace"
    ctx = bootstrap_workspace(workspace_root)

    bib_path = tmp_path / "sample.bib"
    bib_path.write_text(
        "@article{smith2024,\n"
        "  title={Graph Systems},\n"
        "  author={Smith, Jane and Doe, John},\n"
        "  year={2024}\n"
        "}\n",
        encoding="utf-8",
    )

    import_result = ctx.reference_controller.import_reference_file(
        workspace_root,
        bib_path,
        tags=("graph", "survey"),
    )
    assert import_result["success"]

    search_result = ctx.search_controller.search_notes(workspace_root, "survey")
    assert search_result["success"]
    results = tuple(search_result["data"].get("results", ()))
    assert any(
        item.get("object_kind") == "reference" and item.get("title") == "Graph Systems"
        for item in results
    )


def test_reference_directory_import_supports_pdf_and_title_search(tmp_path):
    workspace_root = tmp_path / "demo_workspace"
    ctx = bootstrap_workspace(workspace_root)

    import_dir = tmp_path / "imports"
    import_dir.mkdir()
    pdf_path = import_dir / "DeepLearningNotes.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%Fake PDF content for tests\n")

    import_result = ctx.reference_controller.import_reference_directory(
        workspace_root,
        import_dir,
        tags=("deep-learning",),
    )
    assert import_result["success"]
    references = tuple(import_result["data"].get("references", ()))
    assert len(references) == 1

    title_search = ctx.search_controller.search_notes(workspace_root, "DeepLearningNotes")
    assert title_search["success"]
    title_results = tuple(title_search["data"].get("results", ()))
    assert any(item.get("object_kind") == "reference" for item in title_results)

    tag_search = ctx.search_controller.search_notes(workspace_root, "deep-learning")
    assert tag_search["success"]
    tag_results = tuple(tag_search["data"].get("results", ()))
    assert any(item.get("object_kind") == "reference" for item in tag_results)
