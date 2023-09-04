import os

from intent import extract_intent

from promptflow import tool
from promptflow.connections import CustomConnection


@tool
def extract_intent_tool(customer_info, history, user_prompt_template, connection: CustomConnection) -> str:

    # set environment variables
    for key, value in dict(connection).items():
        os.environ[key] = value

    # call the entry function
    return extract_intent(
        customer_info=customer_info,
        history=history,
        user_prompt_template=user_prompt_template,
    )
