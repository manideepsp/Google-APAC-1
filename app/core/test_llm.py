from app.core.llm import get_llm

def test_llm():
    llm = get_llm()
    response = llm.invoke("Say hello like a YouTube expert")
    print(response.content)

if __name__ == "__main__":
    test_llm()