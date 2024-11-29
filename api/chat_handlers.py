from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

# chains.py
from .llm_chains import assign_chat_topic

llm = ChatGroq(model='llama-3.1-70b-versatile')

assign_chat_topic_chain = assign_chat_topic(llm=llm)
# print(assign_chat_topic_chain.invoke('i am researching on gravitons and how gravity affects ANTImatter'))