from agent import build_graph
from datetime import datetime

def run_agent():
    days_of_week= datetime.today().strftime("%A")
    graph= build_graph()
    graph.invoke({
        "day_of_week":days_of_week,
        "search_results":[],
        "generated_post": "",
        "quality_passed":False,
        "posted":False,
        "posted_topics":[]
        })
    print("Graph finished")

if __name__ == "__main__":
    run_agent()


