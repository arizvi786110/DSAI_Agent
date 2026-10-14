import os
import re
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END

from generate_post import (
    ANSWER_SLIDE,
    QUESTION_SLIDE,
    generate_carousel,
    render_image,
    send_to_make,
)
from memory import load_memory, save_memory
from tools import search_news

load_dotenv()

POST_DAYS = {"Monday"}  
MAX_ATTEMPTS = 3         


class AgentState(TypedDict):
    day_of_week: str
    search_results: list
    generated_post: str
    post: dict           # parsed {statement, is_true, explanation, source}
    quality_passed: bool
    attempts: int
    posted: bool
    posted_topics: list




def route_start(state: AgentState):
    if state["day_of_week"] in POST_DAYS or os.getenv("FORCE_RUN") == "1":
        return "search_news"
    print(f"{state['day_of_week']} is not a posting day, stopping.")
    return END


def route_search(state: AgentState):
    if state["search_results"]:
        return "generate_post"
    print("No new articles found, stopping.")
    return END


def route_quality(state: AgentState):
    if state["quality_passed"]:
        return "post_to_instagram"
    if state.get("attempts", 0) >= MAX_ATTEMPTS:
        print(f"Giving up after {MAX_ATTEMPTS} attempts.")
        return END
    return "generate_post"


def search_news_node(state: AgentState):
    print("starting to search...")
    memory = load_memory()
    already_posted = set(memory.get("posted_topics", []))
    articles = search_news() or []
    fresh = [
        a for a in articles
        if a.get("url") and a["url"] not in already_posted and a.get("title")
    ]
    print(f"Found {len(articles)} articles, {len(fresh)} not posted before")
    return {"search_results": fresh}


PROMPT = """You are the social media manager for a university Data Science and AI society.
Write ONE "Fact or Fiction?" statement for an Instagram carousel, based on one of these recent news articles.

{articles}

Rules:
- The statement must be about AI, data science or machine learning, and interesting to university students.
- Decide whether to make it TRUE (accurately reflects the article) or FALSE (a plausible-sounding twist on it). Mix it up.
- The statement must be at most 25 words and must NOT end with a question mark.
- The explanation must be at most 30 words, state what is actually true, and not start with "True" or "False".
- SOURCE is the number of the article you used.

Return exactly this format and nothing else:
STATEMENT: <statement>
ANSWER: <TRUE or FALSE>
EXPLANATION: <explanation>
SOURCE: <number>"""


def _format_articles(articles):
    lines = []
    for i, a in enumerate(articles, start=1):
        desc = (a.get("description") or "").strip()
        lines.append(f"{i}. {a['title']}\n   {desc}")
    return "\n".join(lines)


def _parse(text):
    """Pull the four fields out of the LLM response. Returns None if malformed."""
    fields = {}
    for key in ("STATEMENT", "ANSWER", "EXPLANATION", "SOURCE"):
        match = re.search(rf"^{key}:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
        if not match:
            return None
        fields[key] = match.group(1).strip()

    answer = fields["ANSWER"].upper().strip("[]. ")
    if answer not in ("TRUE", "FALSE"):
        return None
    try:
        source = int(re.sub(r"\D", "", fields["SOURCE"])) - 1
    except ValueError:
        return None

    return {
        "statement": fields["STATEMENT"].rstrip("?").strip(),
        "is_true": answer == "TRUE",
        "explanation": fields["EXPLANATION"],
        "source": source,
    }


def generate_post_node(state: AgentState):
    attempts = state.get("attempts", 0) + 1
    print(f"starting to generate post (attempt {attempts})...")
    model = ChatGroq(
        model_name="llama-3.3-70b-versatile",
        temperature=0.7,
        api_key=os.getenv("GROQ_API_KEY"),
    )
    prompt = PROMPT.format(articles=_format_articles(state["search_results"]))
    response = model.invoke([HumanMessage(content=prompt)])
    text = response.content
    print("GENERATED RESULT:", text)
    return {"generated_post": text, "post": _parse(text) or {}, "attempts": attempts}


def quality_check_node(state: AgentState):
    print("starting to quality check...")
    post = state.get("post") or {}

    if not post:
        print("FAILED: response not in the expected format")
        return {"quality_passed": False}

    if not 0 <= post["source"] < len(state["search_results"]):
        print("FAILED: source number out of range")
        return {"quality_passed": False}

    if len(post["statement"]) < 20 or len(post["explanation"]) < 20:
        print("FAILED: statement or explanation too short")
        return {"quality_passed": False}

   
    verdict = "TRUE" if post["is_true"] else "FALSE"
    try:
        render_image(post["statement"], QUESTION_SLIDE, "output_question.png")
        render_image(post["explanation"], ANSWER_SLIDE, "output_answer.png", heading=verdict)
    except ValueError as e:
        print("FAILED:", e)
        return {"quality_passed": False}

    print("PASSED")
    return {"quality_passed": True}


def post_instagram_node(state: AgentState):
    print("starting to post to insta...")
    post = state["post"]
    article = state["search_results"][post["source"]]

    question_url, answer_url = generate_carousel(
        question=post["statement"],
        answer_is_true=post["is_true"],
        explanation=post["explanation"],
    )
    print("question_url:", question_url)
    print("answer_url:", answer_url)

    caption = (
        "Fact or fiction? 🤔 Comment TRUE or FALSE, then swipe to check 👉\n\n"
        f"Based on: {article['title']}\n\n"
        "#DataScience #AI #MachineLearning #FactOrFiction"
    )
    send_to_make(question_url, answer_url, caption)

    save_memory([article], post["statement"])
    return {"posted": True}


def build_graph():
    insta_graph = StateGraph(AgentState)
    insta_graph.add_node("search_news", search_news_node)
    insta_graph.add_node("generate_post", generate_post_node)
    insta_graph.add_node("quality_check", quality_check_node)
    insta_graph.add_node("post_to_instagram", post_instagram_node)

    insta_graph.add_conditional_edges(START, route_start, {
        "search_news": "search_news",
        END: END,
    })
    insta_graph.add_conditional_edges("search_news", route_search, {
        "generate_post": "generate_post",
        END: END,
    })
    insta_graph.add_edge("generate_post", "quality_check")
    insta_graph.add_conditional_edges("quality_check", route_quality, {
        "post_to_instagram": "post_to_instagram",
        "generate_post": "generate_post",
        END: END,
    })
    insta_graph.add_edge("post_to_instagram", END)
    return insta_graph.compile()