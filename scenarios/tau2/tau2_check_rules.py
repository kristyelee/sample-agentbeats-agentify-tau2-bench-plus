from litellm import completion
import json
import re
from typing import Any, Dict, List

# ==> COMMENT: Specify all the rules governing the interaction (copied from env.wiki)
SCENARIO_RULES = {}
SCENARIO_RULES["retail"] = [
"""
General rules:
- At the beginning of the conversation, you have to authenticate the user identity by locating their user id via email, or via name + zip code. This has to be done even when the user already provides the user id.
- Once the user has been authenticated, you can provide the user with information about order, product, profile information, e.g. help the user look up order id.
- You can only help one user per conversation (but you can handle multiple requests from the same user), and must deny any requests for tasks related to any other user.
- Before taking consequential actions that update the database (cancel, modify, return, exchange), you have to list the action detail and obtain explicit user confirmation (yes) to proceed.
- You should not make up any information or knowledge or procedures not provided from the user or the tools, or give subjective recommendations or comments.
- You should at most make one tool call at a time, and if you take a tool call, you should not respond to the user at the same time. If you respond to the user, you should not make a tool call.
- You should transfer the user to a human agent if and only if the request cannot be handled within the scope of your actions.
""",
"""
Canceling pending order rules:
- An order can only be cancelled if its status is 'pending', and you should check its status before taking the action.
- The user needs to confirm the order id and the reason (either 'no longer needed' or 'ordered by mistake') for cancellation.
- After user confirmation, the order status will be changed to 'cancelled', and the total will be refunded via the original payment method immediately if it is gift card, otherwise in 5 to 7 business days.
""",
"""
Modify payment rules:
- The user can only choose a single payment method different from the original payment method.
- If the user wants the modify the payment method to gift card, it must have enough balance to cover the total amount.
- After user confirmation, the order status will be kept 'pending'. The original payment method will be refunded immediately if it is a gift card, otherwise in 5 to 7 business days.
""",
"""
Modify items rules:
- This action can only be called once, and will change the order status to 'pending (items modifed)', and the agent will not be able to modify or cancel the order anymore. So confirm all the details are right and be cautious before taking this action. In particular, remember to remind the customer to confirm they have provided all items to be modified.
- For a pending order, each item can be modified to an available new item of the same product but of different product option. There cannot be any change of product types, e.g. modify shirt to shoe.
- The user must provide a payment method to pay or receive refund of the price difference. If the user provides a gift card, it must have enough balance to cover the price difference.
""",
"""
Return delivered order rules:
- An order can only be returned if its status is 'delivered', and you should check its status before taking the action.
- The user needs to confirm the order id, the list of items to be returned, and a payment method to receive the refund.
- The refund must either go to the original payment method, or an existing gift card.
- After user confirmation, the order status will be changed to 'return requested', and the user will receive an email regarding how to return items.
""",
"""
Exchange delivered order rules:
- An order can only be exchanged if its status is 'delivered', and you should check its status before taking the action. In particular, remember to remind the customer to confirm they have provided all items to be exchanged.
- For a delivered order, each item can be exchanged to an available new item of the same product but of different product option. There cannot be any change of product types, e.g. modify shirt to shoe.
- The user must provide a payment method to pay or receive refund of the price difference. If the user provides a gift card, it must have enough balance to cover the price difference.
- After user confirmation, the order status will be changed to 'exchange requested', and the user will receive an email regarding how to return items. There is no need to place a new order
""",
]

def _extract_json_objects(text: str) -> List[Dict[str, Any]]:
    """
    Extract all <json>...</json> blocks from `text` and parse them to dicts.
    Raises ValueError if a block cannot be parsed as JSON.
    """
    blocks = re.findall(r"<json>(.*?)</json>", text, flags=re.DOTALL | re.IGNORECASE)
    parsed = []
    for block in blocks:
        s = block.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError as e:
            try:
                obj = json.loads(s.replace("'", '"'))
            except Exception:
                raise ValueError(f"Failed to parse JSON block: {e}\nBlock:\n{s}") from e
        parsed.append(obj)
    return parsed

def _filter_domain_information(text):
    """
    Remove every block starting at a header "## Domain basic" (case-insensitive)
    up to and including the next header that starts with "## ".

    Returns the cleaned text.
    """
    cleaned = []
    pattern0 = re.compile(r'^##(?!#)\s*domain\s+basic\s*\b', re.IGNORECASE)
    pattern1 = re.compile(r'^##(?!#)', re.IGNORECASE)
    remove = False
    for line in text.splitlines(True):
        if pattern0.match(line):
            remove = True
        elif pattern1.match(line):
            remove = False
        if not remove:
            cleaned.append(line)
    return cleaned

def _extract_message_exchanges(simulation_messages):
    messages = []
    for message in simulation_messages:
        if message.role == 'assistant' and message.content:
            messages.append(f"Agent message: {message.content}")
        elif message.role == 'user' and message.content:
            messages.append(f"User message: {message.content}")
        #elif message.role == 'Assistant' and message.tool_calls:
        #    messages.append(f"Assistant tool calls: {message.tool_calls}")
        #elif message.role == 'tool' and message.content:
        #    messages.append(f"Tool call: {message.content}")
    return messages

def llm_rules_evaluator(env, env_name, simulation_messages):
    """
    Use the LLM to check if there are any rules that are violated in the message exchanges
    between the white-agent and the green-agent
    """
    results = {
        "violation_count" : 0,
        "violations" : [],
    }

    #
    # Specify the system message
    #
    scenario_rules = ""
    if SCENARIO_RULES.get(env_name, False):
        scenario_rules = f"{SCENARIO_RULES[env_name]}"
    else:
        scenario_rules = _filter_domain_information(env.policy)

    system_message = \
        f"You are to evaluate the performance of a {env_name} agent based on the following rules: {scenario_rules}." + \
        "Your response should include the number of rules violated and the list violated rules in json format." + \
        """Please wrap the JSON part with <json>...</json> tags.
        The JSON should contain:
        - "violation_count": the number of rules violated.
        - "violations": a list of violated rules.
        If there are no violation, you should return "violation_count" value 0
        """

    messages = [{
        "role": "system",
        "content": f"{system_message}",
    }]

    #
    # pass the exchanged messages between the green-agent and the white-agent
    #
    message_exchanges = _extract_message_exchanges(simulation_messages)
    messages.append({
        "role": "user",
        "content": f"The following are the interaction between the agent and the user:\n{message_exchanges}",
    })

    #
    # Call the LLM
    #
    response = completion(
        messages=messages,
        model="openai/gpt-4o",
        custom_llm_provider="openai",
        temperature=0.0,
    )

    #
    # Check for violations in the response
    #
    response_message = response.choices[0].message.model_dump()
    violations = _extract_json_objects(response_message["content"])
    if violations and violations[0]:
        results["violation_count"] = violations[0].get("violation_count", 0)
        results["violations"] = violations[0].get("violations", [])

    return results
