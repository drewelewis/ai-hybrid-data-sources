import asyncio
from os import getenv

from agent_framework import AgentThread
from dotenv import load_dotenv

from markets_risk_agent import create_markets_risk_agent


QUIT_COMMANDS = {"exit", "quit"}


async def run_chat() -> None:
    load_dotenv()
    environment_name = getenv("ENVIRONMENT_NAME", "").strip().lower()
    agent = create_markets_risk_agent()
    thread = AgentThread()

    print("=" * 60)
    print("Contoso Bank - Markets Risk Analyst")
    print("=" * 60)
    print(f"Environment: {environment_name}")
    print("Model-only analysis through the governed APIM endpoint.")
    print("This agent cannot retrieve live bank or market data.")
    print("Commands: exit | quit")

    while True:
        try:
            message = await asyncio.to_thread(input, "\nYou: ")
        except EOFError:
            print()
            return

        message = message.strip()
        if not message:
            continue
        if message.lower() in QUIT_COMMANDS:
            return

        response = await agent.run(message, thread=thread)
        print(f"\nAgent: {response.text or ''}")


def main() -> int:
    try:
        asyncio.run(run_chat())
    except ValueError as error:
        print(f"Configuration error: {error}")
        return 2
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
