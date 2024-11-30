from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing_extensions import List, Optional, Union, TypedDict, Literal, Dict, Literal, Annotated
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import trim_messages
from .token_counter import tiktoken_counter
from langchain.schema import SystemMessage, HumanMessage




class DecomposedQuestion(TypedDict):
    """
    Represents decomposed sub-questions.
    """
    sub_questions: Annotated[
        Optional[List[str]], 
        "A list of sub-questions derived from the original question."
    ]

class RephrasedQuestion(TypedDict):
    """
    Represents rephrased question.
    """
    rephrased_question: Annotated[
        Optional[str], 
        "A rephrased version of the original question."
    ]

class DecompositionCheck(TypedDict):
    """
    For evaluating whether a question needs to be decomposed into simple, isolated, answerable sub-questions.
    """
    needs_decomposition: Annotated[Literal["Decompose", "Rephrase"], "Evaluation of whether the question needs to be decomposed into simpler sub-questions."
    ]



def dec_parser(task_list: List[str]) -> str:
    """
    Parses a list of tasks, removing any empty or whitespace-only strings,
    and returns a single string with tasks separated by commas.

    Parameters:
    - task_list (list): The list of task strings to be parsed.

    Returns:
    - str: A non-empty, comma-separated string of tasks.
    """
    parsed_task = ', '.join(filter(lambda x: x.strip() != '', task_list))
    return parsed_task


def decomposition_chain(llm):
    """
    Creates a chain for decomposing questions into sub-questions or rephrasing the question.
    
    Parameters:
    - llm: The language model instance.

    Returns:
    - callable: A callable chain that performs question decomposition.
    """
    template = """You are an assistant that decomposes complex questions into simpler, isolated sub-questions.

    Your task is to break down the given question into the smallest possible set of essential sub-problems or sub-questions, with a maximum limit of 3 sub-questions.
    ### Important and strict note: Break down the question into sub-questions **only if it improves clarity or retrieval efficiency**. If the question can be directly answered or requires only one or two sub-questions, do not force it into three sub-questions.

    Each sub-question should:
    1. Be independently answerable.
    2. Be necessary to address the original question.
    3. Be formulated in a way that enhances the efficiency of the retrieval process.

    Respond only with the sub-questions, separated by a newline.

    Question: {question}
    """

    structured_output_llm = llm.with_structured_output(DecomposedQuestion)

    decomposition_prompt = ChatPromptTemplate.from_template(template)

    generate_queries_decomposition = (
        decomposition_prompt 
        | structured_output_llm 
        | (lambda x: dec_parser(x["sub_questions"]).lower())
    )
    return generate_queries_decomposition


def requires_decomposition(llm):
    template = """You are an assistant that evaluates whether a given question should be decomposed into simpler, isolated sub-questions.

    Your task is to determine if the given question needs to be broken down. 
    - Answer "Decompose" if the question is complex, multi-faceted, or requires multiple retrieval tasks to answer.
    - Answer "Rephrase" if the question is straightforward or can be answered directly without decomposition.

    Question: {question}
    """

    structured_output_llm = llm.with_structured_output(DecompositionCheck)

    decomposition_prompt = ChatPromptTemplate.from_template(template)

    evaluate_decomposition = decomposition_prompt | structured_output_llm | (lambda x: x["needs_decomposition"])

    return evaluate_decomposition


def rephrase_chain(llm):
    template = """You are an assistant tasked with rephrasing complex or unclear questions into simpler, clearer, and more direct versions while preserving the original meaning.
    
    Your goal is to improve the clarity and search efficiency of the input question for document retrieval systems like web search, Arxiv, or other knowledge databases. You should focus on:
    
    1. Making the question more concise and to the point.
    2. Retaining key domain-specific terms that are necessary for accurate retrieval (e.g., technical terms, scientific terms).
    3. Simplifying sentence structures, but ensuring that the question targets the core aspect of the query.
    4. Replacing general or vague phrasing with more specific, searchable keywords.
    5. Making sure that the question is actionable, targeting a clear and direct search outcome.

    If the question includes technical or scientific terms, leave them as they are but ensure they are used effectively for search efficiency. Do not introduce ambiguity.

    The rephrased question should be well-suited for searching in databases like Arxiv, Google Scholar, or other document retrieval systems.

    Question: {question}
    """

    structured_output_llm = llm.with_structured_output(RephrasedQuestion)
    
    rephrasing_prompt = ChatPromptTemplate.from_template(template)
    
    rephrase_chain = (
        rephrasing_prompt 
        | structured_output_llm 
        | (lambda x: x["rephrased_question"].lower())
    )
    
    return rephrase_chain


