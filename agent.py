from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from tools import search_news, post_to_instagram, generate_post
from memory import load_memory, save_memory


class AgentState(TypedDict):
    day_of_week: str
    search_results: list
    generated_post: str
    quality_passed: bool
    posted: bool
    posted_topics: list


def route_quality(state: AgentState):
    if state["quality_passed"]:
        return "post_to_instagram"
    else:
        return "generate_post"


def build_graph():
    insta_graph = StateGraph(AgentState)
    insta_graph.add_node("search_news", search_news_node)
    insta_graph.add_node("generate_post", generate_post_node)
    insta_graph.add_node("quality_check", quality_check_node)
    insta_graph.add_node("post_to_instagram", post_instagram_node)

    insta_graph.add_edge(START, "search_news")
    insta_graph.add_edge("search_news", "generate_post")
    insta_graph.add_edge("generate_post", "quality_check")
    insta_graph.add_conditional_edges("quality_check", route_quality, {
        "post_to_instagram": "post_to_instagram",
        "generate_post": "generate_post"
    })
    insta_graph.add_edge("post_to_instagram", END)
    return insta_graph.compile()


def search_news_node(state: AgentState):
    print("starting to search...")
    results = search_news()
    return {"search_results": results}


def generate_post_node(state: AgentState):
    print("DAY RECEIVED:", state["day_of_week"])
    print("starting to generate post...")
    memory = load_memory()
    last_question = memory.get("last_question", None)
    result = generate_post(
        state["search_results"],
        state["day_of_week"],
        last_question
    )
    print("GENERATED RESULT:", result)
    return {"generated_post": result}


def quality_check_node(state: AgentState):
    print("starting to quality check...")
    post = state["generated_post"]
    if not post:
        return {"quality_passed": False}
    memory = load_memory()
    current_urls = [article["url"] for article in state["search_results"]]
    already_posted = any(url in memory["posted_topics"] for url in current_urls)
    day = state["day_of_week"]
    if day == "Monday":
        passed = len(post) > 50 and "?" in post and not already_posted
    else:
        passed = len(post) > 50 and "ANSWER" in post and not already_posted
    print("POST:", post)
    print("LEN:", len(post))
    print("PASSED:", passed)
    return {"quality_passed": passed}


def post_instagram_node(state: AgentState):
    print("starting to post to insta...")
    post_to_instagram(state["generated_post"])
    save_memory(state["search_results"], state["generated_post"])
    return {"posted": True}