You are given a list of orders with item_numbers from a customer and a statement from the customer. It is your job to identify
the intent that the customer has with their statement. Possible intents can be:
"product return", "product exchange", "general question", "product question", "other".

If the intent is product related ("product return", "product exchange", "product question"), then you should also
provide the order id and item that the customer is referring to in their statement.

For instance if you are give the following list of orders:

order_number: 2020230
date: 2023-04-23
store_location: SeattleStore
items:
- description: Roof Rack, color black, price $199.99
  item_number: 101010
- description: Running Shoes, size 10, color blue, price $99.99
  item_number: 202020

You are given the following customer statements:
- I am having issues with the jobbing shoes I bought.

Then you should answer with in valid yaml format with the fields intent, order_number, item, and item_number like so:
intent: product question
order_number: 2020230
descrption: Running Shoes, size 10, color blue, price $99.99
item_number: 202020

Here is the acutal problem you need to solve:

In triple backticks below is the customer information and a list of orders.
```
{customer_info}
```

In triple backticks below are the is the chat history with customer statements and replies from the customer service agent:
```
{chat_history}
```

What is the customer's `intent:` here?
"product return", "exchange product", "general question", "product question" or "other"?

Reply with only the intent string.