def get_plan_chain(llm):
    few_shot_rewoo = """
        You will be given a simple question or sub-questions separated by commas that are decomposed from the original question. For each question, develop a series of sequential plans that specify exactly which agents to use to retrieve the necessary evidence. Format each plan in the following way:

        Format:
        Plan: [Provide a concise description of the intended action, including any specific sources, search queries, or steps that must be followed. Reference any evidence needed from previous steps.]
        #E[number] = [Agent[Specific Query/Input, including any references to previous #E results if applicable]]

        Use the minimum number of plans necessary to provide an accurate and relevant answer. Each plan should be followed by only one #E, with clear sequential ordering for reference by subsequent steps.
        Strictly provide output only. Provide a complete plan that addresses all questions as a whole, instead of creating individual plans for each question.

        Agents Available:
        - RagSearcher[input]: Uses a vector database to retrieve relevant documents or research papers based on prior knowledge or pre-embedded content (use for tasks related to research papers in the form of PDFs or topics embedded in the database).
        - Searcher[input]: Conducts searches via Tavily search, Web Scraper, or Arxiv Search to retrieve both general web information and academic papers from online sources.
        - Coder[input]: A code-execution agent using Python REPL for tasks requiring code, data analysis, or visualizations.
        - ChatBot[input]: Processes or generates natural language responses based on gathered evidence or specific input.

        ### Instructions on Considering Conversation History:
        - Incorporate relevant information or context from past messages when creating plans.
        - If past messages contain partial results, instructions, or clarifications, ensure they are factored into the plan and appropriately referenced in queries.
        - Summarize past messages, if necessary, to create precise and well-informed agent queries.

        ### Advice:
        - When creating each plan, ensure that the query given to the agent precisely reflects the questions received and leverages any relevant conversation history or past messages. Optimize the query for vectorDB retrieval, web search, or Arxiv search accordingly.

        ### Examples
        Task: Summarize recent advancements in Video Transformers for action recognition tasks.
        Plan: Search for recent publications on Arxiv that discuss Video Transformers for action recognition using the Searcher agent. #E1 = Searcher[Video Transformers action recognition]
        Plan: Retrieve related research papers on Video Transformers stored in the vector database using the RagSearcher agent. #E2 = RagSearcher[Video Transformers action recognition]
        Plan: Use the retrieved documents to generate a summary highlighting advancements in the use of Video Transformers for action recognition. #E3 = ChatBot[Summarize #E1, #E2]

        Task: Analyze the importance of GAN metrizability for improved performance in generative models.
        Plan: Search Arxiv for recent studies on GAN metrizability and its impact on generative model performance using the Searcher agent. #E1 = Searcher[GAN metrizability and generative models]
        Plan: Retrieve any embedded research on GAN metrizability from the vector database using the RagSearcher agent. #E2 = RagSearcher[GAN metrizability in generative models]
        Plan: Summarize findings on why metrizability is significant for GAN performance based on the retrieved papers. #E3 = ChatBot[Summarize #E1, #E2]

    Task: {task}
    """

    trimmer = trim_messages(
        max_tokens=5984,
        strategy="last",
        token_counter=tiktoken_counter,
        include_system=True,
        allow_partial=False,
    )

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ('system', few_shot_rewoo),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )
    # prompt_template = ChatPromptTemplate.from_template(few_shot_rewoo)

    planner = prompt_template | trimmer | llm | (lambda x: x.content)
    return planner



def assign_chat_topic(llm):

    template = """
        "You are an expert in assigning concise topics to conversations. The user provides their focus area, "
        "and you assign a relevant topic in 5 words or less. "
        "Here is the user's input:\n\n"
        f"{user_input}\n\n"
        "What is the best topic for this conversation? Provide only the topic without any extra text."
    """

    prompt_template = ChatPromptTemplate.from_template(template=template)

    assign_chat_topic_chain = prompt_template | llm | (lambda x: x.content)

    return assign_chat_topic_chain
