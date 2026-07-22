import streamlit as st
from crew import crew


st.set_page_config(
    page_title="AI Research Assistant",
    page_icon="🤖",
    layout="wide"
)


st.title("🤖 AI Research Assistant")

st.caption(
    "Generate professional AI-powered research reports in seconds."
)


# حفظ التقرير في Session
if "report" not in st.session_state:
    st.session_state.report = None


# Form
with st.form("research_form"):

    topic = st.text_area(
        label="🔍 What do you want to research?",
        height=100,
        placeholder="Type your question here..."
    )


    report_length = st.selectbox(
        "📄 Report length",
        [
            "Short (300 words)",
            "Medium (500 words)",
            "Long (800 words)"
        ]
    )


    submit = st.form_submit_button(
        "🚀 Generate Report"
    )


# تشغيل البحث
if submit:

    if topic:

        with st.spinner("Researching and generating report..."):

            result = crew.kickoff(
                inputs={
                    "topic": topic,
                    "length": report_length
                }
            )

            st.session_state.report = result.raw

    else:
        st.warning("Please enter a topic")


# عرض التقرير
if st.session_state.report:

    st.divider()

    st.header("📄 Research Report")


    st.markdown(
        st.session_state.report
    )


    st.divider()


    if st.button("🔄 New Question"):

        st.session_state.report = None

        st.rerun()