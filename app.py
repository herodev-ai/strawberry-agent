import json

from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.runnable import Runnable
from langchain.schema.runnable.config import RunnableConfig

import chainlit as cl

from helpers.prompts import PROMPT_ANSWER, PROMPT_INTENT, PROMPT_TASK, PROMPT_EXTRACT


@cl.step(type="tool", name="count characters")
async def count_occurrences_of_substring_in_string(string, substring):
    return string.lower().count(substring.lower())


@cl.on_chat_start
async def on_chat_start():
    model = ChatGroq(temperature=0.7, model_name="llama-3.1-8b-instant")
    cl.user_session.set("model", model)


@cl.on_message
async def on_message(message: cl.Message):
    model = cl.user_session.get("model")  # type: ChatGroq

    # Step 1: Understand the user's intent
    messages = [
        ("system", PROMPT_INTENT),
        ("human", message.content)
    ]
    response = model.invoke(messages)  # type: BaseMessage
    intent = response.content

    # Step 2: Match the intent to a task
    messages = [
        ("system", PROMPT_TASK),
        ("human", intent)
    ]
    response = model.invoke(messages)  # type: BaseMessage
    task = json.loads(response.content)

    final_prompt = message.content

    # Step 3: Select the appropriate tool if there is a match
    if task["task"] == "COUNT_LETTERS_IN_WORD":
        user_prompt = f"{intent}\nPlease extract the letter and the word from the following text: {message.content}"
        messages = [
            ("system", PROMPT_EXTRACT),
            ("human", user_prompt)
        ]
        response = model.invoke(messages)  # type: BaseMessage
        parameters = json.loads(response.content)

        result = await count_occurrences_of_substring_in_string(parameters["word"], parameters["letter"])
        final_prompt = f"The user asked: {message.content}\nThe correct answer is: {result}"

    # Step 4: Provide the answer
    prompt = ChatPromptTemplate.from_messages([
        ("system", PROMPT_ANSWER),
        ("human", final_prompt),
    ])

    runnable = prompt | model | StrOutputParser()  # type: Runnable
    msg = cl.Message(content="")

    async for chunk in runnable.astream(
            {},
            config=RunnableConfig(callbacks=[cl.LangchainCallbackHandler()]),
    ):
        await msg.stream_token(chunk)

    await msg.send()
