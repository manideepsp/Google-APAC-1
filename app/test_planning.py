from app.agents.planning_agent import planning_agent

def test():
    state = {
        "research": {
            "topics": ["AI tools", "LLMs"],
            "titles": ["Top AI tools", "Best AI apps"]
        }
    }

    result = planning_agent(state)
    print(result["tasks"])

if __name__ == "__main__":
    test()