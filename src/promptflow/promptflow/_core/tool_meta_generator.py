# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

"""
This file can generate a meta file for the given prompt template or a python file.
"""
import importlib.util
import inspect
import json
import re
import types
from dataclasses import asdict
from pathlib import Path
from traceback import TracebackException

from jinja2.environment import COMMENT_END_STRING, COMMENT_START_STRING

from promptflow._core._errors import MetaFileNotFound, MetaFileReadError
from promptflow._core.tool import ToolProvider
from promptflow._utils.exception_utils import ADDITIONAL_INFO_USER_CODE_STACKTRACE, get_tb_next, last_frame_info
from promptflow._utils.tool_utils import function_to_interface, get_inputs_for_prompt_template
from promptflow.contracts.tool import InputDefinition, Tool, ToolType, ValueType
from promptflow.exceptions import ErrorTarget, UserErrorException

PF_MAIN_MODULE_NAME = "__pf_main__"


def asdict_without_none(obj):
    return asdict(obj, dict_factory=lambda x: {k: v for (k, v) in x if v})


def generate_prompt_tool(name, content, prompt_only=False, source=None):
    """Generate meta for a single jinja template file."""
    # Get all the variable name from a jinja template
    tool_type = ToolType.PROMPT if prompt_only else ToolType.LLM
    try:
        inputs = get_inputs_for_prompt_template(content)
    except Exception as e:
        msg = f"Parsing jinja got exception: {e}"
        raise JinjaParsingError(msg) from e

    if prompt_only:
        # Currently this is a hard code for prompt tool
        # TODO: Use registration instead of hard code
        reserved_keys_to_raise = {"template"}
    else:
        # Import the tools module to initialize the LLM reserved keys
        import promptflow.tools  # noqa: F401
        from promptflow._core.tools_manager import reserved_keys

        reserved_keys_to_raise = reserved_keys

    for input in inputs:
        if input in reserved_keys_to_raise:
            msg = (
                f"Parsing jinja got exception: Variable name {input} is reserved by {tool_type.value} tool."
                + " Please change another name."
            )
            raise ReservedVariableCannotBeUsed(msg)

    pattern = f"{COMMENT_START_STRING}(((?!{COMMENT_END_STRING}).)*){COMMENT_END_STRING}"
    match_result = re.match(pattern, content)
    description = match_result.groups()[0].strip() if match_result else None
    # Construct the Tool structure
    tool = Tool(
        name=name,
        description=description,
        type=tool_type,
        inputs={i: InputDefinition(type=[ValueType.STRING]) for i in inputs},
        outputs={},
    )
    if source is None:
        tool.code = content
    else:
        tool.source = source
    return tool


def generate_prompt_meta_dict(name, content, prompt_only=False, source=None):
    return asdict_without_none(generate_prompt_tool(name, content, prompt_only, source))


def is_tool(f):
    if not isinstance(f, types.FunctionType):
        return False
    if not hasattr(f, "__tool"):
        return False
    return True


def collect_tool_functions_in_module(m):
    tools = []
    for _, obj in inspect.getmembers(m):
        if is_tool(obj):
            # Note that the tool should be in defined in exec but not imported in exec,
            # so it should also have the same module with the current function.
            if getattr(obj, "__module__", "") != m.__name__:
                continue
            tools.append(obj)
    return tools


def collect_tool_methods_in_module(m):
    tools = []
    for _, obj in inspect.getmembers(m):
        if isinstance(obj, type) and issubclass(obj, ToolProvider) and obj.__module__ == m.__name__:
            for _, method in inspect.getmembers(obj):
                if is_tool(method):
                    tools.append(method)
    return tools


def _parse_tool_from_function(f):
    if hasattr(f, "__tool") and isinstance(f.__tool, Tool):
        return f.__tool
    if hasattr(f, "__original_function"):
        f = f.__original_function
    try:
        inputs, _, _ = function_to_interface(f)
    except Exception as e:
        raise BadFunctionInterface(f"Failed to parse interface for tool {f.__name__}, reason: {e}") from e
    class_name = None
    if "." in f.__qualname__:
        class_name = f.__qualname__.replace(f".{f.__name__}", "")
    # Construct the Tool structure
    return Tool(
        name=f.__qualname__,
        description=inspect.getdoc(f),
        inputs=inputs,
        type=ToolType.PYTHON,
        class_name=class_name,
        function=f.__name__,
        module=f.__module__,
    )


def generate_python_tools_in_module(module):
    tool_functions = collect_tool_functions_in_module(module)
    tool_methods = collect_tool_methods_in_module(module)
    return [_parse_tool_from_function(f) for f in tool_functions + tool_methods]


def generate_python_tools_in_module_as_dict(module):
    tools = generate_python_tools_in_module(module)
    return {f"{t.module}.{t.name}": asdict_without_none(t) for t in tools}


