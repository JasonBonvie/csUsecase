"""
Streamlit interface to trigger the deployed Support Email Flow on CrewAI AMP.

This app does NOT handle approve/deny - HITL is handled by CrewAI AMP
(email or dashboard). Use this app only to kick off the flow.
"""

import os

import requests
import streamlit as st

st.set_page_config(
    page_title="Support Email Flow",
    page_icon="📧",
    layout="centered",
)

st.title("Support Email Flow Trigger")

st.markdown(
    "Trigger the Support Email Flow on CrewAI AMP. "
    "Human approval/rejection is handled in CrewAI (email or dashboard)."
)

amp_url = os.getenv("CREWAI_AMP_URL", "").rstrip("/")
bearer_token = os.getenv("CREWAI_BEARER_TOKEN", "")

with st.sidebar:
    st.header("AMP Configuration")
    amp_url_input = st.text_input(
        "AMP Base URL",
        value=amp_url or "https://your-crew.crewai.com",
        help="From AMP Status tab, e.g. https://your-crew.crewai.com",
        key="amp_url",
    )
    token_input = st.text_input(
        "Bearer Token",
        value="",
        type="password",
        help="From AMP Status tab. Leave blank when using env.",
        key="bearer_token",
    )
    use_env = st.checkbox(
        "Use env vars",
        value=bool(amp_url and bearer_token),
        help="Use CREWAI_AMP_URL and CREWAI_BEARER_TOKEN from environment",
    )

base_url = (amp_url if use_env else amp_url_input or amp_url or "").rstrip("/")
token = bearer_token if use_env else token_input

if st.button("Trigger Support Flow", type="primary"):
    if not base_url or not token or (token == "••••••••" and not bearer_token):
        st.error("Set AMP URL and Bearer Token in sidebar or environment.")
    else:
        url = f"{base_url.rstrip('/')}/kickoff"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {}

        with st.spinner("Triggering flow..."):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=30)
                if resp.ok:
                    data = resp.json()
                    kickoff_id = data.get("id") or data.get("kickoff_id") or data.get("execution_id")
                    st.success(f"Flow triggered successfully.")
                    if kickoff_id:
                        st.info(f"Kickoff ID: `{kickoff_id}`")
                        st.markdown(f"Check status: `GET {base_url}/{kickoff_id}/status`")
                else:
                    st.error(f"Error {resp.status_code}: {resp.text[:500]}")
            except requests.RequestException as e:
                st.error(f"Request failed: {e}")

st.divider()
st.caption("Deploy this flow to AMP with `crewai deploy create`. Set CREWAI_AMP_URL and CREWAI_BEARER_TOKEN for production.")
