from crewai import Task
from agents import researcher


research_task = Task(
    description="""
    Research:

    {topic}


    Return a professional report:

# Title

## Executive Summary

## Key Findings

## Important Facts

## Analysis

## Risks

## Recommendations

## Sources


Report Length: {length}

If the user selects:

- Short → around 300 words
- Medium → around 600 words
- Long → around 1000 words

Follow the selected length.

    """ ,
    expected_output="""
    A concise AI research summary under 500 words.
    """,

    agent=researcher
)