from app.agents.reflection_agent import reflection_agent

def test():
    state = {
        "tasks": [
            {"task": "Create AI video", "priority": "High", "day": "Day 1"}
        ]
    }

    result = reflection_agent(state)
    print(result["tasks"])

if __name__ == "__main__":
    test()