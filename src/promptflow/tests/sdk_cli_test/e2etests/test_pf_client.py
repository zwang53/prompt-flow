# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import pytest

from promptflow import PFClient
from promptflow._core.operation_context import OperationContext


@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestPFClient:
    def test_pf_client_user_agent(self):
        PFClient()
        assert "promptflow-sdk" in OperationContext.get_instance().get_user_agent()
