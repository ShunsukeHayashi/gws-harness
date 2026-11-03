"""Forms OAuth scopes and Forms API enablement probe."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from conftest import load_script

ROOT = Path(__file__).resolve().parents[1]
setup = load_script("garc-setup.py")
import garc_core  # noqa: E402


def test_scope_map_has_forms_tasks_and_profiles():
    scope_map = json.loads((ROOT / "config" / "scope-map.json").read_text())
    tasks = scope_map["tasks"]
    assert "https://www.googleapis.com/auth/forms.body.readonly" in tasks["read_form"]["scopes"]
    assert tasks["read_form"]["gate"] == "none"
    assert "https://www.googleapis.com/auth/forms.body" in tasks["create_form"]["scopes"]
    assert tasks["create_form"]["gate"] == "preview"
    assert "https://www.googleapis.com/auth/forms.body" in tasks["update_form"]["scopes"]
    assert tasks["update_form"]["gate"] == "preview"
    assert tasks["publish_form"]["gate"] == "approval"
    assert "https://www.googleapis.com/auth/forms.body" in tasks["publish_form"]["scopes"]
    assert "https://www.googleapis.com/auth/forms.responses.readonly" in tasks["read_form_responses"]["scopes"]

    patterns = scope_map["keyword_patterns"]
    assert "create form" in patterns["create_form"]
    assert "publish form" in patterns["publish_form"]

    for profile in ("writer", "admin", "backoffice_agent"):
        scopes = scope_map["profiles"][profile]["scopes"]
        assert "https://www.googleapis.com/auth/forms.body" in scopes
    readonly = scope_map["profiles"]["readonly"]["scopes"]
    assert "https://www.googleapis.com/auth/forms.body.readonly" in readonly
    assert "https://www.googleapis.com/auth/forms.responses.readonly" in readonly


def test_gate_policy_classifies_publish_as_approval():
    policy = json.loads((ROOT / "config" / "gate-policy.json").read_text())
    assert "read_form" in policy["gates"]["none"]["tasks"]
    assert "create_form" in policy["gates"]["preview"]["tasks"]
    assert "update_form" in policy["gates"]["preview"]["tasks"]
    assert "publish_form" in policy["gates"]["approval"]["tasks"]


def test_runtime_scope_lists_include_forms():
    assert "https://www.googleapis.com/auth/forms.body" in garc_core.ALL_SCOPES
    assert "https://www.googleapis.com/auth/forms.responses.readonly" in garc_core.ALL_SCOPES
    assert "https://www.googleapis.com/auth/forms.body.readonly" in garc_core.PROFILE_SCOPES["readonly"]
    assert "https://www.googleapis.com/auth/forms.body" in garc_core.PROFILE_SCOPES["writer"]
    assert "https://www.googleapis.com/auth/forms.body" in garc_core.PROFILE_SCOPES["backoffice_agent"]


def test_forms_probe_404_means_api_enabled():
    svc = MagicMock()
    svc.forms.return_value.get.return_value.execute.side_effect = Exception(
        "HttpError 404 Requested entity was not found"
    )
    assert setup.probe_forms_api(svc) == "✅"
    svc.forms.return_value.get.assert_called_once_with(formId=setup.FORMS_PROBE_ID)


def test_forms_probe_disabled_api_is_failure():
    svc = MagicMock()
    svc.forms.return_value.get.return_value.execute.side_effect = Exception(
        "HttpError 403 accessNotConfigured Forms API has not been used in project 1 before or it is disabled"
    )
    result = setup.probe_forms_api(svc)
    assert result.startswith("❌")
    assert "disabled" in result.lower() or "accessNotConfigured" in result


def test_check_api_access_reports_forms(monkeypatch, capsys):
    def fake_build(name, version, scopes=None):
        svc = MagicMock()
        if name == "forms":
            svc.forms.return_value.get.return_value.execute.side_effect = Exception(
                "HttpError 404 not found"
            )
        elif name == "drive":
            svc.about.return_value.get.return_value.execute.return_value = {"user": {}}
        elif name == "gmail":
            svc.users.return_value.getProfile.return_value.execute.return_value = {}
        elif name == "calendar":
            svc.calendarList.return_value.list.return_value.execute.return_value = {}
        elif name == "tasks":
            svc.tasklists.return_value.list.return_value.execute.return_value = {}
        elif name == "people":
            svc.people.return_value.connections.return_value.list.return_value.execute.return_value = {}
        return svc

    monkeypatch.setattr(setup, "build_service", fake_build)
    results = setup.check_api_access({})
    assert results["Forms API"] == "✅"
    assert "forms.googleapis.com" in capsys.readouterr().out
