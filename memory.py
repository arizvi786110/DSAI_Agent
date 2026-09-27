import json
import os

def save_memory(articles, question):
    memory= load_memory()
    memory["last_question"]= question
    if articles:
        memory["posted_topics"].append(articles[0]["url"])
    with open("agent_memory.json","w") as f:
        json.dump(memory,f)

def load_memory():
    if os.path.exists("agent_memory.json"):
        with open("agent_memory.json","r") as f:
            return json.load(f)
    else:
        return{"last_question":None, "posted_topics":[]}
