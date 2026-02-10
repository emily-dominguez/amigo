import streamlit as st
import json
from typing import Dict, List
from agent import agent_reply


st.set_page_config(page_title="Amigo Take-Home Prototype", page_icon="💬", layout="centered")

st.title("💬 Primary Care Amigo ")

# Simple session state
if "messages" not in st.session_state:
    st.session_state.messages: List[Dict[str, str]] = []

# Seed with opening message (only once)
if not st.session_state.messages:
    st.session_state.messages.append({
        "role": "assistant", 
        "content": "Hi! What brings you in today?"
    })

# Render chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Describe your symptoms or concerns..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get agent reply
    with st.chat_message("assistant"):
        result = agent_reply(st.session_state.messages, prompt, {})
        st.markdown(result.content)

    # Store assistant response
    st.session_state.messages.append({
        "role": "assistant", 
        "content": result.content
    })

# Clear chat button
st.divider()
if st.button("🔄 Clear Chat / New Consultation"):
    st.session_state.messages = [{"role": "assistant", "content": "Hi! What brings you in today?"}]
    st.rerun()

# Transcripts

def format_transcript(messages: List[Dict[str, str]]) -> str:
    lines = []
    for m in messages:
        role = "PATIENT" if m["role"] == "user" else "AGENT"
        lines.append(f"{role}: {m['content']}")
        lines.append("")  # blank line
    return "\n".join(lines).strip()

st.divider()
st.subheader("Export transcript")



txt_content = format_transcript(st.session_state.messages)
json_content = json.dumps(
    {
        "messages": st.session_state.messages,
    },
    indent=2
)

colA, colB = st.columns(2)
with colA:
    st.download_button(
        label="⬇️ Download transcript (.txt)",
        data=txt_content,
        file_name=f"transcript_.txt",
        mime="text/plain",
    )

with colB:
    st.download_button(
        label="⬇️ Download transcript (.json)",
        data=json_content,
        file_name=f"transcript_.json",
        mime="application/json",
    )
