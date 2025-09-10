import json
import os
from pathlib import Path


import synctools.utils as utils

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

    assert diff == {}

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

    assert True
