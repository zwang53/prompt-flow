import pytest

from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor
from promptflow.executor._result import BulkResult, LineResult

from ..utils import get_flow_sample_inputs, get_yaml_file

SAMPLE_FLOW_WITH_LANGCHAIN_TRACES = "flow_with_langchain_traces"


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
@pytest.mark.e2etest
class TestLangchain:
    def get_line_inputs(self, flow_folder=""):
        if flow_folder:
            inputs = self.get_bulk_inputs(flow_folder)
            return inputs[0]
        return {
            "url": "https://www.apple.com/shop/buy-iphone/iphone-14",
            "text": "some_text",
        }

    def get_bulk_inputs(self, nlinee=4, flow_folder=""):
        if flow_folder:
            inputs = get_flow_sample_inputs(flow_folder)
            if isinstance(inputs, list) and len(inputs) > 0:
                return inputs
            elif isinstance(inputs, dict):
                return [inputs]
            else:
                raise Exception(f"Invalid type of bulk input: {inputs}")
        return [self.get_line_inputs() for _ in range(nlinee)]

    def test_executor_exec_bulk_with_langchain(self, dev_connections):
        flow_folder = SAMPLE_FLOW_WITH_LANGCHAIN_TRACES
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, raise_ex=True)
        bulk_inputs = self.get_bulk_inputs(flow_folder=flow_folder)
        bulk_results = executor.exec_bulk(bulk_inputs)
        assert isinstance(bulk_results, BulkResult)
        assert len(bulk_results.outputs) == len(bulk_inputs)
        for i, line_result in enumerate(bulk_results.line_results):
            assert isinstance(line_result, LineResult)
            assert line_result.run_info.status == Status.Completed
        # TODO: It is not stable to collect openai metrics for now, need to fix it later
        # openai_metrics = bulk_results.get_openai_metrics()
        # assert "total_tokens" in openai_metrics
        # assert openai_metrics["total_tokens"] > 0
