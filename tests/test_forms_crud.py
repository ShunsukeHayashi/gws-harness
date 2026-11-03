"""Google Forms create / read / update, with publish gated on human --go."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from conftest import load_script

forms = load_script("garc-forms-helper.py")
HELPER = Path(__file__).resolve().parents[1] / "scripts" / "garc-forms-helper.py"


def _svc():
    svc = MagicMock()
    svc.forms.return_value = MagicMock()
    return svc


def test_get_form_returns_title_and_description():
    svc = _svc()
    svc.forms.return_value.get.return_value.execute.return_value = {
        "formId": "FORM123",
        "info": {
            "title": "経費精算",
            "description": "月次の申請",
            "documentTitle": "経費精算",
        },
        "items": [{"title": "金額"}],
        "publishSettings": {
            "publishState": {"isPublished": False, "isAcceptingResponses": False}
        },
    }

    result = forms.get_form("FORM123", svc=svc)

    svc.forms.return_value.get.assert_called_once_with(formId="FORM123")
    assert result["info"]["title"] == "経費精算"
    assert result["info"]["description"] == "月次の申請"
    assert result["items"][0]["title"] == "金額"


def test_create_form_is_unpublished_draft_and_does_not_publish():
    svc = _svc()
    svc.forms.return_value.create.return_value.execute.return_value = {
        "formId": "NEW1",
        "info": {"title": "SOP確認", "description": "下書き"},
    }

    result = forms.create_form("SOP確認", description="下書き", svc=svc)

    kwargs = svc.forms.return_value.create.call_args.kwargs
    assert kwargs["unpublished"] is True
    body = kwargs["body"]
    assert body["info"]["title"] == "SOP確認"
    assert body["info"]["description"] == "下書き"
    assert "publishSettings" not in body
    svc.forms.return_value.setPublishSettings.assert_not_called()
    assert result["formId"] == "NEW1"


def test_create_form_fallback_does_not_call_set_publish_settings():
    svc = _svc()
    svc.forms.return_value.create.side_effect = [
        TypeError("unexpected keyword unpublished"),
        MagicMock(execute=MagicMock(return_value={"formId": "NEW2", "info": {"title": "T"}})),
    ]

    forms.create_form("T", svc=svc)

    assert svc.forms.return_value.create.call_count == 2
    second = svc.forms.return_value.create.call_args_list[1].kwargs
    assert "unpublished" not in second
    assert "publishSettings" not in second["body"]
    svc.forms.return_value.setPublishSettings.assert_not_called()


def test_update_form_title_description_and_items_does_not_publish():
    svc = _svc()
    svc.forms.return_value.get.return_value.execute.return_value = {
        "formId": "FORM1",
        "items": [{"itemId": "itemA", "title": "旧質問"}],
        "publishSettings": {"publishState": {"isPublished": False, "isAcceptingResponses": False}},
    }
    svc.forms.return_value.batchUpdate.return_value.execute.return_value = {
        "form": {"formId": "FORM1", "info": {"title": "新タイトル"}}
    }

    forms.update_form(
        "FORM1",
        title="新タイトル",
        description="新しい説明",
        add_items=["所属部署"],
        item_index=0,
        item_title="金額（円）",
        svc=svc,
    )

    body = svc.forms.return_value.batchUpdate.call_args.kwargs["body"]
    kinds = [next(iter(req)) for req in body["requests"]]
    assert kinds == ["updateFormInfo", "updateItem", "createItem"]

    info_req = body["requests"][0]["updateFormInfo"]
    assert info_req["info"]["title"] == "新タイトル"
    assert info_req["info"]["description"] == "新しい説明"
    assert "title" in info_req["updateMask"]
    assert "description" in info_req["updateMask"]

    item_req = body["requests"][1]["updateItem"]
    assert item_req["location"]["index"] == 0
    assert item_req["item"]["title"] == "金額（円）"
    assert item_req["item"]["itemId"] == "itemA"

    created = body["requests"][2]["createItem"]
    assert created["item"]["title"] == "所属部署"
    assert created["location"]["index"] == 1
    assert "questionItem" in created["item"]

    svc.forms.return_value.setPublishSettings.assert_not_called()
    assert all("publishSettings" not in req and "setPublishSettings" not in req for req in body["requests"])


def test_publish_without_go_does_not_call_api():
    svc = _svc()
    with pytest.raises(SystemExit) as exc:
        forms.set_publish_settings("FORM1", go=False, svc=svc)
    assert exc.value.code == 2
    svc.forms.return_value.setPublishSettings.assert_not_called()
    svc.forms.return_value.batchUpdate.assert_not_called()


def test_publish_with_go_sets_publish_state():
    svc = _svc()
    svc.forms.return_value.setPublishSettings.return_value.execute.return_value = {
        "formId": "FORM1",
        "publishSettings": {"publishState": {"isPublished": True, "isAcceptingResponses": True}},
    }

    forms.set_publish_settings("FORM1", go=True, published=True, accepting=True, svc=svc)

    kwargs = svc.forms.return_value.setPublishSettings.call_args.kwargs
    assert kwargs["formId"] == "FORM1"
    state = kwargs["body"]["publishSettings"]["publishState"]
    assert state == {"isPublished": True, "isAcceptingResponses": True}
    assert kwargs["body"]["updateMask"] == "publishState"


def test_publish_refuses_accepting_while_unpublished_even_with_go():
    svc = _svc()
    with pytest.raises(SystemExit) as exc:
        forms.set_publish_settings(
            "FORM1", go=True, published=False, accepting=True, svc=svc
        )
    assert exc.value.code == 2
    svc.forms.return_value.setPublishSettings.assert_not_called()


def test_close_responses_with_go_keeps_form_published():
    svc = _svc()
    svc.forms.return_value.setPublishSettings.return_value.execute.return_value = {}

    forms.set_publish_settings("FORM1", go=True, published=True, accepting=False, svc=svc)

    state = svc.forms.return_value.setPublishSettings.call_args.kwargs["body"]["publishSettings"]["publishState"]
    assert state["isPublished"] is True
    assert state["isAcceptingResponses"] is False


def test_shell_publish_without_go_exits_before_python(tmp_path):
    """The bash gate must refuse --go-less publish without invoking the helper."""
    root = Path(__file__).resolve().parents[1]
    script = """
set -euo pipefail
source "$GARC_DIR/lib/forms.sh"
garc_forms publish FORM1
"""
    env = dict(**{k: v for k, v in __import__("os").environ.items() if k != "PYTHONPATH"})
    env["GARC_DIR"] = str(root)
    env["PATH"] = str(tmp_path) + ":" + env.get("PATH", "")
    python_stub = tmp_path / "python3"
    python_stub.write_text("#!/bin/sh\necho python-was-called >&2\nexit 99\n")
    python_stub.chmod(0o755)
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 2
    assert "HUMAN GO" in result.stderr
    assert "python-was-called" not in result.stderr


def test_publish_cli_without_go_exits_2_and_mentions_human_go():
    result = subprocess.run(
        [sys.executable, str(HELPER), "publish", "FORM1"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    combined = result.stderr + result.stdout
    assert "HUMAN GO" in combined
    assert "--go" in combined
