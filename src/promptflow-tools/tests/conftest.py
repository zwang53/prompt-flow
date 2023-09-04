import json
import os
import sys
from pathlib import Path

import pytest
from pytest_mock import MockerFixture  # noqa: E402
# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import ConnectionManager
from promptflow.tools.aoai import AzureOpenAI

PROMOTFLOW_ROOT = Path(__file__).absolute().parents[1]
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
root_str = str(PROMOTFLOW_ROOT.resolve().absolute())
if root_str not in sys.path:
    sys.path.insert(0, root_str)


# connection
@pytest.fixture(autouse=True)
def use_secrets_config_file(mocker: MockerFixture):
    mocker.patch.dict(os.environ, {"PROMPTFLOW_CONNECTIONS": CONNECTION_FILE})


@pytest.fixture
def azure_open_ai_connection():
    return ConnectionManager().get("azure_open_ai_connection")


@pytest.fixture
def aoai_provider(azure_open_ai_connection) -> AzureOpenAI:
    aoai_provider = AzureOpenAI(azure_open_ai_connection)
    return aoai_provider


@pytest.fixture
def open_ai_connection():
    return ConnectionManager().get("open_ai_connection")


@pytest.fixture
def serp_connection():
    return ConnectionManager().get("serp_connection")


@pytest.fixture(autouse=True)
def skip_if_no_key(request, mocker):
    mocker.patch.dict(os.environ, {"PROMPTFLOW_CONNECTIONS": CONNECTION_FILE})
    if request.node.get_closest_marker('skip_if_no_key'):
        conn_name = request.node.get_closest_marker('skip_if_no_key').args[0]
        connection = request.getfixturevalue(conn_name)
        # if dummy placeholder key, skip.
        if "-api-key" in connection.api_key:
            pytest.skip('skipped because no key')


# example prompts
@pytest.fixture
def example_prompt_template() -> str:
    with open(PROMOTFLOW_ROOT / "tests/test_configs/prompt_templates/marketing_writer/prompt.jinja2") as f:
        prompt_template = f.read()
    return prompt_template


@pytest.fixture
def chat_history() -> list:
    with open(PROMOTFLOW_ROOT / "tests/test_configs/prompt_templates/marketing_writer/history.json") as f:
        history = json.load(f)
    return history


@pytest.fixture
def example_prompt_template_with_function() -> str:
    with open(PROMOTFLOW_ROOT / "tests/test_configs/prompt_templates/prompt_with_function.jinja2") as f:
        prompt_template = f.read()
    return prompt_template


# functions
@pytest.fixture
def functions():
    return [
        {
            "name": "get_current_weather",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        }
    ]
