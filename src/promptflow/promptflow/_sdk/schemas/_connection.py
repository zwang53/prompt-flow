# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import copy

from marshmallow import fields, pre_dump

from promptflow._sdk._constants import ConnectionType
from promptflow._sdk.schemas._base import YamlFileSchema
from promptflow._sdk.schemas._fields import StringTransformedEnum
from promptflow._utils.utils import camel_to_snake


def _casting_type(typ):
    type_dict = {
        ConnectionType.AZURE_OPEN_AI: "azure_open_ai",
        ConnectionType.OPEN_AI: "open_ai",
    }

    if typ in type_dict:
        return type_dict.get(typ)
    return camel_to_snake(typ)


class ConnectionSchema(YamlFileSchema):
    name = fields.Str(attribute="name")
    module = fields.Str(dump_default="promptflow.connections")
    created_date = fields.Str(dump_only=True)
    last_modified_date = fields.Str(dump_only=True)
    expiry_time = fields.Str(dump_only=True)

    @pre_dump
    def _pre_dump(self, data, **kwargs):
        from promptflow._sdk.entities._connection import _Connection

        if not isinstance(data, _Connection):
            return data
        # Update the type replica of the connection object to match schema
        copied = copy.deepcopy(data)
        copied.type = camel_to_snake(copied.type)
        return copied


class AzureOpenAIConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(allowed_values="azure_open_ai", required=True)
    api_key = fields.Str(required=True)
    api_base = fields.Str(required=True)
    api_type = fields.Str(dump_default="azure")
    api_version = fields.Str(dump_default="2023-07-01-preview")


class OpenAIConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(allowed_values="open_ai", required=True)
    api_key = fields.Str(required=True)
    organization = fields.Str()


class EmbeddingStoreConnectionSchema(ConnectionSchema):
    module = fields.Str(dump_default="promptflow_vectordb.connections")
    api_key = fields.Str(required=True)
    api_base = fields.Str(required=True)


class QdrantConnectionSchema(EmbeddingStoreConnectionSchema):
    type = StringTransformedEnum(allowed_values=camel_to_snake(ConnectionType.QDRANT), required=True)


class WeaviateConnectionSchema(EmbeddingStoreConnectionSchema):
    type = StringTransformedEnum(allowed_values=camel_to_snake(ConnectionType.WEAVIATE), required=True)


class CognitiveSearchConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(
        allowed_values=camel_to_snake(ConnectionType.COGNITIVE_SEARCH),
        required=True,
    )
    api_key = fields.Str(required=True)
    api_base = fields.Str(required=True)
    api_version = fields.Str(dump_default="2023-07-01-Preview")


class SerpConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(allowed_values=camel_to_snake(ConnectionType.SERP), required=True)
    api_key = fields.Str(required=True)


class AzureContentSafetyConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(
        allowed_values=camel_to_snake(ConnectionType.AZURE_CONTENT_SAFETY),
        required=True,
    )
    api_key = fields.Str(required=True)
    endpoint = fields.Str(required=True)
    api_version = fields.Str(dump_default="2023-04-30-preview")
    api_type = fields.Str(dump_default="Content Safety")


class FormRecognizerConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(
        allowed_values=camel_to_snake(ConnectionType.FORM_RECOGNIZER),
        required=True,
    )
    api_key = fields.Str(required=True)
    endpoint = fields.Str(required=True)
    api_version = fields.Str(dump_default="2023-07-31")
    api_type = fields.Str(dump_default="Form Recognizer")


class CustomConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(allowed_values=camel_to_snake(ConnectionType.CUSTOM), required=True)
    configs = fields.Dict(keys=fields.Str(), values=fields.Str())
    # Secrets is a must-have field for CustomConnection
    secrets = fields.Dict(keys=fields.Str(), values=fields.Str(), required=True)
