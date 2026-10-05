import json
import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from synctools import utils

script_dir = Path(os.path.dirname(os.path.realpath(__file__)))


def load_testdata(filename: str):
    full_path = Path(script_dir / "testdata" / filename)
    with open(full_path) as file:
        data = json.loads(file.read())

    return data


def test_identity():
    dict_b = load_testdata("dict_b.json")

    diff = utils.dict_diff(dict_b, dict_b)

    assert diff == {}


def test_list_of_dicts_diff():
    dict_c = load_testdata("dict_c.json")
    dict_d = load_testdata("dict_d.json")

    diff = utils.dict_diff(dict_c, dict_d)

    assert diff["options"][0]["id"] == "1"


def test_dict_diff():
    with open(script_dir / "testdata" / "dict_a.json", "r") as file:
        dict_a = json.loads(file.read())

    with open(script_dir / "testdata" / "dict_b.json", "r") as file:
        dict_b = json.loads(file.read())

    diff = utils.dict_diff(dict_a, dict_b)

    assert diff


def test_validate_dict():
    template_a = load_testdata("template_a.json")

    utils.validate_dict(template_a)

    template_b = load_testdata("template_b.json")

    # TODO: Probably a better way to do this
    empty_value_exception_thrown = False
    try:
        utils.validate_dict(template_b)
    except utils.EmptyValueException:
        empty_value_exception_thrown = True

    assert empty_value_exception_thrown

    template_c = load_testdata("template_c.json")

    mixed_types_exception_thrown = False
    try:
        utils.validate_dict(template_c)
    except utils.MixedTypesException:
        mixed_types_exception_thrown = True

    assert mixed_types_exception_thrown


def test_complete_dicts():
    dict_e = load_testdata("dict_e.json")
    template_a = load_testdata("template_a.json")

    completed_dict = utils.complete_dicts(template_a, [dict_e])[0]

    # Check completion
    assert completed_dict["custom_fields"]["abc"] == []
    # Check type coercion
    assert completed_dict["postal_address"]["street_number"] == "22"


def test_create_schema_dict():
    dict_list = [
        {"Id": 1, "Name": "Oslo", "Phone": None, "Fax": None, "Email": None},
        {"Id": 2, "Name": "Stavanger", "Phone": None, "Fax": None, "Email": None},
        {"Id": 3, "Name": "Bergen", "Phone": None, "Fax": None, "Email": None},
    ]

    expected_result = {"Id": 3, "Name": "Bergen", "Phone": "", "Fax": "", "Email": ""}

    result = utils.create_schema_dict(dict_list)

    assert result == expected_result


ENV_TEXT = "# comment\n\n  FOO = \"bar\"  \nBAZ='q'\nNOEQ\nKEEP=new\n"


@pytest.fixture
def env(monkeypatch):
    for key in ("FOO", "BAZ", "NOEQ", "KEEP"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("KEEP", "old")


def assert_env_loaded():
    assert os.environ["FOO"] == "bar"
    assert os.environ["BAZ"] == "q"
    assert "NOEQ" not in os.environ
    assert os.environ["KEEP"] == "old"


def test_load_env_file(env, tmp_path):
    envfile = tmp_path / ".env"
    envfile.write_text(ENV_TEXT)

    utils.load_env_file(envfile)

    assert_env_loaded()


def test_load_env_file_missing(env, tmp_path):
    utils.load_env_file(tmp_path / "missing.env")

    assert "FOO" not in os.environ


def test_load_env_tpl(env):
    with mock.patch.object(subprocess, "run", return_value=mock.Mock(stdout=ENV_TEXT)) as run:
        utils.load_env_tpl("app.env.tpl")

    assert run.call_args.args[0] == ["op", "inject", "-i", "app.env.tpl"]
    assert_env_loaded()


def test_load_env(env, tmp_path):
    envfile = tmp_path / ".env"
    envfile.write_text(ENV_TEXT)

    assert utils.load_env(["FOO", "KEEP"], str(envfile)) == {"FOO": "bar", "KEEP": "old"}


def test_load_env_missing_file(env, tmp_path):
    with pytest.raises(FileNotFoundError):
        utils.load_env(["FOO"], str(tmp_path / "missing.env"))


def test_load_env_missing_or_empty_var(env, monkeypatch):
    with pytest.raises(EnvironmentError):
        utils.load_env(["FOO"])

    monkeypatch.setenv("FOO", "")
    with pytest.raises(EnvironmentError):
        utils.load_env(["FOO"])
