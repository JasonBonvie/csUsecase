"""Support crew: extracts info, researches, and drafts support responses."""

from typing import List

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool


@CrewBase
class SupportCrew:
    """Crew that extracts, researches, and drafts support email responses."""

    agents: List[BaseAgent]
    tasks: List[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def extractor(self) -> Agent:
        return Agent(
            config=self.agents_config["extractor"],  # type: ignore[index]
            verbose=True,
        )

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],  # type: ignore[index]
            tools=[SerperDevTool()],
            verbose=True,
        )

    @agent
    def responder(self) -> Agent:
        return Agent(
            config=self.agents_config["responder"],  # type: ignore[index]
            verbose=True,
        )

    @task
    def extract_task(self) -> Task:
        return Task(
            config=self.tasks_config["extract_task"],  # type: ignore[index]
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"],  # type: ignore[index]
            context=[self.extract_task()],
        )

    @task
    def draft_task(self) -> Task:
        return Task(
            config=self.tasks_config["draft_task"],  # type: ignore[index]
            context=[self.extract_task(), self.research_task()],
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.extractor(), self.researcher(), self.responder()],
            tasks=[self.extract_task(), self.research_task(), self.draft_task()],
            process=Process.sequential,
            verbose=True,
        )
