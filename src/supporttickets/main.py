#!/usr/bin/env python
"""Support email flow: fetch support email, research, draft reply, HITL approval, send.

Uses native CrewAI Gmail integration (requires CREWAI_PLATFORM_INTEGRATION_TOKEN
and Gmail connected in AMP Integrations).
"""

import re
from email.utils import parseaddr

from crewai import Task, Crew
from pydantic import BaseModel

from crewai.flow import Flow, listen, router, start
from crewai.flow.human_feedback import human_feedback

from supporttickets.agents.gmail_agent import get_gmail_agent
from supporttickets.crews.support_crew.support_crew import SupportCrew


class SupportState(BaseModel):
    """State for the support email flow."""

    email_raw: str = ""
    original_sender: str = ""
    email_subject: str = ""
    draft: str = ""
    email_content: str = ""


def _extract_sender_from_raw(raw: str) -> str:
    """Extract email address from FROM line."""
    match = re.search(r"FROM:\s*(.+)", raw, re.IGNORECASE)
    if not match:
        return ""
    _, addr = parseaddr(match.group(1).strip())
    return addr or match.group(1).strip()


class SupportEmailFlow(Flow[SupportState]):
    """Flow that fetches support email, researches, drafts, gets HITL approval, then sends."""

    @start()
    def fetch_email(self, crewai_trigger_payload: dict | None = None):
        """Fetch the first support email from inbox using native Gmail integration."""
        agent = get_gmail_agent()
        task = Task(
            description=(
                "Use gmail/fetch_emails with q='subject:support' and maxResults=1 to find "
                "the first email whose subject contains 'support'. If you get message IDs, "
                "use gmail/get_message to retrieve the full content of the first one. "
                "Return the email in this exact format:\n"
                "SUBJECT: <subject>\nFROM: <sender email or name>\nBODY:\n<plain text body>"
            ),
            agent=agent,
            expected_output="Email content in SUBJECT/FROM/BODY format, or a message if none found.",
        )
        crew = Crew(agents=[agent], tasks=[task])
        result = crew.kickoff()
        raw = result.raw if hasattr(result, "raw") else str(result)

        if not raw or "no " in raw.lower()[:50] or "error" in raw.lower()[:50]:
            self.state.email_raw = ""
            self.state.email_content = ""
            return raw

        self.state.email_raw = raw
        self.state.email_content = raw
        self.state.original_sender = _extract_sender_from_raw(raw)

        match = re.search(r"SUBJECT:\s*(.+)", raw, re.IGNORECASE)
        self.state.email_subject = match.group(1).strip() if match else "Re: Support"

        return raw

    @listen(fetch_email)
    def extract_and_search(self):
        """Run support crew: extract, research, draft."""
        if not self.state.email_content:
            return "No support email to process."

        result = (
            SupportCrew()
            .crew()
            .kickoff(inputs={"email_content": self.state.email_content})
        )
        self.state.draft = result.raw
        return self.state.draft

    @router(extract_and_search)
    def check_has_draft(self, result):
        """Route: only request review if we have a draft."""
        if not self.state.draft or result == "No support email to process.":
            return "no_email"
        return "needs_review"

    @listen("needs_review")
    @human_feedback(
        message="Approve this support reply to send to the customer?",
        emit=["approved", "rejected"],
        llm="gpt-4o-mini",
    )
    def request_review(self):
        """Pause for human approval (handled by CrewAI AMP: email or dashboard)."""
        return self.state.draft

    @listen("approved")
    def send_email(self):
        """Send the approved draft to the original sender using native Gmail integration."""
        if not self.state.original_sender or not self.state.draft:
            return "Cannot send: missing sender or draft."

        agent = get_gmail_agent()
        subject = f"Re: {self.state.email_subject}"
        task = Task(
            description=(
                f"Send an email using gmail/send_email with:\n"
                f"to: {self.state.original_sender}\n"
                f"subject: {subject}\n"
                f"body: {self.state.draft}"
            ),
            agent=agent,
            expected_output="Confirmation that the email was sent successfully.",
        )
        crew = Crew(agents=[agent], tasks=[task])
        result = crew.kickoff()
        return result.raw if hasattr(result, "raw") else str(result)

    @listen("rejected")
    def on_rejected(self):
        """Handle rejection - no email sent."""
        return "Support reply rejected. No email sent."

    @listen("no_email")
    def on_no_email(self):
        """No support email found - nothing to do."""
        return "No support email found. Flow complete."


def kickoff():
    """Run the support email flow."""
    flow = SupportEmailFlow()
    flow.kickoff()


def plot():
    """Generate flow diagram."""
    flow = SupportEmailFlow()
    flow.plot("support_email_flow")


def run_with_trigger():
    """Run flow with trigger payload from AMP (e.g. Gmail trigger)."""
    import json
    import sys

    if len(sys.argv) < 2:
        raise ValueError("No trigger payload provided. Provide JSON as argument.")

    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON payload")

    flow = SupportEmailFlow()
    result = flow.kickoff({"crewai_trigger_payload": trigger_payload})
    return result


if __name__ == "__main__":
    kickoff()
