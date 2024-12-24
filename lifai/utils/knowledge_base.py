from typing import List, Dict, Tuple
import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import re
from lifai.utils.logger_utils import get_module_logger

logger = get_module_logger(__name__)

class Document:
    """文档类，用于存储文档内容和元数据"""
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
        """初始化知识库
        
        Args:
            base_dir: 知识库基础目录
        """
        # 确保只初始化一次
        if KnowledgeBase._initialized:
            return
            
        KnowledgeBase._initialized = True
        
        self.base_dir = base_dir
        self.docs_dir = os.path.join(base_dir, "docs")
        self.index_dir = os.path.join(base_dir, "index")
        
        # 确保目录存在
        os.makedirs(self.docs_dir, exist_ok=True)
        os.makedirs(self.index_dir, exist_ok=True)
        
        # 初始化 embedding 模型
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # 初始化 FAISS 索引
        self.dimension = 384  # all-MiniLM-L6-v2 的维度
        # 对于小数据集，使用简单的 IndexFlatL2
        self.index = faiss.IndexFlatL2(self.dimension)
        self.use_ivf = False  # 标记是否使用 IVF 索引
        
        # 存储文档内容和元数据
        self.documents = []
        self.metadata = []
        
        # 加载现有索引和文档
        self._load_index()
        
        logger.info(f"Initialized knowledge base at {base_dir}")
        logger.info(f"Using model: all-MiniLM-L6-v2")
        logger.info(f"Vector dimension: {self.dimension}")
        logger.info(f"Current documents count: {len(self.documents)}")
        
    def reset(self):
        """重置单例状态，主要用于测试"""
        KnowledgeBase._instance = None
        KnowledgeBase._initialized = False
    
    def _split_text(self, text: str, chunk_size: int = 256, overlap: int = 100) -> List[str]:
        """智能分割文本，保留缩写词的完整性
        
        Args:
            text: 要分割的文本
            chunk_size: 每个块的最大字符数
            overlap: 块之间的重叠字符数
            
        Returns:
            分割后的句子列表
        """
        # 首先保护缩写词
        protected_text = text
        abbreviations = re.findall(r'\b[A-Z]{2,}\b', text)
        placeholders = {}
        for i, abbr in enumerate(abbreviations):
            placeholder = f"__ABR{i}__"
            placeholders[placeholder] = abbr
            protected_text = protected_text.replace(abbr, placeholder)
        
        # 分割成句子
        sentences = []
        current_chunk = ""
        
        # 按句号分割，但保持缩写词完整
        parts = protected_text.split('.')
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            # 恢复缩写词
            for placeholder, abbr in placeholders.items():
                part = part.replace(placeholder, abbr)
            
            # 如果当前块加上新句子超过了��大小，保存当前块并开始新块
            if len(current_chunk) + len(part) > chunk_size:
                if current_chunk:
                    sentences.append(current_chunk)
                current_chunk = part
            else:
                if current_chunk:
                    current_chunk += ". " + part
                else:
                    current_chunk = part
        
        # 添加最后一个块
        if current_chunk:
            sentences.append(current_chunk)
        
        # 处理重叠
        if overlap > 0 and len(sentences) > 1:
            overlapped_sentences = []
            for i in range(len(sentences)):
                if i > 0:
                    # 从前一个块的末尾取 overlap 个字符
                    prev_end = sentences[i-1][-overlap:]
                    sentences[i] = prev_end + " " + sentences[i]
                overlapped_sentences.append(sentences[i])
            sentences = overlapped_sentences
        
        return sentences
    
    def _batch_add_to_index(self, embeddings: np.ndarray):
        """分批添加向量到索引
        
        Args:
            embeddings: 要添加的向量
        """
        try:
            # 检查是否需要切换到 IVF 索引
            if not self.use_ivf and len(self.documents) >= 1000:
                logger.info("Switching to IVF index due to dataset size")
                # 创建新的 IVF 索引
                ncentroids = min(int(len(self.documents) / 10), 100)  # 动态设置聚类数
                quantizer = faiss.IndexFlatL2(self.dimension)
                new_index = faiss.IndexIVFFlat(quantizer, self.dimension, ncentroids)
                
                # 训练新索引
                if len(self.documents) > 0:
                    all_embeddings = self.model.encode(self.documents, convert_to_numpy=True)
                    new_index.train(all_embeddings)
                    new_index.add(all_embeddings)
                
                self.index = new_index
                self.use_ivf = True
                logger.info(f"Successfully switched to IVF index with {ncentroids} centroids")
            
            # 添加新的向量
            self.index.add(embeddings)
            logger.debug(f"Added batch of {len(embeddings)} vectors to index")
                
        except Exception as e:
            logger.error(f"Error adding vectors to index: {e}")
            raise
    
    def add_text(self, text: str, metadata: dict = None):
        """添加单个文本到知识库"""
        try:
            # 智能分割文本
            sentences = self._split_text(text)
            
            if not sentences:
                logger.warning("No valid sentences found in text")
                return
            
            # 计算嵌入向量
            embeddings = self.model.encode(sentences, convert_to_numpy=True)
            
            # 添加到索引
            self._batch_add_to_index(embeddings)
            
            # 保存文档和元数据
            for sentence in sentences:
                self.documents.append(sentence)
                self.metadata.append(metadata or {})
            
            # 保存更改
            self._save_index()
            
            logger.info(f"Added {len(sentences)} sentences to knowledge base")
            
        except Exception as e:
            logger.error(f"Error adding text: {e}")
    
    def add_documents(self, texts: List[str], metadata_list: List[dict] = None, collection_name: str = None):
        """添加多个文档到知识库
        
        Args:
            texts: 要添加的文本列表
            metadata_list: 文本对应的元数据列表
            collection_name: 集合名称（可选，用于兼容性）
        """
        try:
            if not texts:
                logger.warning("Attempted to add empty text list to knowledge base")
                return
            
            # 确保 metadata_list 和 texts 长度相同
            if metadata_list is None:
                metadata_list = [{}] * len(texts)
            elif len(metadata_list) != len(texts):
                raise ValueError("Length of texts and metadata_list must match")
            
            # 处理每个本
            for text, metadata in zip(texts, metadata_list):
                if not text.strip():
                    continue
                self.add_text(text, metadata)
            
            logger.info(f"Successfully added {len(texts)} documents to knowledge base")
            
        except Exception as e:
            logger.error(f"Error adding documents to knowledge base: {e}")
            raise
    
    def get_context(self, query: str, k: int = 20, threshold: float = 0.2) -> str:
        """获取与查询相关的上下文
        
        Args:
            query: 查询文本
            k: 返回的最相关文档数量
            threshold: 相似度阈值
            
        Returns:
            相关上下文文本
        """
        try:
            if not self.documents:
                logger.warning("Knowledge base is empty")
                return ""
            
            # 提取查询中的缩写词
            abbreviations = set(re.findall(r'\b[A-Z]{2,}\b', query))
            logger.info(f"Found abbreviations in query: {abbreviations}")
            
            # 计算查询的嵌入向量
            query_vector = self.model.encode([query], convert_to_numpy=True)
            
            # 搜索最相似的文档，增加检索数量以提高匹配概率
            distances, indices = self.index.search(query_vector, k=min(k * 3, len(self.documents)))
            
            # 构建上下文，优先考虑包含相同缩写词的文档
            context_parts = []
            seen_abbrs = set()  # 用于跟踪已处理的缩写词
            added_docs = set()  # 用于跟踪已添加的文档
            
            # 第一轮：优先添加包含任何查询缩写词的文档
            for dist, idx in zip(distances[0], indices[0]):
                doc = self.documents[idx]
                if doc in added_docs:
                    continue
                    
                similarity = 1 - (dist / 2)  # 转换距离为相似度
                if similarity < threshold:
                    continue
                
                # 检查文档中的缩写词
                doc_abbrs = set(re.findall(r'\b[A-Z]{2,}\b', doc))
                matching_abbrs = doc_abbrs.intersection(abbreviations)
                
                if matching_abbrs:
                    context_parts.append(
                        f"[Relevance: {similarity:.2%}]\n{doc}"
                    )
                    seen_abbrs.update(matching_abbrs)
                    added_docs.add(doc)
                    logger.info(f"Found relevant context with abbreviations {matching_abbrs}")
            
            # 第二轮：添加其他相关文档
            remaining_slots = k - len(context_parts)
            if remaining_slots > 0:
                for dist, idx in zip(distances[0], indices[0]):
                    if len(context_parts) >= k:
                        break
                        
                    doc = self.documents[idx]
                    if doc in added_docs:
                        continue
                        
                    similarity = 1 - (dist / 2)
                    if similarity >= threshold:
                        context_parts.append(
                            f"[Relevance: {similarity:.2%}]\n{doc}"
                        )
                        added_docs.add(doc)
                        logger.info(f"Found relevant context with similarity {similarity:.2%}")
            
            if not context_parts:
                logger.warning("No relevant context found")
                return ""
            
            # 记录未找到上下文的缩写词
            missing_abbrs = abbreviations - seen_abbrs
            if missing_abbrs:
                logger.warning(f"No context found for abbreviations: {missing_abbrs}")
            
            context = "\n\n---\n\n".join(context_parts)
            logger.info(f"Retrieved {len(context_parts)} relevant contexts")
            return context
            
        except Exception as e:
            logger.error(f"Error getting context: {e}")
            return ""
    
    def get_document_count(self) -> int:
        """获取知识库中的文档数量"""
        return len(self.documents)
    
    def clear(self):
        """清空知识库"""
        try:
            # 重新初始化为简单索引
            self.index = faiss.IndexFlatL2(self.dimension)
            self.use_ivf = False
            
            self.documents = []
            self.metadata = []
            self._save_index()
            logger.info("Knowledge base cleared")
            
            # 删除所有文件
            if os.path.exists(self.index_dir):
                for file in os.listdir(self.index_dir):
                    file_path = os.path.join(self.index_dir, file)
                    try:
                        os.remove(file_path)
                        logger.info(f"Deleted file: {file_path}")
                    except Exception as e:
                        logger.error(f"Error deleting file {file_path}: {e}")
                        
        except Exception as e:
            logger.error(f"Error clearing knowledge base: {e}")
            
    def get_all_documents(self) -> List[Document]:
        """获取知识库中的所有文档
        
        Returns:
            List[Document]: 文档列表，每个文档包含 page_content 和 metadata
        """
        try:
            # 构建文档对象列表
            documents = []
            for content, metadata in zip(self.documents, self.metadata):
                doc = Document(
                    page_content=content,
                    metadata=metadata
                )
                documents.append(doc)
            
            logger.info(f"Retrieved {len(documents)} documents from knowledge base")
            return documents
            
        except Exception as e:
            logger.error(f"Error getting all documents: {e}")
            return []
    
    def _load_index(self):
        """加载现有索引和文档"""
        index_file = os.path.join(self.index_dir, "faiss.index")
        docs_file = os.path.join(self.index_dir, "documents.json")
        
        try:
            if os.path.exists(index_file) and os.path.exists(docs_file):
                # 加载 FAISS 索引
                self.index = faiss.read_index(index_file)
                self.use_ivf = isinstance(self.index, faiss.IndexIVFFlat)
                
                # 加载文档和元数据
                with open(docs_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.documents = data['documents']
                    self.metadata = data['metadata']
                
                logger.info(f"Loaded {len(self.documents)} documents from existing index")
            else:
                logger.info("No existing index found, starting fresh")
                # 使用简单索引开始
                self.index = faiss.IndexFlatL2(self.dimension)
                self.use_ivf = False
                
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            logger.warning("Starting with fresh index")
            # 使用简单索引开始
            self.index = faiss.IndexFlatL2(self.dimension)
            self.use_ivf = False
            self.documents = []
            self.metadata = []
    
    def _save_index(self):
        """保存索引和文档"""
        try:
            # 保存 FAISS 索引
            index_file = os.path.join(self.index_dir, "faiss.index")
            faiss.write_index(self.index, index_file)
            
            # 保存文档和元数据
            docs_file = os.path.join(self.index_dir, "documents.json")
            with open(docs_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'documents': self.documents,
                    'metadata': self.metadata
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved {len(self.documents)} documents to index")
            
        except Exception as e:
            logger.error(f"Error saving index: {e}")
    
    def delete_document(self, doc_id: int) -> bool:
        """删除指定的文档
        
        Args:
            doc_id: 文档ID（索引）
            
        Returns:
            bool: 是否成功删除
        """
        try:
            if 0 <= doc_id < len(self.documents):
                # 删除文档和元数据
                del self.documents[doc_id]
                del self.metadata[doc_id]
                
                # 重建索引
                self.index = faiss.IndexIVFFlat(self.quantizer, self.dimension, 100)
                self.index.nprobe = 10
                
                if self.documents:
                    # 重新计算所有文档的嵌入向量
                    embeddings = self.model.encode(self.documents, convert_to_numpy=True)
                    self._batch_add_to_index(embeddings)
                
                # 保存更改
                self._save_index()
                
                logger.info(f"Successfully deleted document {doc_id}")
                return True
            else:
                logger.warning(f"Invalid document ID: {doc_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return False
    
    def delete_documents(self, doc_ids: List[int]) -> bool:
        """删除多个文档
        
        Args:
            doc_ids: 要删除的文档ID列表
            
        Returns:
            bool: 是否全部成功删除
        """
        try:
            # 验证所有ID是否有效
            if not all(0 <= doc_id < len(self.documents) for doc_id in doc_ids):
                logger.warning("Some document IDs are invalid")
                return False
            
            # 按降序排序以避免删除时的索引问题
            for doc_id in sorted(doc_ids, reverse=True):
                del self.documents[doc_id]
                del self.metadata[doc_id]
            
            # 重建索引
            self.index = faiss.IndexIVFFlat(self.quantizer, self.dimension, 100)
            self.index.nprobe = 10
            
            if self.documents:
                # 重新计算所有文档的嵌入向量
                embeddings = self.model.encode(self.documents, convert_to_numpy=True)
                self._batch_add_to_index(embeddings)
            
            # 保存更改
            self._save_index()
            
            logger.info(f"Successfully deleted {len(doc_ids)} documents")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            return False
    
    def search_documents(self, query: str, k: int = 10) -> List[Tuple[int, str, float]]:
        """搜索文档并返回文档ID、内容和相似度
        
        Args:
            query: 搜索查询
            k: 返回的结果数量
            
        Returns:
            List[Tuple[int, str, float]]: 文档ID、内容和相似度的列表
        """
        try:
            if not self.documents:
                return []
            
            # 计算查询向量
            query_vector = self.model.encode([query], convert_to_numpy=True)
            
            # 搜索最相似的文档
            distances, indices = self.index.search(query_vector, k=min(k, len(self.documents)))
            
            # 构建结果
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                similarity = 1 - (dist / 2)
                results.append((idx, self.documents[idx], similarity))
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
 