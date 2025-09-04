import os
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
import PyPDF2

# ---- Env keys ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


# ---- Data path ----
BASE_DIR = Path(__file__).resolve().parents[1]  # .../authapi/
PDF_DIR  = BASE_DIR / "data" / "pdfs"

# ---- Global state ----
retriever = None
current_llm_config = {"provider": "google", "model": "gemini-1.5-flash"}

def load_pdfs_return_docs(pdf_dir: Path):
    """Loads all PDFs from directory and returns LangChain Document objects."""
    docs = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        try:
            reader = PyPDF2.PdfReader(str(pdf_path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if text.strip():
                docs.append(
                    Document(page_content=text, metadata={"source": str(pdf_path.name)})
                )
        except Exception as e:
            print(f"[RAG] Failed reading {pdf_path.name}: {e}")
    return docs

def build_retriever():
    """Builds and caches the retriever from PDFs."""
    global retriever
    if retriever is not None:
        return retriever

    docs = load_pdfs_return_docs(PDF_DIR)
    if not docs:
        raise RuntimeError(f"No PDFs found in {PDF_DIR}. Put files there.")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)
    chunks = splitter.split_documents(docs)

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectordb   = FAISS.from_documents(chunks, embeddings)
    retriever  = vectordb.as_retriever(search_kwargs={"k": 5})
    return retriever

def get_llm(provider: str, model_name: str):
    if provider == "openai":
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY missing")
        llm = ChatOpenAI(model=model_name, temperature=0)
        return llm, f"OpenAI/{model_name}"
    if provider == "groq":
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY missing")
        llm = ChatGroq(model_name=model_name, temperature=0)
        return llm, f"Groq/{model_name}"
    if provider == "google":
        if not GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY missing")
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
        return llm, f"Google/{model_name}"
    raise ValueError("Unknown provider")

def create_rag_chain(provider: str, model_name: str):
    r = build_retriever()

    prompt = PromptTemplate(
        template="""
You are a helpful assistant.
Answer ONLY from the provided document context.
If the context is insufficient, say you don't know.
You are a company assistant and will assist the fellow employee in Bangla if the user writes in Bangla, otherwise answer in English.
Be descriptive, use bullet points where helpful, and point to where more info can be found in the PDF.

Context:
{context}

Question: {question}
""",
        input_variables=["context", "question"],
    )

    def format_docs(retrieved_docs):
        return "\n\n".join(d.page_content for d in retrieved_docs if d.page_content)

    llm, llm_desc = get_llm(provider, model_name)

    chain = (
        {"context": r | RunnableLambda(format_docs), "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain, llm_desc

def llm_options() -> Dict[str, Any]:
    return {
        "providers": {
            "openai":  {"models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1"], "default": "gpt-4o-mini"},
            "groq":    {"models": ["llama-3.1-70b-versatile", "mixtral-8x7b-32768"], "default": "llama-3.1-70b-versatile"},
            "google":  {"models": ["gemini-1.5-flash", "gemini-1.5-pro"], "default": "gemini-1.5-flash"},
        },
        "current": current_llm_config,
    }

def set_default_llm(provider: str, model: str) -> Dict[str, str]:
    global current_llm_config
    _llm, desc = get_llm(provider, model)
    current_llm_config = {"provider": provider, "model": model}
    return {"provider": provider, "model": model, "description": desc}

def answer_question(question: str, provider: Optional[str], model_name: Optional[str]) -> Tuple[str, str]:
    p = provider or current_llm_config["provider"]
    m = model_name or current_llm_config["model"]
    chain, desc = create_rag_chain(p, m)
    answer = chain.invoke(question)
    return answer, desc
