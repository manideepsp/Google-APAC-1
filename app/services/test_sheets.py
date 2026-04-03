from app.services.sheets_client import add_task

def test():
    res = add_task("Make video", "Pending", "High", "Day 1")
    print(res.message)

if __name__ == "__main__":
    test()