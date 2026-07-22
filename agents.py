from crewai import Agent
from crewai_tools import SerperDevTool
from config import llm


search_tool = SerperDevTool()


researcher = Agent(
    role="AI Research Analyst",
    goal="Search latest information and create accurate reports",
    backstory="Expert AI researcher who uses web search tools",
    tools=[search_tool],
    llm=llm,
    verbose=True
)