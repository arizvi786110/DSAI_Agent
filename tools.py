import requests
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage


def search_news():
    load_dotenv()
    apiKey = os.getenv("NEWS_API_KEY")
    params = {
        "q": "artificial intelligence OR data science OR machine learning",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 5,
        "apiKey": apiKey,
    }
    response = requests.get("https://newsapi.org/v2/everything", params=params)
    return response.json()["articles"]

def generate_post(articles, day, last_question):
    load_dotenv()
    if day == "Monday":
        temperature = 0.7
        prompt = f"""You are a social media manager for a university AI and data science society. Based on these recent AI news articles, create an Instagram poll post.
State something as either a FACT or MYTH for followers to guess.
Articles: {articles}
Return your response in exactly this format:
QUESTION: One sentence statement ending in a question mark asking if its a fact or myth
OPTION A: Fact
OPTION B: Myth
ANSWER: [Fact or Myth]
Do not add any extra text outside this format"""
        model = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=temperature,
            api_key=os.getenv("GROQ_API_KEY")
        )

    elif day == "Tuesday":
        temperature = 0.1
        prompt = f"""You are a social media manager for a university AI and data science society.
Based on the article given and the question that has been made, return the correct answer.
Articles: {articles}
Return your response in exactly this format:
QUESTION: {last_question}
ANSWER: [Fact or Myth]
EXPLANATION: [a simple explanation]
Do not add any extra text outside this format"""
        model = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=temperature,
            api_key=os.getenv("GROQ_API_KEY")
        )
    else:
        return None

    response = model.invoke([HumanMessage(content=prompt)])
    return response.content


def post_to_instagram(generate_post):
    load_dotenv()
    webhook_url = os.getenv("MAKE_WEBHOOK_URL")
    payload = {
        "question": generate_post,
        "options": ["Fact", "Myth"],
        "media_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1e/Artificial_intelligence_prompt_engineer.jpg/1280px-Artificial_intelligence_prompt_engineer.jpg"
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(webhook_url, json=payload, headers=headers)
    return response.text