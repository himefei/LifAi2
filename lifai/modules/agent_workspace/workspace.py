from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QTabWidget, QTextEdit, QPushButton, QComboBox,
                            QLabel, QProgressBar, QFrame, QLineEdit, QFormLayout,
                            QMessageBox, QGroupBox)
from PyQt6.QtCore import Qt
from typing import Dict
import requests
import json
import os

from lifai.utils.ollama_client import OllamaClient
from lifai.utils.logger_utils import get_module_logger

logger = get_module_logger(__name__)

class AgentWorkspaceWindow(QMainWindow):
    def __init__(self, settings: Dict, ollama_client: OllamaClient):
        super().__init__()
        self.settings = settings
        self.ollama_client = ollama_client
        
        # Load API settings
        self.config_file = os.path.join(os.path.dirname(__file__), 'config.json')
        self.api_settings = self.load_api_settings()
        
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        self.setup_ui()
        self.hide()

    def setup_ui(self):
        """Setup the main UI components"""
        self.setWindowTitle("Agent Workspace")
        self.resize(1200, 800)
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Create tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Add workspace tabs
        tabs.addTab(self.create_task_tab(), "Task Planning")
        tabs.addTab(self.create_tools_tab(), "Tools & Skills")
        tabs.addTab(self.create_memory_tab(), "Memory & Knowledge")
        tabs.addTab(self.create_monitoring_tab(), "Monitoring")

    def create_task_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Task input group
        input_group = QGroupBox("Task Input")
        input_layout = QVBoxLayout(input_group)
        
        # Task input area
        self.task_input = QTextEdit()
        self.task_input.setPlaceholderText("Enter your task or goal here...")
        input_layout.addWidget(self.task_input)
        
        layout.addWidget(input_group)
        
        # Control group
        control_group = QGroupBox("Task Control")
        control_layout = QHBoxLayout(control_group)
        
        # Agent type selector
        control_layout.addWidget(QLabel("Agent Type:"))
        self.agent_types = QComboBox()
        self.agent_types.addItems(["Account Manager", "Research Agent", "Repeat Scrubbing"])
        control_layout.addWidget(self.agent_types)
        
        # Execute button
        execute_btn = QPushButton("Execute Task")
        execute_btn.clicked.connect(self.execute_task)
        control_layout.addWidget(execute_btn)
        
        layout.addWidget(control_group)
        
        # Progress group
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        layout.addWidget(progress_group)
        
        # Output group
        output_group = QGroupBox("Task Output")
        output_layout = QVBoxLayout(output_group)
        self.task_output = QTextEdit()
        self.task_output.setReadOnly(True)
        output_layout.addWidget(self.task_output)
        
        layout.addWidget(output_group)
        
        return widget

    def create_tools_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Search Engine Selection Group
        engine_group = QGroupBox("Search Engine Selection")
        engine_layout = QVBoxLayout(engine_group)
        
        self.search_engine = QComboBox()
        self.search_engine.addItems(["SearXNG", "Google Custom Search", "Bing Search"])
        self.search_engine.setCurrentText(self.api_settings.get('search_engine', 'SearXNG'))
        self.search_engine.currentTextChanged.connect(self.on_search_engine_change)
        engine_layout.addWidget(self.search_engine)
        layout.addWidget(engine_group)
        
        # SearXNG Settings
        self.searxng_group = QGroupBox("SearXNG Settings")
        searxng_layout = QFormLayout(self.searxng_group)
        
        self.searxng_instance = QComboBox()
        self.searxng_instance.setEditable(True)
        self.searxng_instance.addItems([
            'https://searx.thegpm.org',
            'https://searx.tiekoetter.com',
            'https://searx.fmac.xyz',
            'https://searx.be'
        ])
        self.searxng_instance.setCurrentText(self.api_settings.get('searxng_instance', 'https://searx.thegpm.org'))
        searxng_layout.addRow("Instance URL:", self.searxng_instance)
        layout.addWidget(self.searxng_group)
        
        # Google API Settings
        self.google_group = QGroupBox("Google Custom Search Settings")
        google_layout = QFormLayout(self.google_group)
        
        self.google_api_key = QLineEdit()
        self.google_api_key.setText(self.api_settings.get('google_api_key', ''))
        self.google_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        google_layout.addRow("API Key:", self.google_api_key)
        
        self.google_cx = QLineEdit()
        self.google_cx.setText(self.api_settings.get('google_cx', ''))
        google_layout.addRow("Search Engine ID:", self.google_cx)
        layout.addWidget(self.google_group)
        
        # Bing API Settings
        self.bing_group = QGroupBox("Bing Search Settings")
        bing_layout = QFormLayout(self.bing_group)
        
        self.bing_api_key = QLineEdit()
        self.bing_api_key.setText(self.api_settings.get('bing_api_key', ''))
        self.bing_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        bing_layout.addRow("API Key:", self.bing_api_key)
        layout.addWidget(self.bing_group)
        
        # Common Settings
        common_group = QGroupBox("Common Settings")
        common_layout = QFormLayout(common_group)
        
        self.results_count = QComboBox()
        self.results_count.addItems(['5', '10', '15', '20'])
        self.results_count.setCurrentText(str(self.api_settings.get('results_count', 5)))
        common_layout.addRow("Results Count:", self.results_count)
        layout.addWidget(common_group)
        
        # Add save and test buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_api_config)
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self.test_search_connection)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(test_btn)
        layout.addLayout(button_layout)
        
        # Status label
        self.test_status = QLabel("Status: Not tested")
        layout.addWidget(self.test_status)
        
        # Show/hide appropriate settings based on current selection
        self.on_search_engine_change(self.search_engine.currentText())
        
        layout.addStretch()
        return widget

    def on_search_engine_change(self, engine):
        """Show/hide settings based on selected search engine"""
        self.searxng_group.setVisible(engine == "SearXNG")
        self.google_group.setVisible(engine == "Google Custom Search")
        self.bing_group.setVisible(engine == "Bing Search")

    def create_memory_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Memory Management - Coming Soon"))
        return widget

    def create_monitoring_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Agent Monitoring - Coming Soon"))
        return widget

    def load_api_settings(self):
        """Load API settings from config file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading API settings: {e}")
        return {
            'searxng_instance': 'https://searx.be',  # Default public instance
            'results_count': 5
        }

    def save_api_settings(self):
        """Save API settings to config file"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.api_settings, f, indent=4)
            logger.info("API settings saved successfully")
        except Exception as e:
            logger.error(f"Error saving API settings: {e}")

    def test_search_connection(self):
        """Test connection to selected search engine"""
        engine = self.search_engine.currentText()
        try:
            if engine == "Google Custom Search":
                if not (self.google_api_key.text() and self.google_cx.text()):
                    raise Exception("Google API credentials not configured")
                results = self.google_search("test")
                success = len(results) > 0
                
            elif engine == "Bing Search":
                if not self.bing_api_key.text():
                    raise Exception("Bing API key not configured")
                results = self.bing_search("test")
                success = len(results) > 0
                
            else:  # SearXNG
                instance_url = self.searxng_instance.currentText().strip()
                
                # Basic parameters without format specification
                params = {
                    'q': 'test',
                    'language': 'en'
                }
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
                
                response = requests.get(
                    instance_url,
                    params=params,
                    headers=headers,
                    timeout=10
                )
                response.raise_for_status()
                success = True
                
            if success:
                self.test_status.setText(f"Status: {engine} connection successful ✓")
                self.test_status.setStyleSheet("color: green")
                logger.info(f"{engine} connection test successful")
            else:
                raise Exception("No results returned")
                
        except Exception as e:
            error_msg = str(e)
            if '403' in error_msg:
                error_msg = "Access forbidden. Check API credentials or try a different instance."
            elif '404' in error_msg:
                error_msg = "Service not found. Check the URL or endpoint."
            elif 'timeout' in error_msg.lower():
                error_msg = "Connection timed out. Service might be down."
                
            self.test_status.setText(f"Status: Connection failed ✗ ({error_msg})")
            self.test_status.setStyleSheet("color: red")
            logger.error(f"{engine} connection test failed: {e}")

    def save_api_config(self):
        """Save API configuration"""
        self.api_settings.update({
            'search_engine': self.search_engine.currentText(),
            'searxng_instance': self.searxng_instance.currentText(),
            'google_api_key': self.google_api_key.text(),
            'google_cx': self.google_cx.text(),
            'bing_api_key': self.bing_api_key.text(),
            'results_count': int(self.results_count.currentText())
        })
        self.save_api_settings()
        QMessageBox.information(self, "Success", "Settings saved successfully!")

    def searxng_search(self, query: str) -> list:
        """Perform search using SearXNG"""
        try:
            instance_url = self.api_settings['searxng_instance']
            
            # Basic parameters without format specification
            params = {
                'q': query,
                'language': 'en',
                'pageno': '1'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            logger.info(f"Performing SearXNG search: {query}")
            response = requests.get(
                instance_url,
                params=params,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            # Parse the HTML response using BeautifulSoup
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try different possible selectors
            results = []
            result_elements = (
                soup.select('.result') or
                soup.select('.result-default') or
                soup.select('.results-item') or
                soup.select('article') or
                soup.select('.searchresult')
            )
            
            for result in result_elements:
                try:
                    # Try different possible selectors for title
                    title_element = (
                        result.select_one('.result-title') or
                        result.select_one('.title') or
                        result.select_one('h3') or
                        result.select_one('h4')
                    )
                    
                    # Try different possible selectors for link
                    link_element = (
                        result.select_one('.result-link') or
                        result.select_one('.url') or
                        result.select_one('a')
                    )
                    
                    # Try different possible selectors for content
                    content_element = (
                        result.select_one('.result-content') or
                        result.select_one('.content') or
                        result.select_one('.snippet') or
                        result.select_one('p')
                    )
                    
                    if title_element and link_element:
                        title = title_element.get_text(strip=True)
                        link = link_element.get('href')
                        content = content_element.get_text(strip=True) if content_element else ""
                        
                        if title and link:
                            results.append({
                                'title': title,
                                'snippet': content,
                                'link': link
                            })
                        
                    if len(results) >= self.api_settings['results_count']:
                        break
                        
                except Exception as e:
                    logger.debug(f"Failed to parse result: {e}")
                    continue
            
            logger.info(f"Found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"SearXNG search error: {e}")
            return []

    def web_search(self, query: str) -> list:
        """Perform web search using selected search engine"""
        engine = self.api_settings.get('search_engine', 'SearXNG')
        
        if engine == "Google Custom Search":
            return self.google_search(query)
        elif engine == "Bing Search":
            return self.bing_search(query)
        else:
            return self.searxng_search(query)

    def google_search(self, query: str) -> list:
        """Perform Google Custom Search"""
        try:
            api_key = self.api_settings.get('google_api_key')
            cx = self.api_settings.get('google_cx')
            
            if not (api_key and cx):
                logger.error("Google API credentials not configured")
                return []
                
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': api_key,
                'cx': cx,
                'q': query,
                'num': min(int(self.api_settings['results_count']), 10)
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            items = response.json().get('items', [])
            return [{
                'title': item.get('title', ''),
                'snippet': item.get('snippet', ''),
                'link': item.get('link', '')
            } for item in items]
            
        except Exception as e:
            logger.error(f"Google search error: {e}")
            return []

    def bing_search(self, query: str) -> list:
        """Perform Bing Web Search"""
        try:
            api_key = self.api_settings.get('bing_api_key')
            
            if not api_key:
                logger.error("Bing API key not configured")
                return []
                
            url = "https://api.bing.microsoft.com/v7.0/search"
            headers = {"Ocp-Apim-Subscription-Key": api_key}
            params = {
                "q": query,
                "count": min(int(self.api_settings['results_count']), 50)
            }
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            webpages = response.json().get('webPages', {}).get('value', [])
            return [{
                'title': page.get('name', ''),
                'snippet': page.get('snippet', ''),
                'link': page.get('url', '')
            } for page in webpages]
            
        except Exception as e:
            logger.error(f"Bing search error: {e}")
            return []

    def execute_task(self):
        """Execute the selected task with the chosen agent"""
        try:
            task_text = self.task_input.toPlainText().strip()
            agent_type = self.agent_types.currentText()
            
            if not task_text:
                logger.warning("No task text provided")
                return
                
            logger.info(f"Executing task with {agent_type}")
            self.progress_bar.setValue(10)
            
            # For Research Agent, perform web search first
            search_results = []
            if agent_type == "Research Agent":
                logger.info("Performing web search...")
                search_results = self.web_search(task_text)
                if not search_results:
                    logger.warning("No search results found")
            
            # For Account Manager, add specific context and guidelines
            elif agent_type == "Account Manager":
                logger.info("Setting up Account Manager context...")
                account_context = """
                You are an professional and expereinced account manager with strong communication and soft skills.
                """
                task_text = f"{account_context}\n\nBelow is the customer email and communications: {task_text}. \n\n Your task is to analyze the provided customer emails to extract key points, pain points, requirements, expectations, and involved stakeholders. Summarize your findings in a clear and concise report using professional language and generate a response to the customer."

            # For Repeat Scrubbing, add specific context and guidelines
            elif agent_type == "Repeat Scrubbing":
                logger.info("Setting up Repeat Scrubbing context...")
                
                # Company-specific abbreviations and terms
                company_terms = """
                Common Internal Abbreviations and Terms:
                - NOI = no other issues
                - TS = troubleshooting
                - LSP = Lenovo Service Provider
                - FT = Field Technician
                - CX = Customers
                - TAM = Technical Account Manager
                - L2 = level 2 support
                - SB = systemboard
                - MB = motherboard
                - SP = speakers
                - HP = Hewlett Packard
                - red nub = trackpoint
                - WWAN = cellular network card
                - LAN = ethernet connection
                - L1 = level 1 support agent
                - LTS = level 1 support agent
                - UCC = Univeral control centre usually responsible for parts and field tech
                """
                
                scrubbing_context = f"""
                You the most experiened and professional tech support agent in a Lenovo like PC company. Your job is to understand the repair and figure out why there is a repeat repair and why couldn't we fix it the first time.
                
                CONTEXT UNDERSTANDING:
                {company_terms}
                
                YOUR CORE RESPONSIBILITIES:
                1. Text Analysis:
                   - Identify repeated information and redundant statements
                   - Recognize and properly interpret company abbreviations
                   - Understand technical context and domain-specific language
                
                2. Content Processing:
                   - Consolidate similar points while preserving technical accuracy
                   - Maintain proper use of company terminology
                   - Ensure consistency in abbreviation usage
                   - Preserve important technical details and specifications
                
                3. Quality Assurance:
                   - Verify that all technical terms are correctly maintained
                   - Ensure no critical information is lost during consolidation
                   - Maintain document structure and technical context
                """
                
                task_instructions = """
                Please process the content following these steps:
                1. Initial scan for company abbreviations and terms
                2. Identify repetitive content while considering technical context
                3. Consolidate similar information
                4. Preserve unique technical details
                5. Maintain proper terminology usage
                
                Provide output in the following format:
                
                === DOCUMENT METRICS ===
                Original Length: [Word count]
                Cleaned Length: [Word count]
                Reduction: [Percentage]
                
                === ABBREVIATIONS DETECTED ===
                [List all company abbreviations found in the text]
                
                === CLEANED CONTENT ===
                [Your cleaned and consolidated content here]
                
                === CONSOLIDATION SUMMARY ===
                [List of major changes and consolidations made]
                
                === TECHNICAL TERMS PRESERVED ===
                [List of key technical terms and contexts maintained]
                """
                
                task_text = f"{scrubbing_context}\n\nCONTENT TO PROCESS:\n{task_text}\n\n{task_instructions}"

            # Construct the prompt based on agent type and search results
            prompt = f"You are a {agent_type}. Please help with this task:\n\n{task_text}\n\n"
            
            if search_results:
                prompt += "\nBased on these search results:\n"
                for i, result in enumerate(search_results, 1):
                    prompt += f"\n{i}. {result['title']}\n"
                    prompt += f"   {result['snippet']}\n"
                    prompt += f"   Source: {result['link']}\n"
            
            prompt += "\nProvide your response in a clear, step-by-step format."
            
            logger.debug(f"Generated prompt with {'web search results' if search_results else 'no search results'}")
            self.progress_bar.setValue(30)
            
            # Generate response using ollama
            response = self.ollama_client.generate_response(
                prompt=prompt,
                model=self.settings['model'].get()
            )
            
            self.progress_bar.setValue(70)
            
            if response:
                self.task_output.clear()
                self.task_output.setPlainText(response)
                self.progress_bar.setValue(100)
                logger.info("Task executed successfully")
            else:
                logger.error("No response generated from the model")
                self.task_output.setPlainText("Error: Failed to generate response")
                self.progress_bar.setValue(0)
                
        except Exception as e:
            logger.error(f"Error executing task: {e}")
            self.task_output.setPlainText(f"Error: {str(e)}")
            self.progress_bar.setValue(0)

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def show(self):
        super().show()
        self.raise_()

    def hide(self):
        super().hide()