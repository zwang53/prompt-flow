import json
import os

import pytest

from promptflow._core.operation_context import OperationContext


@pytest.mark.usefixtures("flow_serving_client", "setup_local_connection")
@pytest.mark.e2etest
def test_swagger(flow_serving_client):
    swagger_dict = json.loads(flow_serving_client.get("/swagger.json").data.decode())
    assert swagger_dict == {
        "components": {"securitySchemes": {"bearerAuth": {"scheme": "bearer", "type": "http"}}},
        "info": {
            "title": "Promptflow[basic-with-connection] API",
            "version": "1.0.0",
            "x-flow-name": "basic-with-connection",
        },
        "openapi": "3.0.0",
        "paths": {
            "/score": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "example": {"text": "Hello World!"},
                                "schema": {
                                    "properties": {"text": {"type": "string"}},
                                    "required": ["text"],
                                    "type": "object",
                                },
                            }
                        },
                        "description": "promptflow input data",
                        "required": True,
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"properties": {"output_prompt": {"type": "string"}}, "type": "object"}
                                }
                            },
                            "description": "successful operation",
                        },
                        "400": {"description": "Invalid input"},
                        "default": {"description": "unexpected error"},
                    },
                    "summary": "run promptflow: basic-with-connection with an given input",
                }
            }
        },
        "security": [{"bearerAuth": []}],
    }


@pytest.mark.usefixtures("flow_serving_client", "setup_local_connection")
@pytest.mark.e2etest
def test_user_agent(flow_serving_client):
    operation_context = OperationContext.get_instance()
    assert "test-user-agent" in operation_context.get_user_agent()
    assert "promptflow-local-serving" in operation_context.get_user_agent()


@pytest.mark.usefixtures("flow_serving_client", "setup_local_connection")
@pytest.mark.e2etest
def test_serving_api(flow_serving_client):
    response = flow_serving_client.get("/health")
    assert b'{"status":"Healthy","version":"0.0.1"}' in response.data
    response = flow_serving_client.post("/score", data=json.dumps({"text": "hi"}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    assert "output_prompt" in json.loads(response.data.decode())
    # Assert environment variable resolved
    assert os.environ["API_TYPE"] == "azure"


@pytest.mark.usefixtures("evaluation_flow_serving_client", "setup_local_connection")
@pytest.mark.e2etest
def test_evaluation_flow_serving_api(evaluation_flow_serving_client):
    response = evaluation_flow_serving_client.post("/score", data=json.dumps({"url": "https://www.microsoft.com/"}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    assert "category" in json.loads(response.data.decode())
