import streamlit as st
import pandas as pd
from agent.graph import mcp_agent

# --- UI Configuration ---
st.set_page_config(page_title="Enterprise SQL Agent", page_icon="🤖", layout="wide")
st.title("🤖 Autonomous Text-to-SQL Agent")
st.markdown("""
    *Powered by Llama 3.3 70B, LangGraph, and PostgreSQL.* Ask questions in plain English, and the agent will intelligently query the database.
""")

# --- Session State Management ---
# We use this to remember the chat history and the graph's state across UI reruns
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_state" not in st.session_state:
    st.session_state.current_state = None

# --- Display Chat History ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # If the message has extra metrics/SQL data, display it in an expander
        if "sql" in msg:
            with st.expander("🔍 View Database Execution Details"):
                st.code(msg["sql"], language="sql")
                if "metrics" in msg and msg["metrics"]:
                    st.write("**Performance Metrics:**")
                    for metric in msg["metrics"]:
                        st.text(metric)

# --- Handle Human-In-The-Loop (HITL) Approval ---
# If the graph paused because it needs human approval for a modifying query
if st.session_state.current_state and st.session_state.current_state.get("requires_approval") and not st.session_state.current_state.get("is_approved"):
    st.warning("⚠️ **CRITICAL ACTION DETECTED:** The agent wants to modify the database.")
    st.code(st.session_state.current_state.get("generated_sql"), language="sql")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Approve & Execute", use_container_width=True):
            st.session_state.current_state["is_approved"] = True
            with st.spinner("Executing approved modification..."):
                # Resume the graph with the approved state
                final_state = mcp_agent.invoke(st.session_state.current_state)
                st.session_state.messages.append({"role": "assistant", "content": final_state.get("final_answer")})
                st.session_state.current_state = None
                st.rerun()
                
    with col2:
        if st.button("❌ Reject & Abort", type="primary", use_container_width=True):
            st.error("Action aborted by user.")
            st.session_state.messages.append({"role": "assistant", "content": "I have aborted the operation as requested."})
            st.session_state.current_state = None
            st.rerun()

# --- Chat Input ---
# Only show the input box if we are NOT waiting for an approval
elif prompt := st.chat_input("Ask a question about your database (e.g., 'What are our top selling products?'):"):
    
    # Add user message to UI
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Run the Agent
    with st.chat_message("assistant"):
        with st.spinner("Thinking & Generating SQL..."):
            initial_state = {
                "user_query": prompt,
                "correction_attempts": 0,
                "is_approved": False
            }
            
            # Execute the LangGraph workflow
            result_state = mcp_agent.invoke(initial_state)
            
            # If the graph halts for approval, we save the state and rerun the UI to show the buttons
            if result_state.get("requires_approval") and not result_state.get("is_approved"):
                st.session_state.current_state = result_state
                st.rerun()
            
            # Otherwise, it was a safe SELECT query, so we display the final answer
            answer = result_state.get("final_answer", "Sorry, I couldn't process that.")
            st.markdown(answer)
            
            # Display the slick expander with SQL and Performance Metrics
            with st.expander("🔍 View Database Execution Details"):
                st.code(result_state.get("generated_sql"), language="sql")
                metrics = result_state.get("execution_metrics", [])
                if metrics:
                    st.write("**Performance Metrics:**")
                    for metric in metrics:
                        st.text(metric)
            
            # Save to chat history
            st.session_state.messages.append({
                "role": "assistant", 
                "content": answer,
                "sql": result_state.get("generated_sql"),
                "metrics": metrics
            })