def load_python_module_from_file(src_file: Path):
    # Here we hard code the module name as __pf_main__ since it is invoked as a main script in pf.
    src_file = Path(src_file).resolve()  # Make sure the path is absolute to align with python import behavior.
    spec = importlib.util.spec_from_file_location("__pf_main__", location=src_file)
    if spec is None or spec.loader is None:
        raise PythonLoaderNotFound(f"Failed to load python file '{src_file}', please make sure it is a valid .py file.")
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        # TODO: add stacktrace to additional info
        raise PythonLoadError(f"Failed to load python module from file '{src_file}', reason: {e}.") from e
    return m


def load_python_module(content, source=None):
    # Source represents code first experience.
    if source is not None and Path(source).exists():
        return load_python_module_from_file(Path(source))
    try:
        m = types.ModuleType(PF_MAIN_MODULE_NAME)
        exec(content, m.__dict__)
        return m
    except Exception as e:
        msg = f"Parsing python got exception: {e}"
        raise PythonParsingError(msg) from e


def collect_tool_function_in_module(m):
    tools = collect_tool_functions_in_module(m)
    if len(tools) == 0:
        raise NoToolDefined("No tool found in the python script.")
    elif len(tools) > 1:
        tool_names = ", ".join(t.__name__ for t in tools)
        raise MultipleToolsDefined(f"Expected 1 but collected {len(tools)} tools: {tool_names}.")
    return tools[0]


def generate_python_tool(name, content, source=None):
    m = load_python_module(content, source)
    f = collect_tool_function_in_module(m)
    tool = _parse_tool_from_function(f)
    tool.module = None
    if name is not None:
        tool.name = name
    if source is None:
        tool.code = content
    else:
        tool.source = source
    return tool


def generate_python_meta_dict(name, content, source=None):
    return asdict_without_none(generate_python_tool(name, content, source))


def generate_python_meta(name, content, source=None):
    return json.dumps(generate_python_meta_dict(name, content, source), indent=2)


def generate_prompt_meta(name, content, prompt_only=False, source=None):
    return json.dumps(generate_prompt_meta_dict(name, content, prompt_only, source), indent=2)


def generate_tool_meta_dict_by_file(path: str, tool_type: ToolType):
    """Generate meta for a single tool file, which can be a python file or a jinja template file,
    note that if a python file is passed, correct working directory must be set and should be added to sys.path.
    """
    tool_type = ToolType(tool_type)
    file = Path(path).resolve()
    if not file.is_file():
        raise MetaFileNotFound(
            message_format="Meta file not found, path '{file_path}', type '{tool_type}'.",
            file_path=str(file),
            tool_type=tool_type,
        )
    try:
        content = file.read_text()
    except Exception as e:
        raise MetaFileReadError(
            message_format=("Reading meta file failed, path '{file_path}', type '{tool_type}', exception {exception}."),
            file_path=str(file),
            tool_type=tool_type,
            exception=str(e),
        ) from e

    name = file.stem
    if tool_type == ToolType.PYTHON:
        return generate_python_meta_dict(name, content, path)
    elif tool_type == ToolType.LLM:
        return generate_prompt_meta_dict(name, content, source=path)
    elif tool_type == ToolType.PROMPT:
        return generate_prompt_meta_dict(name, content, prompt_only=True, source=path)
    else:
        raise ValueError(f"Unsupported tool type {tool_type}.")


class ToolValidationError(UserErrorException):
    """Base exception raised when failed to validate tool."""

    def __init__(self, message):
        super().__init__(message, target=ErrorTarget.TOOL)


class JinjaParsingError(ToolValidationError):
    pass


class ReservedVariableCannotBeUsed(JinjaParsingError):
    pass


class PythonParsingError(ToolValidationError):
    pass


class PythonLoaderNotFound(ToolValidationError):
    pass


class NoToolDefined(PythonParsingError):
    pass


class MultipleToolsDefined(PythonParsingError):
    pass


class BadFunctionInterface(PythonParsingError):
    pass


class PythonLoadError(PythonParsingError):
    @property
    def python_load_traceback(self):
        """Return the traceback inside user's source code scope.

        The traceback inside the promptflow's internal code will be taken off.
        """
        exc = self.inner_exception
        if exc and exc.__traceback__ is not None:
            tb = exc.__traceback__
            # The first three frames are always the code in tool.py who invokes the tool.
            # We do not want to dump it to user code's traceback.
            tb = get_tb_next(tb, next_cnt=3)
            if tb is not None:
                te = TracebackException(type(exc), exc, tb)
                formatted_tb = "".join(te.format())

                return formatted_tb
        return None

    @property
    def additional_info(self):
        """Set the python load exception details as additional info."""
        if not self.inner_exception:
            return None

        info = {
            "type": self.inner_exception.__class__.__name__,
            "message": str(self.inner_exception),
            "traceback": self.python_load_traceback,
        }

        info.update(last_frame_info(self.inner_exception))

        return {
            ADDITIONAL_INFO_USER_CODE_STACKTRACE: info,
        }
