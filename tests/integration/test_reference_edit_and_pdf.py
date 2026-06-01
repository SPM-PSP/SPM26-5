from app.bootstrap.startup import bootstrap_workspace


def test_reference_update_persists_and_searches_by_new_tag(tmp_path):
    workspace_root = tmp_path / "demo_workspace"
    ctx = bootstrap_workspace(workspace_root)

    create_result = ctx.reference_controller.create_reference(
        workspace_root,
        {
            "title": "Old Title",
            "authors": ("Jane Smith",),
            "tags": ("initial",),
            "year": 2024,
        },
    )
    assert create_result["success"]
    reference = dict(create_result["data"]["reference"])

    update_result = ctx.reference_controller.update_reference(
        workspace_root,
        str(reference["reference_id"]),
        {
            "title": "Updated Title",
            "authors": ("Jane Smith", "John Doe"),
            "tags": ("updated-tag", "graph"),
            "year": 2025,
            "entry_type": "article",
        },
    )
    assert update_result["success"]

    get_result = ctx.reference_controller.get_reference(workspace_root, str(reference["reference_id"]))
    assert get_result["success"]
    updated = dict(get_result["data"]["reference"])
    assert updated["title"] == "Updated Title"
    assert tuple(updated["tags"]) == ("updated-tag", "graph")

    search_result = ctx.search_controller.search_notes(workspace_root, "updated-tag")
    assert search_result["success"]
    results = tuple(search_result["data"].get("results", ()))
    assert any(
        item.get("object_kind") == "reference" and item.get("title") == "Updated Title"
        for item in results
    )


def test_open_reference_pdf_reports_page_count(tmp_path):
    workspace_root = tmp_path / "demo_workspace"
    ctx = bootstrap_workspace(workspace_root)

    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>endobj\n"
        b"3 0 obj<< /Type /Page /Parent 2 0 R >>endobj\n"
        b"4 0 obj<< /Type /Page /Parent 2 0 R >>endobj\n"
        b"trailer<< /Root 1 0 R >>\n%%EOF\n"
    )

    import_result = ctx.reference_controller.import_reference_file(
        workspace_root,
        source_pdf,
        tags=("pdf",),
    )
    assert import_result["success"]
    reference = dict(import_result["data"]["references"][0])

    open_result = ctx.pdf_controller.open_reference_pdf(workspace_root, str(reference["reference_id"]))
    assert open_result["success"]
    pdf = dict(open_result["data"]["pdf"])
    assert pdf["page_count"] == 2
    assert str(pdf["file_path"]).endswith(".pdf")
