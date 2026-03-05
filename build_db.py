import pandas as pd
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
import os
import shutil

# --- Configuration ---
# Paths to the Excel source files
FILE_QUESTIONS = "data/Questions-Export-2025-October-27-1237.xlsx"
FILE_TUTOS = "data/Tutoriels-Export-2025-October-27-1244.xlsx"
FILE_VIDEOS = "data/Videos-Export-2025-October-27-1248.xlsx"

# Path where the Vector Database will be persisted
DB_PATH = "./chroma_db"

def load_and_process_data():
    """
    Reads Excel files (Questions, Tutorials, Videos) and converts them into 
    LangChain Document objects.

    Returns:
        list[Document]: A list of processed documents ready for embedding.
    """
    docs = []

    # 1. Process Questions (FAQ)
    print("Chargement des Questions...")
    try:
        df_q = pd.read_excel(FILE_QUESTIONS)
        for _, row in df_q.iterrows():
            # Mapping: Excel 'Title' -> Question context, 'Content' -> Answer
            content = f"Question: {row['Title']}\nRéponse: {row['Content']}"
            meta = {
                "type": "faq", 
                "source": "FAQ Étudiants", 
                "id": str(row['id'])
            }
            docs.append(Document(page_content=content, metadata=meta))
    except Exception as e:
        print(f"[WARN] Erreur lecture Questions: {e}")

    # 2. Process Tutorials
    print("Chargement des Tutoriels...")
    try:
        df_t = pd.read_excel(FILE_TUTOS)
        for _, row in df_t.iterrows():
            # Tutorials often contain HTML content in 'Content'
            content = f"Tutoriel: {row['Title']}\nDescription: {row['Content']}"
            meta = {
                "type": "tuto", 
                "source": "Tutoriels", 
                "id": str(row['id'])
            }
            docs.append(Document(page_content=content, metadata=meta))
    except Exception as e:
        print(f"[WARN] Erreur lecture Tutos: {e}")

    # 3. Process Videos
    print("Chargement des Vidéos...")
    try:
        df_v = pd.read_excel(FILE_VIDEOS)
        for _, row in df_v.iterrows():
            content = f"Vidéo: {row['Title']}\nDescription: {row['Content']}"
            meta = {
                "type": "video", 
                "source": "Vidéothèque", 
                "id": str(row['id'])
            }
            docs.append(Document(page_content=content, metadata=meta))
    except Exception as e:
        print(f"[WARN] Erreur lecture Vidéos: {e}")

    return docs

def create_vector_db():
    """
    Main function to rebuild the Vector Database.
    1. Clears existing DB.
    2. Loads documents.
    3. Generates embeddings using 'all-MiniLM-L6-v2'.
    4. Persists the new DB to disk.
    """
    # Clear old database
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)
        print(f"Nettoyage de l'ancienne base : {DB_PATH}")

    # Load documents
    documents = load_and_process_data()
    print(f"DEBUG: Nombre de documents chargés: {len(documents)}")
    
    if not documents:
        print("[ERROR] AUCUN DOCUMENT TROUVÉ ! Vérifiez les fichiers Excel.")
        return
    
    print(f"[INFO] Création des embeddings pour {len(documents)} documents...")

    # Initialize Embedding Model (Free, Local, CPU-friendly)
    embedding_function = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    # Create and persist ChromaDB
    Chroma.from_documents(
        documents=documents,
        embedding=embedding_function,
        persist_directory=DB_PATH
    )
    print(f"[SUCCESS] Base de données vectorielle créée avec succès dans {DB_PATH} !")

if __name__ == "__main__":
    create_vector_db()
