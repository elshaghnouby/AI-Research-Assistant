import os
from dotenv import load_dotenv
from crewai import LLM

load_dotenv()


llm = LLM(
    model="gpt-5-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
    
)