from pathlib import Path

from ddaword_cli import agent


def test_get_system_prompt_creates_agent_files(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "AGENT_ROOT", tmp_path)

    prompt = agent.get_system_prompt("demo-agent")

    assert "<agent_memory>" in prompt

    agent_dir = agent.get_agent_directory("demo-agent")
    assert agent_dir.exists()
    assert (agent_dir / "agent.md").exists()
    assert (agent_dir / agent.MEMORY_DIRNAME).exists()


def test_reset_agent_replaces_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "AGENT_ROOT", tmp_path)

    agent.reset_agent("primary")
    primary_path = agent.get_agent_directory("primary") / "agent.md"
    original = primary_path.read_text()

    primary_path.write_text("custom instructions")
    agent.reset_agent("secondary", source_agent="primary")

    secondary_path = agent.get_agent_directory("secondary") / "agent.md"
    assert secondary_path.read_text() == "custom instructions"

    agent.reset_agent("primary")
    assert primary_path.read_text() == original

