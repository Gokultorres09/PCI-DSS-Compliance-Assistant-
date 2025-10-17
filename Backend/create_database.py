import json
from sentence_transformers import SentenceTransformer
import chromadb

PCI_DATA_FILE = "pci_data.json"
DB_PATH = "pci_vector_db"
COLLECTION_NAME = "pci_requirements"

# 1. Load the sentence transformer model
print("Loading embedding model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

# 2. Load your PCI data
print("Loading PCI data...")
with open(PCI_DATA_FILE, 'r', encoding='utf-8') as f:
    pci_data = json.load(f)

documents = list(pci_data.values())
metadatas = [{"source": req_num} for req_num in pci_data.keys()]
ids = list(pci_data.keys())

# 3. Create embeddings
print("Creating embeddings (this may take a moment)...")
embeddings = model.encode(documents)

# 4. Set up the ChromaDB client and collection
client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection(name=COLLECTION_NAME)

# 5. Add the data to the collection
print(f"Adding {len(documents)} documents to the vector database...")
collection.add(
    embeddings=embeddings,
    documents=documents,
    metadatas=metadatas,
    ids=ids
)

print(f"✅ Vector database created successfully in the '{DB_PATH}' directory.")