"""Gmail agent using native CrewAI platform integration.

Requires CREWAI_PLATFORM_INTEGRATION_TOKEN and Gmail connected in AMP Integrations.
"""

from crewai import Agent


def get_gmail_agent() -> Agent:
    """Return an agent with Gmail fetch and send capabilities."""
    return Agent(
        llm="anthropic/claude-haiku-4-5-20251001",
        role="Gmail Assistant",
        goal="Fetch and send emails via Gmail using platform integration",
        backstory="You use Gmail tools to fetch emails matching search criteria and send replies. "
        "You return content in the exact format requested.",
        apps=[
            "gmail/fetch_emails",
            "gmail/get_message",
            "gmail/send_email",
        ],
        verbose=True,
    )
