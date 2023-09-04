# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
from contextvars import ContextVar
from datetime import datetime
from types import GeneratorType
from typing import Any, Dict, List, Mapping, Optional, Union

from promptflow._core.log_manager import NodeLogManager
from promptflow._core.thread_local_singleton import ThreadLocalSingleton
from promptflow._utils.dataclass_serializer import serialize
from promptflow._utils.exception_utils import ExceptionPresenter
from promptflow._utils.logger_utils import flow_logger
from promptflow.contracts.run_info import FlowRunInfo, RunInfo, Status
from promptflow.contracts.run_mode import RunMode
from promptflow.contracts.tool import ConnectionType
from promptflow.exceptions import ErrorTarget, UserErrorException, ValidationException
from promptflow.storage._run_storage import DummyRunStorage
from promptflow.storage import AbstractRunStorage


class RunTracker(ThreadLocalSingleton):
    RUN_CONTEXT_NAME = "CurrentRun"
    CONTEXT_VAR_NAME = "RunTracker"
    context_var = ContextVar(CONTEXT_VAR_NAME, default=None)

    @staticmethod
    def init_dummy() -> "RunTracker":
        return RunTracker(DummyRunStorage())

    def __init__(self, run_storage: AbstractRunStorage, run_mode: RunMode = RunMode.Test, node_log_manager=None):
        self._node_runs: Dict[str, RunInfo] = {}
        self._flow_runs: Dict[str, FlowRunInfo] = {}
        self._current_run_id = ""
        self._run_context = ContextVar(self.RUN_CONTEXT_NAME, default="")
        self._storage = run_storage
        self._debug = True  # TODO: Make this configurable
        self.node_log_manager = node_log_manager or NodeLogManager()
        self._has_failed_root_run = False
        self._run_mode = run_mode
        self._allow_generator_types = False

    @property
    def allow_generator_types(self):
        return self._allow_generator_types

    @allow_generator_types.setter
    def allow_generator_types(self, value: bool):
        self._allow_generator_types = value

    @property
    def node_run_list(self):
        # Add list() to make node_run_list a new list object,
        # therefore avoid iterating over a dictionary, which might be updated by another thread.
        return list(self._node_runs.values())

    @property
    def flow_run_list(self):
        # Add list() to make flow_run_list a new list object,
        # therefore avoid iterating over a dictionary, which might be updated by another thread.
        return list(self._flow_runs.values())

    def set_current_run_in_context(self, run_id: str):
        self._run_context.set(run_id)

    def get_current_run_in_context(self) -> str:
        return self._run_context.get()

    def start_flow_run(
        self,
        flow_id,
        root_run_id,
        run_id,
        parent_run_id="",
        inputs=None,
        index=None,
        variant_id="",
    ) -> FlowRunInfo:
        """Create a flow run and save to run storage on demand."""
        run_info = FlowRunInfo(
            run_id=run_id,
            status=Status.Running,
            error=None,
            inputs=inputs,
            output=None,
            metrics=None,
            request=None,
            parent_run_id=parent_run_id,
            root_run_id=root_run_id,
            source_run_id=None,
            flow_id=flow_id,
            start_time=datetime.utcnow(),
            end_time=None,
            index=index,
            variant_id=variant_id,
        )
        self.persist_flow_run(run_info)
        self._flow_runs[run_id] = run_info
        self._current_run_id = run_id
        return run_info

    def start_node_run(
        self,
        node,
        flow_run_id,
        parent_run_id,
        run_id,
        index,
    ):
        run_info = RunInfo(
            node=node,
            run_id=run_id,
            flow_run_id=flow_run_id,
            status=Status.Running,
            inputs=None,
            output=None,
            metrics=None,
            error=None,
            parent_run_id=parent_run_id,
            start_time=datetime.utcnow(),
            end_time=None,
        )
        self._node_runs[run_id] = run_info
        self._current_run_id = run_id
        self.set_current_run_in_context(run_id)
        self.node_log_manager.set_node_context(run_id, node, index)
        return run_info

    def _flow_run_postprocess(self, run_info: FlowRunInfo, output, ex: Optional[Exception]):
        if output:
            try:
                self._assert_flow_output_serializable(output)
            except Exception as e:
                output, ex = None, e
        self._common_postprocess(run_info, output, ex)

    def _update_flow_run_info_with_node_runs(self, run_info):
        run_id = run_info.run_id
        run_info.api_calls = self._collect_traces_from_nodes(run_id)
        child_run_infos = self.collect_child_node_runs(run_id)
        run_info.system_metrics = run_info.system_metrics or {}
        run_info.system_metrics.update(self.collect_metrics(child_run_infos, self.OPENAI_AGGREGATE_METRICS))

    def _node_run_postprocess(self, run_info: RunInfo, output, ex: Optional[Exception]):
        run_id = run_info.run_id
        self.set_openai_metrics(run_id)
        logs = self.node_log_manager.get_logs(run_id)
        run_info.logs = logs
        self.node_log_manager.clear_node_context(run_id)

        if run_info.inputs:
            run_info.inputs = self._ensure_inputs_is_json_serializable(run_info.inputs, run_info.node)
        if output is not None:
            msg = f"Output of {run_info.node} is not json serializable, use str to store it."
            output = self._ensure_serializable_value(output, msg)
        self._common_postprocess(run_info, output, ex)

    def _common_postprocess(self, run_info, output, ex):
        if output is not None:
            #  Duplicated fields for backward compatibility.
            run_info.result = output
            run_info.output = output
        if ex is not None:
            self._enrich_run_info_with_exception(run_info=run_info, ex=ex)
        else:
            run_info.status = Status.Completed
        run_info.end_time = datetime.utcnow()
        if not isinstance(run_info.start_time, datetime):
            flow_logger.warning(
                f"Run start time {run_info.start_time} for {run_info.run_id} is not a datetime object, "
                f"got {run_info.start_time}, type={type(run_info.start_time)}."
            )
        else:
            duration = (run_info.end_time - run_info.start_time).total_seconds()
            run_info.system_metrics = run_info.system_metrics or {}
            run_info.system_metrics["duration"] = duration

    def end_run(
        self,
        run_id: str,
        *,
        result: Optional[dict] = None,
        ex: Optional[Exception] = None,
        traces: Optional[List] = None,
    ):
        run_info = self._flow_runs.get(run_id) or self._node_runs.get(run_id)
        if run_info is None:
            raise RunRecordNotFound(message=f"Run {run_id} not found", target=ErrorTarget.RUN_TRACKER)
        if isinstance(run_info, FlowRunInfo):
            self._flow_run_postprocess(run_info, result, ex)
        elif isinstance(run_info, RunInfo):
            run_info.api_calls = traces
            self._node_run_postprocess(run_info, result, ex)
        return run_info

    def _ensure_serializable_value(self, val, warning_msg: Optional[str] = None):
        if ConnectionType.is_connection_value(val):
            return ConnectionType.serialize_conn(val)
        if self.allow_generator_types and isinstance(val, GeneratorType):
            return str(val)
        try:
            json.dumps(val)
            return val
        except Exception:
            if not warning_msg:
                raise
            flow_logger.warning(warning_msg)
            return repr(val)

    def _ensure_inputs_is_json_serializable(self, inputs: dict, node_name: str) -> dict:
        return {
            k: self._ensure_serializable_value(
                v, f"Input '{k}' of {node_name} is not json serializable, use str to store it."
            )
            for k, v in inputs.items()
        }

    def _assert_flow_output_serializable(self, output: Any) -> Any:
        try:
            return {k: self._ensure_serializable_value(v) for k, v in output.items()}
        except Exception as e:
            # If it is flow output not node output, raise an exception.
            raise UserErrorException(
                f"Flow output must be json serializable, dump json failed: {e}",
                target=ErrorTarget.FLOW_EXECUTOR,
            ) from e

    def _enrich_run_info_with_exception(self, run_info: Union[RunInfo, FlowRunInfo], ex: Exception):
        """Update exception details into run info."""
        run_info.error = ExceptionPresenter.create(ex).to_dict(include_debug_info=self._debug)
        run_info.status = Status.Failed

    def collect_all_run_infos_as_dicts(self) -> Mapping[str, List[Mapping[str, Any]]]:
        flow_runs = self.flow_run_list
        node_runs = self.node_run_list
        return {
            "flow_runs": [serialize(run) for run in flow_runs],
            "node_runs": [serialize(run) for run in node_runs],
        }

    def collect_node_runs(self, flow_run_id: Optional[str] = None) -> List[RunInfo]:
        """If flow_run_id is None, return all node runs."""
        if flow_run_id:
            return [run_info for run_info in self.node_run_list if run_info.flow_run_id == flow_run_id]

        return [run_info for run_info in self.node_run_list]

    def collect_child_node_runs(self, parent_run_id: str) -> List[RunInfo]:
        return [run_info for run_info in self.node_run_list if run_info.parent_run_id == parent_run_id]

    def ensure_run_info(self, run_id: str) -> Union[RunInfo, FlowRunInfo]:
        run_info = self._node_runs.get(run_id) or self._flow_runs.get(run_id)
        if run_info is None:
            raise RunRecordNotFound(
                message=f"Run {run_id} not found when tracking inputs", target=ErrorTarget.RUN_TRACKER
            )
        return run_info

    def set_inputs(self, run_id: str, inputs: Mapping[str, Any]):
        run_info = self.ensure_run_info(run_id)
        run_info.inputs = inputs

    def set_openai_metrics(self, run_id: str):
        # TODO: Provide a common implementation for different internal metrics
        run_info = self.ensure_run_info(run_id)
        calls = run_info.api_calls or []
        total_metrics = {}
        for call in calls:
            metrics = self._get_openai_metrics(call)
            self._merge_metrics_dict(total_metrics, metrics)
        run_info.system_metrics = run_info.system_metrics or {}
        run_info.system_metrics.update(total_metrics)

    def _get_openai_metrics(self, api_call: dict):
        total_metrics = {}
        if self._need_collect_metrics(api_call):
            metrics = api_call["output"]["usage"]
            self._merge_metrics_dict(total_metrics, metrics)

        children = api_call.get("children")
        if children is not None:
            for child in children:
                child_metrics = self._get_openai_metrics(child)
                self._merge_metrics_dict(total_metrics, child_metrics)

        return total_metrics

    def _need_collect_metrics(self, api_call: dict):
        if api_call.get("type") != "LLM":
            return False
        output = api_call.get("output")
        if not isinstance(output, dict):
            return False
        usage = output.get("usage")
        if not isinstance(usage, dict):
            return False
        return True

    def _merge_metrics_dict(self, metrics: dict, metrics_to_merge: dict):
        for k, v in metrics_to_merge.items():
            metrics[k] = metrics.get(k, 0) + v

    def _collect_traces_from_nodes(self, run_id):
        child_run_infos = self.collect_child_node_runs(run_id)
        traces = []
        for node_run_info in child_run_infos:
            traces.extend(node_run_info.api_calls)
        return traces

    OPENAI_AGGREGATE_METRICS = ["total_tokens"]

    def collect_metrics(self, run_infos: List[RunInfo], aggregate_metrics: List[str] = []):
        if not aggregate_metrics:
            return {}
        total_metrics = {}
        for run_info in run_infos:
            if not run_info.system_metrics:
                continue
            for metric in aggregate_metrics:
                total_metrics[metric] = total_metrics.get(metric, 0) + run_info.system_metrics.get(metric, 0)
        return total_metrics

    def get_run(self, run_id):
        return self._node_runs.get(run_id) or self._flow_runs.get(run_id)

    def persist_node_run(self, run_info: RunInfo):
        self._storage.persist_node_run(run_info)

    def persist_flow_run(self, run_info: FlowRunInfo):
        self._storage.persist_flow_run(run_info)

    def get_status_summary(self, run_id: str):
        node_run_infos = self.collect_node_runs(run_id)
        status_summary = {}
        line_status = {}
        for run_info in node_run_infos:
            if run_info.index is not None:
                if run_info.index not in line_status.keys():
                    line_status[run_info.index] = True

                line_status[run_info.index] = line_status[run_info.index] and run_info.status == Status.Completed

                node_name = run_info.node
                if "__pf__.nodes." + node_name + ".completed" not in status_summary.keys():
                    status_summary["__pf__.nodes." + node_name + ".completed"] = 0
                    status_summary["__pf__.nodes." + node_name + ".failed"] = 0

                # Only consider Completed and Failed status, because the UX only support two status.
                if run_info.status in (Status.Completed, Status.Failed):
                    status_summary["__pf__.nodes." + node_name + f".{run_info.status.value}".lower()] += 1

            # For reduce node, the index is None.
            else:
                node_name = run_info.node
                status_summary["__pf__.nodes." + node_name + ".completed"] = (
                    1 if run_info.status == Status.Completed else 0
                )

        status_summary["__pf__.lines.completed"] = sum(line_status.values())
        status_summary["__pf__.lines.failed"] = len(line_status) - status_summary["__pf__.lines.completed"]
        return status_summary

    def persist_status_summary(self, status_summary: Dict[str, int], run_id: str):
        self._storage.persist_status_summary(status_summary, run_id)


class RunRecordNotFound(ValidationException):
    pass
