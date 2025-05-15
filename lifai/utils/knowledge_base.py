"""
Knowledge Base module for LifAi2.

Provides a multi-slot, vector-based knowledge management system with async file I/O,
singleton pattern, and FAISS-powered semantic search. Supports chunked document storage,
retrieval-augmented generation (RAG), and robust error handling.

Features:
    - Multiple named knowledge slots (General, Technical, Product, Support, Custom)
    - Async loading/saving of indexes and documents
    - Fast vector search using FAISS
    - Singleton pattern for global access
    - Intelligent text chunking and overlap handling
"""

from typing import List, Dict, Tuple
import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import re
import aiofiles
import asyncio
from lifai.utils.logger_utils import get_module_logger

logger = get_module_logger(__name__)

class Document:
    """Document class for storing content and metadata."""
    def __init__(self, page_content: str, metadata: dict = None):
        self.page_content = page_content
        self.metadata = metadata or {}

class KnowledgeBase:
    _instance = None
    _initialized = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, base_dir: str = "knowledge_base"):
        """Initialize the knowledge base with multiple slots
        
        Args:
            base_dir: Base directory for knowledge base
        """
        # Ensure singleton initialization
        if KnowledgeBase._initialized:
            return
            
        KnowledgeBase._initialized = True
        
        self.base_dir = base_dir
        self.slots = {}  # Dict to store multiple knowledge slots
        self.dimension = 1024  # bge-large-en-v1.5 dimension
        
        # Initialize embedding model
        self.model = SentenceTransformer('BAAI/bge-large-en-v1.5')
        
        # Create default slots
        self.slot_names = ["General", "Technical", "Product", "Support", "Custom"]
        for slot in self.slot_names:
            self._init_slot(slot)
            
        logger.info(f"Initialized knowledge base at {base_dir}")
        logger.info(f"Using model: BAAI/bge-large-en-v1.5")
        logger.info(f"Vector dimension: {self.dimension}")
        logger.info(f"Available slots: {', '.join(self.slot_names)}")

    def _init_slot(self, slot_name: str):
        """Initialize a knowledge slot
        
        Args:
            slot_name: Name of the slot to initialize
        """
        slot_dir = os.path.join(self.base_dir, slot_name.lower())
        docs_dir = os.path.join(slot_dir, "docs")
        index_dir = os.path.join(slot_dir, "index")
        
        # Ensure directories exist
        os.makedirs(docs_dir, exist_ok=True)
        os.makedirs(index_dir, exist_ok=True)
        
        # Initialize slot data structure
        self.slots[slot_name] = {
            'index': faiss.IndexFlatL2(self.dimension),
            'documents': [],
            'metadata': [],
            'use_ivf': False,
            'base_dir': slot_dir,
            'docs_dir': docs_dir,
            'index_dir': index_dir
        }
        
        # Load existing data for the slot
        self._load_slot_index(slot_name)

    async def _load_slot_index(self, slot_name: str):
        """
        Asynchronously load existing index and documents for a slot.
        Includes input validation and robust error handling.
        """
        if slot_name not in self.slots:
            logger.error(f"Invalid slot name: {slot_name}")
            return

        slot = self.slots[slot_name]
        index_file = os.path.join(slot['index_dir'], "faiss.index")
        docs_file = os.path.join(slot['index_dir'], "documents.json")

        try:
            if os.path.exists(index_file) and os.path.exists(docs_file):
                # Load FAISS index (still sync, as faiss does not support async)
                slot['index'] = faiss.read_index(index_file)
                slot['use_ivf'] = isinstance(slot['index'], faiss.IndexIVFFlat)

                # Load documents and metadata asynchronously
                async with aiofiles.open(docs_file, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    slot['documents'] = data['documents']
                    slot['metadata'] = data['metadata']

                logger.info(f"Loaded {len(slot['documents'])} documents from slot {slot_name}")
            else:
                logger.info(f"No existing index found for slot {slot_name}, starting fresh")

        except Exception as e:
            logger.error(f"Error loading index for slot {slot_name}: {e}")
            slot['index'] = faiss.IndexFlatL2(self.dimension)
            slot['use_ivf'] = False
            slot['documents'] = []
            slot['metadata'] = []

    async def _save_slot_index(self, slot_name: str):
        """
        Asynchronously save index and documents for a slot.
        Includes input validation and robust error handling.
        """
        if slot_name not in self.slots:
            logger.error(f"Invalid slot name: {slot_name}")
            return

        slot = self.slots[slot_name]
        try:
            # Save FAISS index (still sync, as faiss does not support async)
            index_file = os.path.join(slot['index_dir'], "faiss.index")
            faiss.write_index(slot['index'], index_file)

            # Save documents and metadata asynchronously
            docs_file = os.path.join(slot['index_dir'], "documents.json")
            async with aiofiles.open(docs_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps({
                    'documents': slot['documents'],
                    'metadata': slot['metadata']
                }, ensure_ascii=False, indent=2))

            logger.info(f"Saved {len(slot['documents'])} documents to slot {slot_name}")

        except Exception as e:
            logger.error(f"Error saving index for slot {slot_name}: {e}")

    def add_documents(self, texts: List[str], metadata_list: List[dict] = None, slot_name: str = "General"):
        """Add multiple documents to a specific knowledge slot
        
        Args:
            texts: List of texts to add
            metadata_list: List of metadata dictionaries
            slot_name: Name of the slot to add to (default: "General")
        """
        if slot_name not in self.slots:
            raise ValueError(f"Invalid slot name: {slot_name}")
            
        slot = self.slots[slot_name]
        
        try:
            if not texts:
                logger.warning(f"Attempted to add empty text list to slot {slot_name}")
                return
            
            # Ensure metadata_list matches texts length
            if metadata_list is None:
                metadata_list = [{}] * len(texts)
            elif len(metadata_list) != len(texts):
                raise ValueError("Length of texts and metadata_list must match")
            
            # Process each text
            for text, metadata in zip(texts, metadata_list):
                if not text.strip():
                    continue
                    
                # Split text into chunks
                sentences = self._split_text(text)
                if not sentences:
                    continue
                
                # Calculate embeddings
                embeddings = self.model.encode(sentences, convert_to_numpy=True)
                
                # Add to slot index
                self._batch_add_to_slot_index(slot_name, embeddings)
                
                # Save documents and metadata
                for sentence in sentences:
                    slot['documents'].append(sentence)
                    slot['metadata'].append(metadata)
            
            # Save changes
            self._save_slot_index(slot_name)
            
            logger.info(f"Added {len(texts)} documents to slot {slot_name}")
            
        except Exception as e:
            logger.error(f"Error adding documents to slot {slot_name}: {e}")
            raise

    def _batch_add_to_slot_index(self, slot_name: str, embeddings: np.ndarray):
        """Add vectors to a slot's index"""
        slot = self.slots[slot_name]
        try:
            # Check if we need to switch to IVF index
            if not slot['use_ivf'] and len(slot['documents']) >= 1000:
                logger.info(f"Switching slot {slot_name} to IVF index")
                ncentroids = min(int(len(slot['documents']) / 10), 100)
                quantizer = faiss.IndexFlatL2(self.dimension)
                new_index = faiss.IndexIVFFlat(quantizer, self.dimension, ncentroids)
                
                # Train new index
                if len(slot['documents']) > 0:
                    all_embeddings = self.model.encode(slot['documents'], convert_to_numpy=True)
                    new_index.train(all_embeddings)
                    new_index.add(all_embeddings)
                
                slot['index'] = new_index
                slot['use_ivf'] = True
                logger.info(f"Successfully switched slot {slot_name} to IVF index")
            
            # Add new vectors
            slot['index'].add(embeddings)
            logger.debug(f"Added {len(embeddings)} vectors to slot {slot_name}")
            
        except Exception as e:
            logger.error(f"Error adding vectors to slot {slot_name}: {e}")
            raise

    def get_context(self, query: str, slot_name: str = None, top_k: int = 5, threshold: float = 0.3) -> str:
        """Get relevant context from knowledge base
        
        Args:
            query: Query text to find relevant context for
            slot_name: Optional name of slot to search in. If None, searches all slots.
            top_k: Number of most relevant documents to return
            threshold: Minimum similarity score threshold
            
        Returns:
            String containing relevant context
        """
        try:
            if not query:
                return ""

            # Get query embedding
            query_embedding = self.model.encode([query], convert_to_numpy=True)

            results = []
            if slot_name:
                # Search in specific slot
                if slot_name not in self.slots:
                    logger.warning(f"Slot {slot_name} not found")
                    return ""
                slot = self.slots[slot_name]
                if not slot['documents']:
                    return ""
                    
                # Search in slot's index
                distances, indices = slot['index'].search(query_embedding, k=min(top_k, len(slot['documents'])))
                
                # Add results from this slot
                for dist, idx in zip(distances[0], indices[0]):
                    if idx < 0 or idx >= len(slot['documents']):
                        continue
                    similarity = 1 - (dist / 2)  # Convert L2 distance to similarity
                    if similarity >= threshold:
                        results.append((slot['documents'][idx], similarity))
            else:
                # Search in all slots
                for slot_name, slot in self.slots.items():
                    if not slot['documents']:
                        continue
                        
                    # Search in slot's index
                    distances, indices = slot['index'].search(query_embedding, k=min(top_k, len(slot['documents'])))
                    
                    # Add results from this slot
                    for dist, idx in zip(distances[0], indices[0]):
                        if idx < 0 or idx >= len(slot['documents']):
                            continue
                        similarity = 1 - (dist / 2)  # Convert L2 distance to similarity
                        if similarity >= threshold:
                            results.append((slot['documents'][idx], similarity))

            # Sort all results by similarity
            results.sort(key=lambda x: x[1], reverse=True)
            results = results[:top_k]

            if not results:
                logger.info("No relevant context found")
                return ""

            # Format results
            context_parts = []
            for doc, score in results:
                context_parts.append(f"Relevance {score:.2f}:\n{doc}")

            return "\n\n".join(context_parts)

        except Exception as e:
            logger.error(f"Error getting context: {e}")
            return ""

    def get_document_count(self, slot_name: str = None) -> Dict[str, int]:
        """Get document count for one or all slots
        
        Args:
            slot_name: Optional slot name to get count for
            
        Returns:
            Dict[str, int]: Mapping of slot names to document counts
        """
        try:
            if slot_name:
                if slot_name not in self.slots:
                    return {}
                return {slot_name: len(self.slots[slot_name]['documents'])}
            else:
                return {name: len(slot['documents']) for name, slot in self.slots.items()}
        except Exception as e:
            logger.error(f"Error getting document count: {e}")
            return {}

    def clear(self, slot_name: str = None):
        """Clear one or all knowledge slots
        
        Args:
            slot_name: Optional slot name to clear
        """
        try:
            if slot_name:
                if slot_name not in self.slots:
                    return
                slots_to_clear = [slot_name]
            else:
                slots_to_clear = list(self.slots.keys())
            
            for name in slots_to_clear:
                slot = self.slots[name]
                # Reset index
                slot['index'] = faiss.IndexFlatL2(self.dimension)
                slot['use_ivf'] = False
                slot['documents'] = []
                slot['metadata'] = []
                self._save_slot_index(name)
                
                # Delete files
                if os.path.exists(slot['index_dir']):
                    for file in os.listdir(slot['index_dir']):
                        file_path = os.path.join(slot['index_dir'], file)
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            logger.error(f"Error deleting file {file_path}: {e}")
            
            logger.info(f"Cleared {len(slots_to_clear)} knowledge slots")
            
        except Exception as e:
            logger.error(f"Error clearing knowledge base: {e}")

    def get_all_documents(self, slot_name: str = None) -> Dict[str, List[Document]]:
        """Get all documents from one or all slots
        
        Args:
            slot_name: Optional slot name to get documents from
            
        Returns:
            Dict[str, List[Document]]: Mapping of slot names to document lists
        """
        try:
            results = {}
            
            if slot_name:
                if slot_name not in self.slots:
                    return {}
                slots_to_get = [slot_name]
            else:
                slots_to_get = list(self.slots.keys())
            
            for name in slots_to_get:
                slot = self.slots[name]
                documents = []
                for content, metadata in zip(slot['documents'], slot['metadata']):
                    doc = Document(
                        page_content=content,
                        metadata=metadata
                    )
                    documents.append(doc)
                results[name] = documents
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting all documents: {e}")
            return {}

    def get_slot_names(self) -> List[str]:
        """Get list of available slot names"""
        return self.slot_names.copy()

    def reset(self):
        """Reset singleton state"""
        KnowledgeBase._instance = None
        KnowledgeBase._initialized = False

    def _split_text(self, text: str, chunk_size: int = 256, overlap: int = 100) -> List[str]:
        """Split text into chunks intelligently, preserving abbreviations
        
        Args:
            text: Text to split
            chunk_size: Maximum characters per chunk
            overlap: Number of overlapping characters between chunks
            
        Returns:
            List of sentence chunks
        """
        # First protect abbreviations
        protected_text = text
        abbreviations = re.findall(r'\b[A-Z]{2,}\b', text)
        placeholders = {}
        for i, abbr in enumerate(abbreviations):
            placeholder = f"__ABR{i}__"
            placeholders[placeholder] = abbr
            protected_text = protected_text.replace(abbr, placeholder)
        
        # Split into sentences
        sentences = []
        current_chunk = ""
        
        # Split by periods while keeping abbreviations intact
        parts = protected_text.split('.')
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            # Restore abbreviations
            for placeholder, abbr in placeholders.items():
                part = part.replace(placeholder, abbr)
            
            # If current chunk plus new sentence exceeds chunk size, save current chunk and start new one
            if len(current_chunk) + len(part) > chunk_size:
                if current_chunk:
                    sentences.append(current_chunk)
                current_chunk = part
            else:
                if current_chunk:
                    current_chunk += ". " + part
                else:
                    current_chunk = part
        
        # Add the last chunk
        if current_chunk:
            sentences.append(current_chunk)
        
        # Handle overlap
        if overlap > 0 and len(sentences) > 1:
            overlapped_sentences = []
            for i in range(len(sentences)):
                if i > 0:
                    # Take overlap characters from end of previous chunk
                    prev_end = sentences[i-1][-overlap:]
                    sentences[i] = prev_end + " " + sentences[i]
                overlapped_sentences.append(sentences[i])
            sentences = overlapped_sentences
        
        return sentences
 