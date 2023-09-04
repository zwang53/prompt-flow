# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from datetime import datetime
from typing import List

from promptflow._sdk._constants import MAX_LIST_CLI_RESULTS
from promptflow._sdk._orm import Connection as ORMConnection
from promptflow._sdk._utils import safe_parse_object_list
from promptflow._sdk.entities._connection import _Connection


class ConnectionOperations:
    """ConnectionOperations."""

    def list(
        self,
        max_results: int = MAX_LIST_CLI_RESULTS,
        all_results: bool = False,
    ) -> List[_Connection]:
        """List connections.

        :param max_results: Max number of results to return.
        :type max_results: int
        :param all_results: Return all results.
        :type all_results: bool
        :return: List of run objects.
        :rtype: List[~promptflow.sdk.entities._connection._Connection]
        """
        orm_connections = ORMConnection.list(max_results=max_results, all_results=all_results)
        return safe_parse_object_list(
            obj_list=orm_connections,
            parser=_Connection._from_orm_object,
            message_generator=lambda x: f"Failed to load connection {x.connectionName}, skipped.",
        )

    def get(self, name: str, **kwargs) -> _Connection:
        """Get a connection entity.

        :param name: Name of the connection.
        :type name: str
        :return: connection object retrieved from the database.
        :rtype: ~promptflow.sdk.entities._connection._Connection
        """
        with_secrets = kwargs.get("with_secrets", False)
        raise_error = kwargs.get("raise_error", True)
        orm_connection = ORMConnection.get(name, raise_error)
        if orm_connection is None:
            return None
        if with_secrets:
            return _Connection._from_orm_object_with_secrets(orm_connection)
        return _Connection._from_orm_object(orm_connection)

    def delete(self, name: str) -> None:
        """Delete a connection entity.

        :param name: Name of the connection.
        :type name: str
        """
        ORMConnection.delete(name)

    def create_or_update(self, connection: _Connection, **kwargs):
        """Create or update a connection.

        :param connection: Run object to create or update.
        :type connection: ~promptflow.sdk.entities._connection._Connection
        """
        orm_object = connection._to_orm_object()
        now = datetime.now().isoformat()
        if orm_object.createdDate is None:
            orm_object.createdDate = now
        orm_object.lastModifiedDate = now
        ORMConnection.create_or_update(orm_object)
        return self.get(connection.name)
