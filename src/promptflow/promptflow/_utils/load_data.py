# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from promptflow.exceptions import ErrorTarget, UserErrorException

module_logger = logging.getLogger(__name__)

MAX_ROWS_COUNT = 1000
DATA_EXCEED_LIMITATION = (
    "The supplied data contains %s lines that exceed the limit. Currently, only the first %s lines will be processed."
    " We are actively working on supporting larger datasets in the near future. Please stay tuned for updates."
)


def _pd_read_file(local_path: str, logger: logging.Logger = None) -> pd.DataFrame:
    local_path = str(local_path)
    # if file is empty, return empty DataFrame directly
    if (
        os.path.getsize(local_path) == 0
    ):  # CodeQL [SM01305] Safe use per local_path is set by PRT service not by end user
        return pd.DataFrame()
    # load different file formats
    if local_path.endswith(".csv"):
        df = pd.read_csv(local_path, keep_default_na=False)
    elif local_path.endswith(".json"):
        df = pd.read_json(local_path)
    elif local_path.endswith(".jsonl"):
        df = pd.read_json(local_path, lines=True)
    elif local_path.endswith(".tsv"):
        df = pd.read_table(local_path, keep_default_na=False)
    elif local_path.endswith(".parquet"):
        df = pd.read_parquet(local_path)
    else:
        # parse file as jsonl when extension is not known (including unavailable)
        # ignore and logging if failed to load file content.
        try:
            df = pd.read_json(local_path, lines=True)
        except:  # noqa: E722
            if logger is None:
                logger = module_logger
            logger.warning(
                f"File {Path(local_path).name} is not supported format: "
                f"csv, tsv, json, jsonl, parquet. Ignoring it."
            )
            return pd.DataFrame()
    return df


def _bfs_dir(dir_path: List[str]) -> Tuple[List[str], List[str]]:
    """BFS traverse directory with depth 1, returns files and directories"""
    files, dirs = [], []
    for path in dir_path:
        for filename in os.listdir(path):
            file = Path(path, filename).resolve()
            if file.is_file():
                files.append(str(file))
            else:
                dirs.append(str(file))
    return files, dirs


def _handle_dir(dir_path: str, max_rows_count: int, logger: logging.Logger = None) -> pd.DataFrame:
    """load data from directory"""
    df = pd.DataFrame()

    # BFS traverse directory to collect files to load
    target_dir = [str(dir_path)]
    while len(target_dir) > 0:
        files, dirs = _bfs_dir(target_dir)
        for file in files:
            current_df = _pd_read_file(file, logger=logger)
            df = pd.concat([df, current_df])
        length = len(df)
        if max_rows_count and length > 0:
            if length > max_rows_count:
                if logger is None:
                    logger = module_logger
                logger.warning(DATA_EXCEED_LIMITATION, length, max_rows_count)
                df = df.head(max_rows_count)
            break
        # no readable data in current level, dive into next level
        target_dir = dirs
    return df


def load_data(local_path: str, *, logger: logging.Logger = None, max_rows_count: int = None) -> List[Dict[str, Any]]:
    """load data from local file"""
    df = load_df(local_path, logger, max_rows_count=max_rows_count or MAX_ROWS_COUNT)

    # convert dataframe to list of dict
    result = []
    # df = df.reset_index() # add index column
    for _, row in df.iterrows():
        result.append(row.to_dict())
    return result


def load_df(local_path: str, logger: logging.Logger = None, max_rows_count: int = None) -> pd.DataFrame:
    """load data from local file to df. For the usage of PRS."""
    lp = Path(local_path)
    try:
        if lp.is_file():
            df = _pd_read_file(local_path, logger=logger)
            # honor max_rows_count if it is specified
            if max_rows_count and len(df) > max_rows_count:
                if logger is None:
                    logger = module_logger
                logger.warning(DATA_EXCEED_LIMITATION, len(df), max_rows_count)
                df = df.head(max_rows_count)
        else:
            df = _handle_dir(local_path, max_rows_count=max_rows_count, logger=logger)
    except ValueError as e:
        raise InvalidUserData(
            message_format="Fail to load invalid data. We support file formats: csv, tsv, json, jsonl, parquet. "
            "Please check input data."
        ) from e

    return df


class InvalidUserData(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)
