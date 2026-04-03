from app.graph.workflow import build_graph

def run():
    graph = build_graph()

    state = {
        "goal": "Start a YouTube channel about AI tools"
    }

    result = graph.invoke(state)

    print("FINAL STATE:")
    print(result)

if __name__ == "__main__":
    run()