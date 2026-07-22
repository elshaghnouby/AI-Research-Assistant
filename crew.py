from crewai import Crew
from agents import researcher
from tasks import research_task


crew = Crew(
    agents=[researcher],
    tasks=[research_task],
    verbose=False
)