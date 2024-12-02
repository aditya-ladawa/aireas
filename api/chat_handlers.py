from langchain_groq import ChatGroq
from dotenv import load_dotenv

from langgraph.prebuilt import create_react_agent
from api.team_tools import tavily_search_tool, arxiv_search_tool
from api.qdrant_cloud_ops import initialize_selfquery_retriever, qdrant_vector_store
from api.token_counter import tiktoken_counter
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage, trim_messages



load_dotenv()

# chains.py
from .llm_chains import assign_chat_topic

llm = ChatGroq(model='llama-3.1-70b-versatile')

assign_chat_topic_chain = assign_chat_topic(llm=llm)



trimmer = trim_messages(
    max_tokens=5984,
    strategy="last",
    token_counter=tiktoken_counter,
    include_system=True,
    allow_partial=False,
)

qdrant_retriever = initialize_selfquery_retriever(llm, qdrant_vector_store=qdrant_vector_store)
qdrant_retriever_tool = qdrant_retriever.as_tool(
    name="retrieve_research_paper_texts",
    description="Search and return information from the vector database containing texts of several research papers, and scholarly articles",
)
react_agent = create_react_agent(model=llm, tools=[qdrant_retriever_tool, arxiv_search_tool, tavily_search_tool])

