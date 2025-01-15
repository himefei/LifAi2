from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                            QTextEdit, QLabel, QFileDialog, QMessageBox, QTabWidget,
                            QTableWidget, QTableWidgetItem, QComboBox)
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
        
        # Create tabs
        tab_widget = QTabWidget()
        
        # Add knowledge tab
        add_tab = QWidget()
        add_layout = QVBoxLayout()
        add_tab.setLayout(add_layout)
        
        # Add slot selection
        slot_layout = QHBoxLayout()
        slot_layout.addWidget(QLabel("Knowledge Slot:"))
        self.slot_combo = QComboBox()
        self.slot_combo.addItems(self.knowledge_base.get_slot_names())
        slot_layout.addWidget(self.slot_combo)
        add_layout.addLayout(slot_layout)
        
        # Add document area
        doc_layout = QHBoxLayout()
        
        # Left side: text input
        input_layout = QVBoxLayout()
        input_layout.addWidget(QLabel("Add Knowledge:"))
        self.input_text = QTextEdit()
        input_layout.addWidget(self.input_text)
        
        # Add button
        add_button = QPushButton("Add to Knowledge Base")
        add_button.clicked.connect(self.add_knowledge)
        input_layout.addWidget(add_button)
        
        doc_layout.addLayout(input_layout)
        
        # Right side: metadata input
        metadata_layout = QVBoxLayout()
        metadata_layout.addWidget(QLabel("Metadata (JSON):"))
        self.metadata_text = QTextEdit()
        self.metadata_text.setPlaceholderText('{\n    "category": "abbreviation",\n    "department": "engineering"\n}')
        metadata_layout.addWidget(self.metadata_text)
        
        doc_layout.addLayout(metadata_layout)
        
        add_layout.addLayout(doc_layout)
        
        # Import/export buttons
        button_layout = QHBoxLayout()
        
        import_file_button = QPushButton("Import from File")
        import_file_button.clicked.connect(self.import_from_file)
        button_layout.addWidget(import_file_button)
        
        import_folder_button = QPushButton("Import from Folder")
        import_folder_button.clicked.connect(self.import_from_folder)
        button_layout.addWidget(import_folder_button)
        
        add_layout.addLayout(button_layout)
        
        # View knowledge tab
        view_tab = QWidget()
        view_layout = QVBoxLayout()
        view_tab.setLayout(view_layout)
        
        # Add slot selection for viewing
        view_slot_layout = QHBoxLayout()
        view_slot_layout.addWidget(QLabel("View Slot:"))
        self.view_slot_combo = QComboBox()
        self.view_slot_combo.addItems(["All"] + self.knowledge_base.get_slot_names())
        self.view_slot_combo.currentTextChanged.connect(self.refresh_knowledge_table)
        view_slot_layout.addWidget(self.view_slot_combo)
        view_layout.addLayout(view_slot_layout)
        
        # Create table
        self.knowledge_table = QTableWidget()
        self.knowledge_table.setColumnCount(4)  # Added Slot column
        self.knowledge_table.setHorizontalHeaderLabels(["Slot", "Content", "Metadata", "Source"])
        self.knowledge_table.horizontalHeader().setStretchLastSection(True)
        view_layout.addWidget(self.knowledge_table)
        
        # Add button layout
        button_layout = QHBoxLayout()
        
        # Refresh button
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_knowledge_table)
        button_layout.addWidget(refresh_button)
        
        # Delete selected button
        delete_selected_button = QPushButton("Delete Selected")
        delete_selected_button.clicked.connect(self.delete_selected)
        button_layout.addWidget(delete_selected_button)
        
        # Clear slot button
        clear_slot_button = QPushButton("Clear Selected Slot")
        clear_slot_button.clicked.connect(self.clear_selected_slot)
        button_layout.addWidget(clear_slot_button)
        
        # Clear all button
        clear_all_button = QPushButton("Clear All")
        clear_all_button.clicked.connect(self.clear_knowledge_base)
        button_layout.addWidget(clear_all_button)
        
        view_layout.addLayout(button_layout)
        
        # Add tabs
        tab_widget.addTab(add_tab, "Add Knowledge")
        tab_widget.addTab(view_tab, "View Knowledge")
        
        layout.addWidget(tab_widget)
        
        # Initial load of knowledge base content
        self.refresh_knowledge_table()
        
    def refresh_knowledge_table(self):
        """Refresh knowledge base content table"""
        try:
            # Get selected slot
            selected_slot = self.view_slot_combo.currentText()
            
            # Get documents based on selection
            if selected_slot == "All":
                docs_by_slot = self.knowledge_base.get_all_documents()
            else:
                docs_by_slot = self.knowledge_base.get_all_documents(selected_slot)
            
            # Calculate total rows
            total_rows = sum(len(docs) for docs in docs_by_slot.values())
            self.knowledge_table.setRowCount(total_rows)
            
            # Fill table
            current_row = 0
            for slot_name, docs in docs_by_slot.items():
                for doc in docs:
                    # Slot
                    slot_item = QTableWidgetItem(slot_name)
                    self.knowledge_table.setItem(current_row, 0, slot_item)
                    
                    # Content
                    content_item = QTableWidgetItem(doc.page_content)
                    content_item.setToolTip(doc.page_content)
                    self.knowledge_table.setItem(current_row, 1, content_item)
                    
                    # Metadata
                    metadata_str = json.dumps(doc.metadata, ensure_ascii=False, indent=2)
                    metadata_item = QTableWidgetItem(metadata_str)
                    metadata_item.setToolTip(metadata_str)
                    self.knowledge_table.setItem(current_row, 2, metadata_item)
                    
                    # Source
                    source = doc.metadata.get('source', 'Manual Input')
                    source_item = QTableWidgetItem(source)
                    source_item.setToolTip(source)
                    self.knowledge_table.setItem(current_row, 3, source_item)
                    
                    current_row += 1
            
            # Adjust column widths
            self.knowledge_table.resizeColumnsToContents()
            
            # Update status
            logger.info(f"Loaded {total_rows} documents from knowledge base")
            
        except Exception as e:
            logger.error(f"Error refreshing knowledge table: {e}")
            self.show_error(f"Failed to refresh knowledge table: {e}")

    def add_knowledge(self):
        """Add knowledge to knowledge base"""
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
            slot_name = self.slot_combo.currentText()
            self.knowledge_base.add_documents([text], [metadata], slot_name)
            self.input_text.clear()
            self.metadata_text.clear()
            self.refresh_knowledge_table()
            QMessageBox.information(self, "Success", f"Knowledge added successfully to slot {slot_name}!")
        except Exception as e:
            self.show_error(f"Failed to add knowledge: {e}")

    def import_from_file(self):
        """Import knowledge from file"""
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
                
            slot_name = self.slot_combo.currentText()
            self.knowledge_base.add_documents(texts, metadata, slot_name)
            self.refresh_knowledge_table()
            QMessageBox.information(self, "Success", f"File imported successfully to slot {slot_name}!")
            
        except Exception as e:
            self.show_error(f"Failed to import file: {e}")

    def import_from_folder(self):
        """Import knowledge from folder"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Import"
        )
        
        if not folder_path:
            return
            
        try:
            imported = 0
            slot_name = self.slot_combo.currentText()
            
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
                            
                        self.knowledge_base.add_documents(texts, metadata, slot_name)
                        imported += len(texts)
            
            self.refresh_knowledge_table()
            QMessageBox.information(self, "Success", 
                                  f"Imported {imported} documents to slot {slot_name} successfully!")
            
        except Exception as e:
            self.show_error(f"Failed to import folder: {e}")

    def clear_selected_slot(self):
        """Clear the selected knowledge slot"""
        slot_name = self.view_slot_combo.currentText()
        if slot_name == "All":
            self.show_error("Please select a specific slot to clear")
            return
            
        confirm = QMessageBox.question(
            self,
            "Confirm Clear Slot",
            f"Are you sure you want to clear the entire {slot_name} slot? This action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.knowledge_base.clear(slot_name)
                self.refresh_knowledge_table()
                QMessageBox.information(self, "Success", f"Knowledge slot {slot_name} cleared successfully!")
            except Exception as e:
                self.show_error(f"Error clearing knowledge slot: {e}")

    def clear_knowledge_base(self):
        """Clear the entire knowledge base"""
        confirm = QMessageBox.question(
            self,
            "Confirm Clear All",
            "Are you sure you want to clear ALL knowledge slots? This action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.knowledge_base.clear()
                self.refresh_knowledge_table()
                QMessageBox.information(self, "Success", "All knowledge slots cleared successfully!")
            except Exception as e:
                self.show_error(f"Error clearing knowledge base: {e}")

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
        
    def delete_selected(self):
        """删除选中的知识条目"""
        selected_rows = set(item.row() for item in self.knowledge_table.selectedItems())
        if not selected_rows:
            self.show_error("Please select items to delete")
            return
            
        # 确认删除
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete {len(selected_rows)} selected items?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                # 将行号转换为列表并排序
                rows_to_delete = sorted(list(selected_rows))
                # 删除文档
                success = self.knowledge_base.delete_documents(rows_to_delete)
                
                if success:
                    self.refresh_knowledge_table()
                    QMessageBox.information(self, "Success", "Selected items deleted successfully!")
                else:
                    self.show_error("Failed to delete some items")
                    
            except Exception as e:
                self.show_error(f"Error deleting items: {e}")
                
    def clear_selected_slot(self):
        """Clear the selected knowledge slot"""
        slot_name = self.view_slot_combo.currentText()
        if slot_name == "All":
            self.show_error("Please select a specific slot to clear")
            return
            
        confirm = QMessageBox.question(
            self,
            "Confirm Clear Slot",
            f"Are you sure you want to clear the entire {slot_name} slot? This action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.knowledge_base.clear(slot_name)
                self.refresh_knowledge_table()
                QMessageBox.information(self, "Success", f"Knowledge slot {slot_name} cleared successfully!")
            except Exception as e:
                self.show_error(f"Error clearing knowledge slot: {e}") 