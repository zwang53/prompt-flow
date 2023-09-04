# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import shutil
import tempfile
from pathlib import Path

import mock
import pandas as pd
import pytest

from promptflow._cli._utils import (
    _build_sorted_column_widths_tuple_list,
    _calculate_column_widths,
    list_of_dict_to_nested_dict,
)
from promptflow._sdk._errors import GenerateFlowToolsJsonError
from promptflow._sdk._utils import (
    decrypt_secret_value,
    encrypt_secret_value,
    generate_flow_tools_json,
    resolve_connections_environment_variable_reference,
    snake_to_camel,
)

TEST_ROOT = Path(__file__).parent.parent.parent
CONNECTION_ROOT = TEST_ROOT / "test_configs/connections"


@pytest.mark.unittest
class TestUtils:
    def test_encrypt_decrypt_value(self):
        test_value = "test"
        encrypted = encrypt_secret_value(test_value)
        assert decrypt_secret_value("mock", encrypted) == test_value

    def test_snake_to_camel(self):
        assert snake_to_camel("test_snake_case") == "TestSnakeCase"
        assert snake_to_camel("TestSnakeCase") == "TestSnakeCase"

    def test_sqlite_retry(self, capfd) -> None:
        from sqlalchemy.exc import OperationalError

        from promptflow._sdk._orm.retry import sqlite_retry

        @sqlite_retry
        def mock_sqlite_op() -> None:
            print("sqlite op...")
            raise OperationalError("statement", "params", "orig")

        # it will finally raise an OperationalError
        with pytest.raises(OperationalError):
            mock_sqlite_op()
        # assert function execution time from stdout
        out, _ = capfd.readouterr()
        assert out.count("sqlite op...") == 3

    def test_resolve_connections_environment_variable_reference(self):
        connections = {
            "test_connection": {
                "type": "AzureOpenAIConnection",
                "value": {
                    "api_key": "${env:AZURE_OPENAI.API_KEY}",
                    "api_base": "${env:AZURE_OPENAI_API_BASE}",
                },
            },
            "test_custom_connection": {
                "type": "CustomConnection",
                "value": {"key": "${env:CUSTOM_KEY}", "key2": "value2"},
            },
        }
        with mock.patch.dict(
            os.environ, {"AZURE_OPENAI.API_KEY": "KEY", "AZURE_OPENAI_API_BASE": "BASE", "CUSTOM_KEY": "CUSTOM_VALUE"}
        ):
            resolve_connections_environment_variable_reference(connections)
        assert connections["test_connection"]["value"]["api_key"] == "KEY"
        assert connections["test_connection"]["value"]["api_base"] == "BASE"
        assert connections["test_custom_connection"]["value"]["key"] == "CUSTOM_VALUE"

    def test_generate_flow_tools_json(self) -> None:
        # call twice to ensure system path won't be affected during generation
        for _ in range(2):
            flow_src_path = "./tests/test_configs/flows/flow_with_sys_inject"
            with tempfile.TemporaryDirectory() as temp_dir:
                flow_dst_path = os.path.join(temp_dir, "flow_with_sys_inject")
                shutil.copytree(flow_src_path, flow_dst_path)
                flow_tools_json = generate_flow_tools_json(flow_dst_path, dump=False)
                groundtruth = {
                    "hello.py": {
                        "type": "python",
                        "inputs": {
                            "input1": {
                                "type": [
                                    "string",
                                ],
                            },
                        },
                        "source": "hello.py",
                        "function": "my_python_tool",
                    }
                }
                assert flow_tools_json["code"] == groundtruth

    def test_generate_flow_tools_json_expecting_fail(self) -> None:
        flow_path = "./tests/test_configs/flows/flow_with_invalid_import"
        with pytest.raises(GenerateFlowToolsJsonError) as e:
            generate_flow_tools_json(flow_path, dump=False)
        assert "Generate meta failed, detail error(s):" in str(e.value)
        # raise_error = False
        flow_tools_json = generate_flow_tools_json(flow_path, dump=False, raise_error=False)
        assert len(flow_tools_json["code"]) == 0


@pytest.mark.unittest
class TestCLIUtils:
    def test_list_of_dict_to_nested_dict(self):
        test_list = [{"node1.connection": "a"}, {"node2.deploy_name": "b"}]
        result = list_of_dict_to_nested_dict(test_list)
        assert result == {"node1": {"connection": "a"}, "node2": {"deploy_name": "b"}}
        test_list = [{"node1.connection": "a"}, {"node1.deploy_name": "b"}]
        result = list_of_dict_to_nested_dict(test_list)
        assert result == {"node1": {"connection": "a", "deploy_name": "b"}}

    def test_build_sorted_column_widths_tuple_list(self) -> None:
        columns = ["col1", "col2", "col3"]
        values1 = {"col1": 1, "col2": 4, "col3": 3}
        values2 = {"col1": 3, "col2": 3, "col3": 1}
        margins = {"col1": 1, "col2": 2, "col3": 2}
        # sort by (max(values1, values2) + margins)
        res = _build_sorted_column_widths_tuple_list(columns, values1, values2, margins)
        assert res == [("col2", 6), ("col3", 5), ("col1", 4)]

    def test_calculate_column_widths(self) -> None:
        data = [
            {
                "inputs.url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g",
                "inputs.answer": "Channel",
                "inputs.evidence": "Url",
                "outputs.category": "Channel",
                "outputs.evidence": "URL",
            },
            {
                "inputs.url": "https://arxiv.org/abs/2307.04767",
                "inputs.answer": "Academic",
                "inputs.evidence": "Text content",
                "outputs.category": "Academic",
                "outputs.evidence": "Text content",
            },
            {
                "inputs.url": "https://play.google.com/store/apps/details?id=com.twitter.android",
                "inputs.answer": "App",
                "inputs.evidence": "Both",
                "outputs.category": "App",
                "outputs.evidence": "Both",
            },
        ]
        df = pd.DataFrame(data)
        terminal_width = 120
        res = _calculate_column_widths(df, terminal_width)
        assert res == [4, 23, 13, 15, 15, 15]
