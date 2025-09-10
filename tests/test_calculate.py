import os
import json
from pathlib import Path

from python_template.App import App

script_dir = Path(os.path.dirname(os.path.realpath(__file__)))
testdata_dir = Path(script_dir, "testdata")
origin_testdata = json.loads(open(testdata_dir / "origin_data.json", "r").read())
target_testdata = json.loads(open(testdata_dir / "target_data.json", "r").read())


def test_calculate_empty():
    changelist = App.calculate([], [])

    assert changelist["newlist"] == []
    assert changelist["updatelist"] == {}
    assert changelist["deletelist"] == {}


def test_calculate_empty_target():
    changelist = App.calculate(origin_testdata, [])

    newlist = changelist["newlist"]
    assert len(newlist) == 3
    assert newlist[0]["Id"] == 1
    assert newlist[0]["Name"] == "stuff1"

    assert changelist["updatelist"] == {}
    assert changelist["deletelist"] == {}


def test_calculate_diff():
    changelist = App.calculate(origin_testdata, target_testdata)

    newlist = changelist["newlist"]
    assert len(newlist) == 1
    assert newlist[0]["Id"] == 3
    assert newlist[0]["Name"] == "stuff3"

    updatelist = changelist["updatelist"]
    assert len(updatelist) == 1
    assert updatelist[2]["Name"] == "stuff2"

    deletelist = changelist["deletelist"]
    assert len(deletelist) == 1
    assert deletelist[4]["Name"] == "stuff4"
