from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Langchain / LLM imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

# Load environment variables
load_dotenv()

# --- Configuration ---
DB_PATH = "./chroma_db"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# Threshold for similarity. Higher value = more lenient (since distance is L2).
# Tuned to 1.3 based on testing.
SIMILARITY_THRESHOLD = 1.3 

# Global variables
vector_db = None
llm = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for the FastAPI app.
    Loads the Vector Database on startup.
    """
    global vector_db, llm
    print("[INFO] Initialisation de la base de données vectorielle et du LLM...")
    try:
        # 1. Connect Vector DB
        embedding_function = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        vector_db = Chroma(persist_directory=DB_PATH, embedding_function=embedding_function)
        print("[SUCCESS] Base de données vectorielle chargée.")
        
        # 2. Connect LLM
        google_api_key = os.environ.get("GOOGLE_API_KEY")
        if not google_api_key or google_api_key == "votre_cle_api_ici":
             print("[WARN] GOOGLE_API_KEY manquante ou invalide dans .env. L'IA générative sera désactivée.")
        else:
             # Using gemini-2.5-flash which is free and fast. Temperature 0.5 for more natural conversation.
             llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.5)
             print("[SUCCESS] Connexion au modèle Gemini LLM établie.")

    except Exception as e:
        print(f"[ERROR] Erreur lors de l'initialisation : {e}")
        vector_db = None
        llm = None
    yield
    # Cleanup if needed (nothing for now)

app = FastAPI(lifespan=lifespan)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Data Models ---
class Message(BaseModel):
    role: str # 'user' or 'assistant'
    content: str
    
class ChatRequest(BaseModel):
    question: str
    history: list[Message] = [] # Ajout de l'historique

class ChatResponse(BaseModel):
    answer_html: str
    source: str
    is_fallback: bool

# --- Helper Functions ---

def search_and_rerank(query: str, k: int = 3):
    """
    Searches the Vector DB for the top 'k' results.
    Apply a re-ranking logic to prioritize Tutorials/Videos if they are close
    matches, as they often provide better "How-To" answers than FAQs.
    """
    if not vector_db:
        return None, None

    # 1. Get raw results from ChromaDB
    results = vector_db.similarity_search_with_score(query, k=k)
    if not results:
        return None, None

    # 2. Pick the best result initially
    best_doc, best_score = results[0]

    # 3. Re-ranking: Check if a Video/Tuto is close to the top result (within 0.2 score difference)
    # If the top result is a FAQ but a Tuto is almost as good, we prefer the Tuto.
    for i in range(1, len(results)):
        candidate_doc, candidate_score = results[i]
        
        doc_type = candidate_doc.metadata.get("type")
        if doc_type in ["tuto", "video"]:
             # Lower score = better match (distance)
             if candidate_score <= best_score + 0.2:
                 print(f"DEBUG: Re-ranking! Promoting {doc_type} (Score {candidate_score:.4f}) over {best_doc.metadata.get('type')} (Score {best_score:.4f})")
                 best_doc = candidate_doc
                 best_score = candidate_score
                 # Stop after promoting the first relevant rich content
                 break 
    
    return best_doc, best_score

def format_answer(doc) -> tuple[str, str]:
    """
    Extracts and filters the best displayable answer from the document.
    Returns: (answer_html, source_name)
    """
    content = doc.page_content
    meta = doc.metadata
    doc_type = meta.get("type", "faq")
    source = meta.get("source", "Inconnu")
    
    answer_text = content
    answer_html = ""

    # Strategy varies by document type
    if doc_type == "faq":
        # Format: "Question: ... \nRéponse: ..."
        if "Réponse:" in content:
            answer_text = content.split("Réponse:", 1)[1].strip()
        # For FAQ, convert newlines to <br> for basic readability
        answer_html = answer_text.replace("\n", "<br>")

    elif doc_type in ["tuto", "video"]:
        # Format: "Tutoriel: ... \nDescription: ..."
        if "Description:" in content:
            # We trust that the Tutorial/Video content is already HTML
            # (imported from the 'Content' column of the Excel which had HTML)
            answer_text = content.split("Description:", 1)[1].strip()
        
        # Do NOT escape newlines for HTML content to strictly preserve structure
        answer_html = answer_text

    else:
        # Fallback for unknown types
        answer_html = answer_text.replace("\n", "<br>")

    return answer_html, source

def get_fallback_response(query: str = ""):
    """Returns the standardized 'No Answer Found' response and logs the query."""
    
    # -- NOUVEAU: Boucle d'auto-apprentissage (Logging) --
    if query:
        log_unanswered_query(query)
        
    return ChatResponse(
        answer_html="<p>Je ne trouve pas de réponse pertinente à votre question.</p>"
                    "<p>Voulez-vous :</p>"
                    "<ul>"
                    "<li><a href='mailto:support@esilv.fr'>Envoyer un email</a></li>"
                    "<li><a href='https://help.esilv.fr/contact' target='_blank'>Remplir le formulaire</a></li>"
                    "</ul>",
        source="Assistant / Fallback",
        is_fallback=True
    )

def log_unanswered_query(query: str):
    """
    Saves unanswered queries to an Excel file to improve the dataset later.
    """
    filename = "data/unanswered_queries.xlsx"
    os.makedirs("data", exist_ok=True)
    
    print(f"[INFO] Logging unanswered query for auto-learning: '{query}'")
    try:
        import pandas as pd
        from datetime import datetime
        
        new_row = pd.DataFrame([{
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Question": query
        }])
        
        if os.path.exists(filename):
            # Append
            existing_df = pd.read_excel(filename)
            updated_df = pd.concat([existing_df, new_row], ignore_index=True)
            updated_df.to_excel(filename, index=False)
        else:
            # Create new
            new_row.to_excel(filename, index=False)
            
    except Exception as e:
        print(f"[ERROR] Failed to log unanswered query: {e}")
        
def generate_llm_response(question: str, history: list, context_text: str) -> str:
    """
    Uses the Gemini LLM to formulate a response based on history and retrieved context.
    """
    if not llm:
        print("[WARN] LLM not initialized. Falling back to exact extraction.")
        return context_text
        
    # Format history for the prompt
    history_str = ""
    if history:
        history_str = "Historique de la conversation :\n"
        # Take only the last 4 exchanges to avoid exploding context size
        for msg in history[-4:]:
            role_name = "Étudiant" if msg.role == "user" else "Assistant"
            history_str += f"{role_name}: {msg.content}\n"
            
    prompt_template = """
    Tu es l'Assistant Virtuel du Help Center de l'ESILV. Ton but est d'accompagner les étudiants d'une manière très naturelle, chaleureuse et humaine.
    
    Règles de comportement:
    1. CONVERSATIONNEL : Ne te contente JAMAIS de copier-coller la documentation. Tu dois l'interpréter et l'expliquer avec tes propres mots, comme si tu parlais à un étudiant en face de toi.
    2. STRUCTURE DE TA RÉPONSE :
       - Commence toujours par une petite formule de politesse amicale en lien avec la question (ex: "Bien sûr, voici comment faire !", "Pas de souci, je vais t'expliquer.").
       - Donne ensuite les explications ou les étapes clairement en t'appuyant sur la documentation.
       - Termine par une phrase chaleureuse (ex: "J'espère que c'est plus clair !", "N'hésite pas si tu bloques à une étape.").
    3. FORMATAGE : Utilise le format HTML (paragraphes <p>, listes <ul>/<li>, gras <strong>) pour rendre ta réponse agréable à lire. Si la documentation contient déjà du HTML pertinent (comme des liens ou iframes de vidéos), réutilise ces balises exactes dans ton explication.
    4. VÉRITÉ : Basse-toi uniquement sur la "Documentation de référence trouvée". Si la réponse n'y est pas, dis-le honnêtement.
    5. HISTORIQUE : Prends en compte l'historique de la conversation pour ajuster ta réponse si c'est une question de suivi.
    6.Soit poli et respectueux envers l'étudiant.
    {history_str}
    
    Documentation de référence trouvée :
    ===========
    {context}
    ===========
    
    Question de l'étudiant : {question}
    
    Ta réponse conversationnelle au format HTML :
    """
    
    prompt = PromptTemplate(
        input_variables=["history_str", "context", "question"],
        template=prompt_template
    )
    
    chain = prompt | llm
    
    try:
        response = chain.invoke({
            "history_str": history_str,
            "context": context_text,
            "question": question
        })
        return response.content.strip()
    except Exception as e:
        print(f"[ERROR] LLM Generation failed: {e}")
        return context_text # Fallback to raw text if API fails

# --- Routes ---

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    API Endpoint handling the user question.
    """
    if not vector_db:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    query = request.question
    print(f"[INFO] Question reçue : {query}")

    # 1. Search
    best_doc, score = search_and_rerank(query)

    # 2. Check Validity
    if not best_doc:
        return get_fallback_response(query)
    
    print(f"[DEBUG] Meilleur match : Type={best_doc.metadata.get('type')} | Score={score:.4f}")

    # 3. Check Threshold (is it relevant enough?)
    if score > SIMILARITY_THRESHOLD:
        print("[WARN] Score trop élevé (résultat non pertinent). Fallback.")
        return get_fallback_response(query)

    # 4. Format Answer (Extraction brute initiale)
    extracted_text, source = format_answer(best_doc)
    
    # 5. LLM Synthesis (RAG)
    # If the document is a big tutorial video html block, we might just return it or let the LLM wrap it.
    # To keep tutorials intact, we pass them as context to the LLM.
    print("[INFO] Génération de la réponse via LLM Gemini...")
    final_html_answer = generate_llm_response(
        question=query, 
        history=request.history, 
        context_text=extracted_text
    )

    return ChatResponse(
        answer_html=final_html_answer,
        source=source,
        is_fallback=False
    )

# Serve Frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
