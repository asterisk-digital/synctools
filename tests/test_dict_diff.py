import json
import os
from pathlib import Path


import synctools.utils as utils

script_dir = Path(os.path.dirname(os.path.realpath(__file__)))

def test_dict_diff():
    with open(script_dir / "testdata" / "dict_a.json", "r") as file:
        dict_a = json.loads(file.read())

    with open(script_dir / "testdata" / "dict_b.json", "r") as file:
        dict_b = json.loads(file.read())

    diff = utils.dict_diff(dict_a, dict_b)

    assert diff

    assert True
