"""Insert paragraphs into an existing Google Doc via documents.batchUpdate."""

from unittest.mock import MagicMock

import pytest

from conftest import load_script

drive = load_script("garc-drive-helper.py")


def _doc_with_heading():
    return {
        "body": {
            "content": [
                {
                    "startIndex": 1,
                    "endIndex": 10,
                    "paragraph": {
                        "elements": [{"textRun": {"content": "手順\n"}}],
                        "paragraphStyle": {"namedStyleType": "HEADING_1"},
                    },
                },
                {
                    "startIndex": 10,
                    "endIndex": 24,
                    "paragraph": {
                        "elements": [{"textRun": {"content": "既存の本文です\n"}}],
                        "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                    },
                },
            ]
        }
    }


def test_append_doc_still_inserts_raw_text_at_end():
    svc = MagicMock()
    svc.documents.return_value.get.return_value.execute.return_value = _doc_with_heading()

    drive.append_doc("DOC1", "追記", svc_docs=svc)

    body = svc.documents.return_value.batchUpdate.call_args.kwargs["body"]
    insert = body["requests"][0]["insertText"]
    assert insert["location"]["index"] == 23
    assert insert["text"] == "追記"


def test_insert_paragraph_after_heading():
    svc = MagicMock()
    svc.documents.return_value.get.return_value.execute.return_value = _doc_with_heading()

    drive.insert_doc(
        "DOC1",
        "正本: https://docs.google.com/document/d/abc",
        after_heading="手順",
        svc_docs=svc,
    )

    body = svc.documents.return_value.batchUpdate.call_args.kwargs["body"]
    insert = body["requests"][0]["insertText"]
    assert svc.documents.return_value.batchUpdate.call_args.kwargs["documentId"] == "DOC1"
    assert insert["location"]["index"] == 10
    assert insert["text"] == "正本: https://docs.google.com/document/d/abc\n"


def test_insert_paragraph_after_heading_when_heading_is_last():
    doc = {
        "body": {
            "content": [
                {
                    "startIndex": 1,
                    "endIndex": 10,
                    "paragraph": {
                        "elements": [{"textRun": {"content": "手順\n"}}],
                        "paragraphStyle": {"namedStyleType": "HEADING_1"},
                    },
                }
            ]
        }
    }
    svc = MagicMock()
    svc.documents.return_value.get.return_value.execute.return_value = doc

    drive.insert_doc("DOC1", "正本: https://docs.google.com/document/d/abc", after_heading="手順", svc_docs=svc)

    insert = svc.documents.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]["insertText"]
    assert insert["location"]["index"] == 9
    assert insert["text"] == "\n正本: https://docs.google.com/document/d/abc"


def test_insert_paragraph_at_end():
    svc = MagicMock()
    svc.documents.return_value.get.return_value.execute.return_value = _doc_with_heading()

    drive.insert_doc("DOC1", "末尾の段落", at_end=True, svc_docs=svc)

    insert = svc.documents.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]["insertText"]
    assert insert["location"]["index"] == 23
    assert insert["text"] == "\n末尾の段落"


def test_insert_paragraph_at_explicit_index():
    svc = MagicMock()
    svc.documents.return_value.get.return_value.execute.return_value = _doc_with_heading()

    drive.insert_doc("DOC1", "途中", index=10, svc_docs=svc)

    insert = svc.documents.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]["insertText"]
    assert insert["location"]["index"] == 10
    assert insert["text"] == "途中\n"


def test_missing_heading_does_not_write():
    svc = MagicMock()
    svc.documents.return_value.get.return_value.execute.return_value = _doc_with_heading()

    with pytest.raises(SystemExit) as exc:
        drive.insert_doc("DOC1", "正本: x", after_heading="存在しない見出し", svc_docs=svc)
    assert exc.value.code == 1
    svc.documents.return_value.batchUpdate.assert_not_called()


def test_plan_insert_rejects_index_past_end():
    with pytest.raises(ValueError):
        drive.plan_doc_insert(_doc_with_heading(), "x", index=99)
