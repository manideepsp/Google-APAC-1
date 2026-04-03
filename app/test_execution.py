from app.agents.execution_agent import execution_agent

def test():
    state = {
        "tasks": [
            {"task": "Choose niche", "priority": "High", "day": "Day 1"},
            {"task": "Create video ideas", "priority": "High", "day": "Day 2"},
        ]
    }

    execution_agent(state)
    print("Tasks sent to Sheets!")

if __name__ == "__main__":
    test()