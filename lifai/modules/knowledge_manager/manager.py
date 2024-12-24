from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                            QTextEdit, QLabel, QFileDialog, QMessageBox, QTabWidget,
                            QTableWidget, QTableWidgetItem)
from PyQt6.QtCore import Qt
from typing import Dict
import json
import os
from lifai.utils.knowledge_base import KnowledgeBase
from lifai.utils.logger_utils import get_module_logger

logger = get_module_logger(__name__)

class KnowledgeManagerWindow(QWidget):
    def __init__(self, settings: Dict):
        super().__init__()
        self.settings = settings
        self.knowledge_base = KnowledgeBase()
        self.setup_ui()
        self.hide()
        
    def setup_ui(self):
        """Setup the UI components"""
        self.setWindowTitle("Knowledge Base Manager")
        self.resize(1000, 800)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 添加知识标签页
        add_tab = QWidget()
        add_layout = QVBoxLayout()
        add_tab.setLayout(add_layout)
        
        # 添加文档区域
        doc_layout = QHBoxLayout()
        
        # 左侧：文本输入
        input_layout = QVBoxLayout()
        input_layout.addWidget(QLabel("Add Knowledge:"))
        self.input_text = QTextEdit()
        input_layout.addWidget(self.input_text)
        
        # 添加按钮
        add_button = QPushButton("Add to Knowledge Base")
        add_button.clicked.connect(self.add_knowledge)
        input_layout.addWidget(add_button)
        
        doc_layout.addLayout(input_layout)
        
        # 右侧：元数据输入
        metadata_layout = QVBoxLayout()
        metadata_layout.addWidget(QLabel("Metadata (JSON):"))
        self.metadata_text = QTextEdit()
        self.metadata_text.setPlaceholderText('{\n    "category": "abbreviation",\n    "department": "engineering"\n}')
        metadata_layout.addWidget(self.metadata_text)
        
        doc_layout.addLayout(metadata_layout)
        
        add_layout.addLayout(doc_layout)
        
        # 导入/导出按钮
        button_layout = QHBoxLayout()
        
        import_file_button = QPushButton("Import from File")
        import_file_button.clicked.connect(self.import_from_file)
        button_layout.addWidget(import_file_button)
        
        import_folder_button = QPushButton("Import from Folder")
        import_folder_button.clicked.connect(self.import_from_folder)
        button_layout.addWidget(import_folder_button)
        
        add_layout.addLayout(button_layout)
        
        # 查看知识标签页
        view_tab = QWidget()
        view_layout = QVBoxLayout()
        view_tab.setLayout(view_layout)
        
        # 创建表格
        self.knowledge_table = QTableWidget()
        self.knowledge_table.setColumnCount(3)
        self.knowledge_table.setHorizontalHeaderLabels(["Content", "Metadata", "Source"])
        self.knowledge_table.horizontalHeader().setStretchLastSection(True)
        view_layout.addWidget(self.knowledge_table)
        
        # 刷新按钮
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_knowledge_table)
        view_layout.addWidget(refresh_button)
        
        # 添加标签页
        tab_widget.addTab(add_tab, "Add Knowledge")
        tab_widget.addTab(view_tab, "View Knowledge")
        
        layout.addWidget(tab_widget)
        
        # 初始加载知识库内容
        self.refresh_knowledge_table()
        
    def refresh_knowledge_table(self):
        """刷新知识库内容表格"""
        try:
            # 获取所有文档
            docs = self.knowledge_base.get_all_documents()
            
            # 设置表格行数
            self.knowledge_table.setRowCount(len(docs))
            
            # 填充表格
            for i, doc in enumerate(docs):
                # 内容
                content_item = QTableWidgetItem(doc.page_content)
                content_item.setToolTip(doc.page_content)  # 添加工具提示
                self.knowledge_table.setItem(i, 0, content_item)
                
                # 元数据
                metadata_str = json.dumps(doc.metadata, ensure_ascii=False, indent=2)
                metadata_item = QTableWidgetItem(metadata_str)
                metadata_item.setToolTip(metadata_str)  # 添加工具提示
                self.knowledge_table.setItem(i, 1, metadata_item)
                
                # 来源
                source = doc.metadata.get('source', 'Manual Input')
                source_item = QTableWidgetItem(source)
                source_item.setToolTip(source)  # 添加工具提示
                self.knowledge_table.setItem(i, 2, source_item)
            
            # 调整列宽
            self.knowledge_table.resizeColumnsToContents()
            
            # 更新状态
            logger.info(f"Loaded {len(docs)} documents from knowledge base")
            
        except Exception as e:
            logger.error(f"Error refreshing knowledge table: {e}")
            self.show_error(f"Failed to refresh knowledge table: {e}")

    def add_knowledge(self):
        """添加知识到知识库"""
        text = self.input_text.toPlainText().strip()
        if not text:
            self.show_error("Please enter some text")
            return
            
        try:
            metadata = json.loads(self.metadata_text.toPlainText() or '{}')
        except json.JSONDecodeError:
            self.show_error("Invalid metadata JSON format")
            return
            
        try:
            self.knowledge_base.add_documents([text], [metadata])
            self.input_text.clear()
            self.metadata_text.clear()
            self.refresh_knowledge_table()  # 刷新表格
            QMessageBox.information(self, "Success", "Knowledge added successfully!")
        except Exception as e:
            self.show_error(f"Failed to add knowledge: {e}")
            
    def import_from_file(self):
        """从文件导入知识"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File to Import",
            "",
            "Text Files (*.txt);;JSON Files (*.json);;All Files (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if file_path.endswith('.json'):
                data = json.loads(content)
                if isinstance(data, list):
                    texts = [item.get('content', '') for item in data]
                    metadata = [{'source': file_path, **item.get('metadata', {})} 
                              for item in data]
                else:
                    texts = [data.get('content', '')]
                    metadata = [{'source': file_path, **data.get('metadata', {})}]
            else:
                texts = [content]
                metadata = [{'source': file_path}]
                
            self.knowledge_base.add_documents(texts, metadata)
            self.refresh_knowledge_table()  # 刷新表格
            QMessageBox.information(self, "Success", "File imported successfully!")
            
        except Exception as e:
            self.show_error(f"Failed to import file: {e}")
            
    def import_from_folder(self):
        """从文件夹导入知识"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Import"
        )
        
        if not folder_path:
            return
            
        try:
            imported = 0
            for root, _, files in os.walk(folder_path):
                for file in files:
                    if file.endswith(('.txt', '.json')):
                        file_path = os.path.join(root, file)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        if file.endswith('.json'):
                            try:
                                data = json.loads(content)
                                if isinstance(data, list):
                                    texts = [item.get('content', '') for item in data]
                                    metadata = [{'source': file_path, **item.get('metadata', {})} 
                                              for item in data]
                                else:
                                    texts = [data.get('content', '')]
                                    metadata = [{'source': file_path, **data.get('metadata', {})}]
                            except json.JSONDecodeError:
                                texts = [content]
                                metadata = [{'source': file_path}]
                        else:
                            texts = [content]
                            metadata = [{'source': file_path}]
                            
                        self.knowledge_base.add_documents(texts, metadata)
                        imported += len(texts)
            
            self.refresh_knowledge_table()  # 刷新表格
            QMessageBox.information(self, "Success", 
                                  f"Imported {imported} documents successfully!")
            
        except Exception as e:
            self.show_error(f"Failed to import folder: {e}")
            
    def show_error(self, message: str):
        """显示错误消息"""
        QMessageBox.critical(self, "Error", message)
        
    def show(self):
        """显示窗口"""
        super().show()
        self.raise_()
        
    def hide(self):
        """隐藏窗口"""
        super().hide() 