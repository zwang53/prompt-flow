# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


class FlowType:
    STANDARD = "standard"
    CHAT = "chat"
    EVALUATION = "evaluate"


class FlowJobType:
    STANDARD = "azureml.promptflow.FlowRun"
    EVALUATION = "azureml.promptflow.EvaluationRun"


# Use this storage since it's the storage used by notebook
DEFAULT_STORAGE = "workspaceworkingdirectory"
PROMPTFLOW_FILE_SHARE_DIR = "Promptflows"

CHILD_RUNS_PAGE_SIZE = 25  # align with UX
NODE_RUNS_PAGE_SIZE = 25

SESSION_CREATION_TIMEOUT_SECONDS = 10 * 60  # 10 minutes
PYTHON_REQUIREMENTS_TXT = "python_requirements_txt"
BASE_IMAGE = "image"
