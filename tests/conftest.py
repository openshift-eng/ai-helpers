import importlib.util
import sys
import tempfile
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    tmp = Path(tempfile.mkdtemp()).resolve()
    yield tmp
    shutil.rmtree(tmp)


def _load_rule_module(filename):
    rule_path = Path(__file__).parent.parent / ".skillsaw" / filename
    spec = importlib.util.spec_from_file_location(filename.replace(".", "_"), rule_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def owners_rule():
    mod = _load_rule_module("owners_rule.py")
    return mod.PluginOwnersRequiredRule


@pytest.fixture
def opencode_color_rule():
    mod = _load_rule_module("opencode_color_rule.py")
    return mod.OpencodeAgentColorRule
