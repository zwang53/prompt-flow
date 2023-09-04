# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from promptflow._core.metric_logger import log_metric

# flake8: noqa
from promptflow._core.tool import ToolProvider, tool

# control plane sdk functions
from ._sdk._pf_client import PFClient
from ._version import VERSION

# backward compatibility
log_flow_metric = log_metric

__version__ = VERSION

__all__ = [
    "PFClient",
    "log_metric",
    "ToolProvider",
    "tool",
]
