import os
import cv2
import numpy as np
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import tempfile
import time
import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext, messagebox
import threading
import queue
import re
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import traceback
import pandas as pd
import io
import csv
import random
import math

# Try to import easyocr with a fallback mechanism
try:
    import easyocr
except ImportError as e:
    if "cannot import name 'get_display' from 'bidi'" in str(e):
        print("Fixing bidi import issue...")
        import sys
        import importlib.util
        
        if importlib.util.find_spec("bidi") is not None:
            import bidi
            from bidi.algorithm import get_display as bidi_get_display
            
            if not hasattr(bidi, 'get_display'):
                bidi.get_display = bidi_get_display
                
            import easyocr
        else:
            print("Error: python-bidi package is not installed correctly.")
            print("Please run: pip install python-bidi==0.4.2")
            sys.exit(1)

# Try to import additional libraries for enhanced features
try:
    from spellchecker import SpellChecker
    SPELLCHECK_AVAILABLE = True
except ImportError:
    SPELLCHECK_AVAILABLE = False

try:
    from langdetect import detect, detect_langs
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

@dataclass
class TextBlock:
    """Represents a text block with metadata"""
    text: str
    bbox: List[List[int]]
    confidence: float
    x: int
    y: int
    width: int
    height: int
    block_type: str = "text"

@dataclass
class DocumentStructure:
    """Represents the structure of a document"""
    headers: List[TextBlock]
    footers: List[TextBlock]
    paragraphs: List[TextBlock]
    form_fields: List[Dict]
    tables: List[Dict]
    invoice_data: Dict

class SmartTextProcessor:
    """Handles intelligent text processing and cleanup"""
    
    def __init__(self):
        self.spell_checker = SpellChecker() if SPELLCHECK_AVAILABLE else None
        self.confidence_threshold = 0.5
        
    def detect_language(self, text: str) -> str:
        """Detect the language of the text"""
        if not LANGDETECT_AVAILABLE or not text.strip():
            return "unknown"
        
        try:
            return detect(text)
        except:
            return "unknown"
    
    def get_language_confidence(self, text: str) -> List[Dict]:
        """Get language detection confidence scores"""
        if not LANGDETECT_AVAILABLE or not text.strip():
            return []
        
        try:
            langs = detect_langs(text)
            return [{"lang": str(lang).split(':')[0], "confidence": float(str(lang).split(':')[1])} 
                   for lang in langs]
        except:
            return []
    
    def spell_check_and_correct(self, text: str, language: str = "en") -> Dict:
        """Perform spell checking and correction"""
        if not SPELLCHECK_AVAILABLE or self.spell_checker is None:
            return {"original": text, "corrected": text, "corrections": []}

        if language == "en":
            self.spell_checker = SpellChecker(language='en')

        words = text.split()
        corrections = []
        corrected_words = []

        for word in words:
            clean_word = re.sub(r'[^-\w]', '', word.lower())
            if clean_word and self.spell_checker is not None and clean_word not in self.spell_checker:
                try:
                    suggestions = list(self.spell_checker.candidates(clean_word))
                except Exception:
                    suggestions = []
                if suggestions:
                    best_correction = suggestions[0]
                    corrections.append({
                        "original": word,
                        "corrected": best_correction,
                        "suggestions": suggestions[:3]
                    })
                    corrected_words.append(word.replace(clean_word, best_correction))
                else:
                    corrected_words.append(word)
            else:
                corrected_words.append(word)

        return {
            "original": text,
            "corrected": " ".join(corrected_words),
            "corrections": corrections
        }
    
    def filter_by_confidence(self, results: List, threshold: float = None) -> List:
        """Filter OCR results by confidence threshold"""
        if threshold is None:
            threshold = self.confidence_threshold
        
        filtered_results = []
        for bbox, text, confidence in results:
            if confidence >= threshold:
                filtered_results.append((bbox, text, confidence))
        
        return filtered_results
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('|', 'I')
        text = text.replace('0', 'O')
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\;]', '', text)
        return text.strip()

class DocumentStructureAnalyzer:
    """Analyzes document structure and extracts different components"""
    
    def __init__(self):
        self.invoice_patterns = self._load_invoice_patterns()
        self.form_patterns = self._load_form_patterns()
    
    def analyze_structure(self, text_blocks: List[TextBlock], page_height: int) -> DocumentStructure:
        """Analyze the structure of the document"""
        headers = self._detect_headers(text_blocks, page_height)
        footers = self._detect_footers(text_blocks, page_height)
        paragraphs = self._detect_paragraphs(text_blocks)
        form_fields = self._detect_form_fields(text_blocks)
        tables = self._detect_tables(text_blocks)
        invoice_data = self._extract_invoice_data(text_blocks)
        
        return DocumentStructure(
            headers=headers,
            footers=footers,
            paragraphs=paragraphs,
            form_fields=form_fields,
            tables=tables,
            invoice_data=invoice_data
        )
    
    def _detect_headers(self, text_blocks: List[TextBlock], page_height: int) -> List[TextBlock]:
        """Detect header sections (top 15% of page)"""
        header_threshold = page_height * 0.15
        headers = []
        
        for block in text_blocks:
            if block.y <= header_threshold:
                block.block_type = "header"
                headers.append(block)
        
        return sorted(headers, key=lambda x: x.y)
    
    def _detect_footers(self, text_blocks: List[TextBlock], page_height: int) -> List[TextBlock]:
        """Detect footer sections (bottom 15% of page)"""
        footer_threshold = page_height * 0.85
        footers = []
        
        for block in text_blocks:
            if block.y >= footer_threshold:
                block.block_type = "footer"
                footers.append(block)
        
        return sorted(footers, key=lambda x: x.y)
    
    def _detect_paragraphs(self, text_blocks: List[TextBlock]) -> List[TextBlock]:
        """Group text blocks into paragraphs"""
        paragraphs = []
        sorted_blocks = sorted(text_blocks, key=lambda x: (x.y, x.x))
        
        current_paragraph = []
        last_y = 0
        line_height_threshold = 50
        
        for block in sorted_blocks:
            if block.block_type in ["header", "footer"]:
                continue
                
            if current_paragraph and abs(block.y - last_y) > line_height_threshold:
                if current_paragraph:
                    combined_text = " ".join([b.text for b in current_paragraph])
                    para_block = TextBlock(
                        text=combined_text,
                        bbox=current_paragraph[0].bbox,
                        confidence=sum([b.confidence for b in current_paragraph]) / len(current_paragraph),
                        x=min([b.x for b in current_paragraph]),
                        y=min([b.y for b in current_paragraph]),
                        width=max([b.x + b.width for b in current_paragraph]) - min([b.x for b in current_paragraph]),
                        height=max([b.y + b.height for b in current_paragraph]) - min([b.y for b in current_paragraph]),
                        block_type="paragraph"
                    )
                    paragraphs.append(para_block)
                current_paragraph = [block]
            else:
                current_paragraph.append(block)
            
            last_y = block.y
        
        if current_paragraph:
            combined_text = " ".join([b.text for b in current_paragraph])
            para_block = TextBlock(
                text=combined_text,
                bbox=current_paragraph[0].bbox,
                confidence=sum([b.confidence for b in current_paragraph]) / len(current_paragraph),
                x=min([b.x for b in current_paragraph]),
                y=min([b.y for b in current_paragraph]),
                width=max([b.x + b.width for b in current_paragraph]) - min([b.x for b in current_paragraph]),
                height=max([b.y + b.height for b in current_paragraph]) - min([b.y for b in current_paragraph]),
                block_type="paragraph"
            )
            paragraphs.append(para_block)
        
        return paragraphs
    
    def _detect_form_fields(self, text_blocks: List[TextBlock]) -> List[Dict]:
        """Detect form fields and their values"""
        form_fields = []
        
        for pattern in self.form_patterns:
            for block in text_blocks:
                match = re.search(pattern["pattern"], block.text, re.IGNORECASE)
                if match:
                    field_data = {
                        "field_name": pattern["name"],
                        "field_type": pattern["type"],
                        "raw_text": block.text,
                        "extracted_value": match.group(1) if match.groups() else match.group(0),
                        "confidence": block.confidence,
                        "bbox": block.bbox
                    }
                    form_fields.append(field_data)
        
        return form_fields
    
    def _detect_tables(self, text_blocks: List[TextBlock]) -> List[Dict]:
        """Detect table structures"""
        tables = []
        rows = defaultdict(list)
        
        for block in text_blocks:
            row_key = round(block.y / 20) * 20
            rows[row_key].append(block)
        
        potential_table_rows = []
        for y_pos, row_blocks in rows.items():
            if len(row_blocks) >= 3:
                sorted_row = sorted(row_blocks, key=lambda x: x.x)
                potential_table_rows.append((y_pos, sorted_row))
        
        if len(potential_table_rows) >= 2:
            table_data = {
                "type": "table",
                "rows": len(potential_table_rows),
                "columns": max([len(row[1]) for row in potential_table_rows]),
                "data": []
            }
            
            for y_pos, row_blocks in potential_table_rows:
                row_data = [block.text for block in row_blocks]
                table_data["data"].append(row_data)
            
            tables.append(table_data)
        
        return tables
    
    def _extract_invoice_data(self, text_blocks: List[TextBlock]) -> Dict:
        """Extract invoice-specific data"""
        invoice_data = {
            "invoice_number": None,
            "date": None,
            "total_amount": None,
            "vendor": None,
            "items": []
        }
        
        all_text = " ".join([block.text for block in text_blocks])
        
        for pattern in self.invoice_patterns:
            match = re.search(pattern["pattern"], all_text, re.IGNORECASE)
            if match:
                invoice_data[pattern["field"]] = match.group(1) if match.groups() else match.group(0)
        
        return invoice_data
    
    def _load_invoice_patterns(self) -> List[Dict]:
        """Load invoice parsing patterns"""
        return [
            {"field": "invoice_number", "pattern": r"invoice\s*#?\s*:?\s*([A-Z0-9\-]+)", "type": "string"},
            {"field": "date", "pattern": r"date\s*:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})", "type": "date"},
            {"field": "total_amount", "pattern": r"total\s*:?\s*\$?(\d+\.?\d*)", "type": "currency"},
            {"field": "vendor", "pattern": r"from\s*:?\s*([A-Za-z\s]+)", "type": "string"}
        ]
    
    def _load_form_patterns(self) -> List[Dict]:
        """Load form field patterns"""
        return [
            {"name": "name", "pattern": r"name\s*:?\s*([A-Za-z\s]+)", "type": "text"},
            {"name": "email", "pattern": r"email\s*:?\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", "type": "email"},
            {"name": "phone", "pattern": r"phone\s*:?\s*(\+?\d{1,3}?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", "type": "phone"},
            {"name": "address", "pattern": r"address\s*:?\s*([A-Za-z0-9\s,.-]+)", "type": "address"},
            {"name": "date_of_birth", "pattern": r"(?:date of birth|dob|birth date)\s*:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})", "type": "date"},
            {"name": "social_security", "pattern": r"(?:ssn|social security)\s*:?\s*(\d{3}-?\d{2}-?\d{4})", "type": "ssn"}
        ]

class EnhancedOCRProcessor:
    def __init__(self, languages=['en', 'ar'], use_gpu=True, confidence_threshold=0.5):
        """Initialize the enhanced OCR processor"""
        print(f"Initializing Enhanced EasyOCR with languages: {languages}")
        self.reader = easyocr.Reader(languages, gpu=use_gpu)
        self.languages = languages
        self.text_processor = SmartTextProcessor()
        self.structure_analyzer = DocumentStructureAnalyzer()
        self.text_processor.confidence_threshold = confidence_threshold
        
    def process_image(self, image_path, enable_smart_processing=True, progress_callback=None):
        """Process a single image file with enhanced OCR and smart text processing"""
        start_time = time.time()
        print(f"Processing image: {image_path}")

        if progress_callback:
            progress_callback("Initializing image processing...")

        # Check if file exists
        if not os.path.isfile(image_path):
            return {"error": f"File does not exist: {image_path}"}

        if progress_callback:
            progress_callback("Loading image file...")

        # Try to read the image
        image = cv2.imread(image_path)
        if image is None:
            return {"error": f"Could not read image file (unsupported or corrupted): {image_path}"}

        if progress_callback:
            progress_callback("Running OCR analysis...")

        try:
            raw_results = self.reader.readtext(image)
            if not raw_results or not isinstance(raw_results, list):
                return {"error": "OCR engine returned no results or an unexpected value."}
        except Exception as e:
            return {"error": f"OCR engine failed: {str(e)}\n{traceback.format_exc()}"}

        if progress_callback:
            progress_callback("Processing OCR results...")

        try:
            height, width = image.shape[:2]
            text_blocks = self._create_text_blocks(raw_results) if raw_results else []
            extracted_text = self._format_results(raw_results) if raw_results else ""

            result = {
                "text": extracted_text,
                "raw_results": raw_results,
                "processing_time": time.time() - start_time,
                "source_type": "image",
                "source_path": image_path,
                "image_dimensions": {"width": width, "height": height}
            }

            if enable_smart_processing:
                if progress_callback:
                    progress_callback("Applying smart text processing...")
                smart_results = self._apply_smart_processing(extracted_text, text_blocks, height)
                result.update(smart_results)

            if progress_callback:
                progress_callback("Image processing complete!")

            return result
        except Exception as e:
            return {"error": f"Post-processing failed: {str(e)}\n{traceback.format_exc()}"}
    
    def process_pdf(self, pdf_path, enable_smart_processing=True, progress_callback=None):
        """Process a PDF file with enhanced OCR and smart text processing"""
        import traceback
        start_time = time.time()
        print(f"Processing PDF: {pdf_path}")

        if progress_callback:
            progress_callback("Initializing PDF processing...")

        if not os.path.isfile(pdf_path):
            return {"error": f"File does not exist: {pdf_path}"}

        try:
            if progress_callback:
                progress_callback("Opening PDF document...")

            pdf_document = fitz.open(pdf_path)
            total_pages = len(pdf_document)
            page_results = []

            if progress_callback:
                progress_callback(f"Found {total_pages} page(s). Starting OCR processing...")

            for page_num in range(total_pages):
                if progress_callback:
                    progress_callback(f"Processing page {page_num + 1}/{total_pages}...")

                page = pdf_document.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))

                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                    temp_path = temp_file.name

                pix.save(temp_path)
                image = cv2.imread(temp_path)
                if image is None:
                    page_result = {"error": f"Could not read page image for page {page_num+1}"}
                    page_results.append(page_result)
                    os.unlink(temp_path)
                    continue

                if progress_callback:
                    progress_callback(f"Running OCR on page {page_num + 1}/{total_pages}...")

                try:
                    raw_results = self.reader.readtext(image)
                    if not raw_results or not isinstance(raw_results, list):
                        page_result = {"error": f"OCR engine returned no results or an unexpected value for page {page_num+1}."}
                        page_results.append(page_result)
                        os.unlink(temp_path)
                        continue
                except Exception as e:
                    page_result = {"error": f"OCR engine failed on page {page_num+1}: {str(e)}\n{traceback.format_exc()}"}
                    page_results.append(page_result)
                    os.unlink(temp_path)
                    continue

                height, width = image.shape[:2]
                text_blocks = self._create_text_blocks(raw_results) if raw_results else []
                extracted_text = self._format_results(raw_results) if raw_results else ""

                page_result = {
                    "page_num": page_num + 1,
                    "text": extracted_text,
                    "raw_results": raw_results,
                    "page_dimensions": {"width": width, "height": height}
                }

                if enable_smart_processing:
                    if progress_callback:
                        progress_callback(f"Applying smart processing to page {page_num + 1}/{total_pages}...")
                    smart_results = self._apply_smart_processing(extracted_text, text_blocks, height)
                    page_result.update(smart_results)

                page_results.append(page_result)
                os.unlink(temp_path)

            if progress_callback:
                progress_callback("Finalizing PDF processing...")

            processing_time = time.time() - start_time
            aggregated_results = self._aggregate_pdf_results(page_results) if enable_smart_processing else {}

            if progress_callback:
                progress_callback("PDF processing complete!")

            return {
                "pages": page_results,
                "total_pages": len(pdf_document),
                "processing_time": processing_time,
                "source_type": "pdf",
                "source_path": pdf_path,
                "aggregated_analysis": aggregated_results
            }

        except Exception as e:
            return {"error": f"Error processing PDF: {str(e)}\n{traceback.format_exc()}"}
    
    def _create_text_blocks(self, raw_results) -> List[TextBlock]:
        """Convert raw OCR results to TextBlock objects"""
        text_blocks = []
        
        for bbox, text, confidence in raw_results:
            x_coords = [point[0] for point in bbox]
            y_coords = [point[1] for point in bbox]
            
            x = min(x_coords)
            y = min(y_coords)
            width = max(x_coords) - x
            height = max(y_coords) - y
            
            text_block = TextBlock(
                text=text,
                bbox=bbox,
                confidence=confidence,
                x=int(x),
                y=int(y),
                width=int(width),
                height=int(height)
            )
            text_blocks.append(text_block)
        
        return text_blocks
    
    def _apply_smart_processing(self, text: str, text_blocks: List[TextBlock], page_height: int) -> Dict:
        """Apply smart text processing and document structure analysis"""
        detected_language = self.text_processor.detect_language(text)
        language_confidence = self.text_processor.get_language_confidence(text)
        spell_check_results = self.text_processor.spell_check_and_correct(text, detected_language)
        cleaned_text = self.text_processor.clean_text(text)
        
        high_confidence_blocks = [block for block in text_blocks 
                                if block.confidence >= self.text_processor.confidence_threshold]
        
        document_structure = self.structure_analyzer.analyze_structure(text_blocks, page_height)
        
        smart_results = {
            "smart_processing": {
                "language_detection": {
                    "primary_language": detected_language,
                    "language_confidence": language_confidence
                },
                "spell_check": spell_check_results,
                "cleaned_text": cleaned_text,
                "confidence_filtering": {
                    "threshold": self.text_processor.confidence_threshold,
                    "total_blocks": len(text_blocks),
                    "high_confidence_blocks": len(high_confidence_blocks),
                    "filtered_percentage": len(high_confidence_blocks) / len(text_blocks) * 100 if text_blocks else 0
                }
            },
            "document_structure": {
                "headers": [{"text": h.text, "confidence": h.confidence, "position": {"x": h.x, "y": h.y}} 
                           for h in document_structure.headers],
                "footers": [{"text": f.text, "confidence": f.confidence, "position": {"x": f.x, "y": f.y}} 
                           for f in document_structure.footers],
                "paragraphs": [{"text": p.text, "confidence": p.confidence, "word_count": len(p.text.split())} 
                              for p in document_structure.paragraphs],
                "form_fields": document_structure.form_fields,
                "tables": document_structure.tables,
                "invoice_data": document_structure.invoice_data
            }
        }
        
        return smart_results
    
    def _aggregate_pdf_results(self, page_results: List[Dict]) -> Dict:
        """Aggregate smart processing results across all PDF pages"""
        aggregated = {
            "total_text_blocks": 0,
            "average_confidence": 0,
            "languages_detected": set(),
            "total_corrections": 0,
            "document_type": "unknown",
            "all_form_fields": [],
            "all_tables": [],
            "consolidated_invoice_data": {}
        }
        
        total_confidence = 0
        total_blocks = 0
        
        for page in page_results:
            if "smart_processing" in page:
                if "confidence_filtering" in page["smart_processing"]:
                    page_blocks = page["smart_processing"]["confidence_filtering"]["total_blocks"]
                    total_blocks += page_blocks
                    total_confidence += page_blocks * 0.7
                
                if "language_detection" in page["smart_processing"]:
                    lang = page["smart_processing"]["language_detection"]["primary_language"]
                    if lang != "unknown":
                        aggregated["languages_detected"].add(lang)
                
                if "spell_check" in page["smart_processing"]:
                    corrections = page["smart_processing"]["spell_check"].get("corrections", [])
                    aggregated["total_corrections"] += len(corrections)
            
            if "document_structure" in page:
                aggregated["all_form_fields"].extend(page["document_structure"]["form_fields"])
                aggregated["all_tables"].extend(page["document_structure"]["tables"])
                
                invoice_data = page["document_structure"]["invoice_data"]
                for key, value in invoice_data.items():
                    if value and not aggregated["consolidated_invoice_data"].get(key):
                        aggregated["consolidated_invoice_data"][key] = value
        
        if total_blocks > 0:
            aggregated["average_confidence"] = total_confidence / total_blocks
        
        aggregated["languages_detected"] = list(aggregated["languages_detected"])
        aggregated["total_text_blocks"] = total_blocks
        
        if aggregated["consolidated_invoice_data"].get("invoice_number"):
            aggregated["document_type"] = "invoice"
        elif aggregated["all_form_fields"]:
            aggregated["document_type"] = "form"
        elif aggregated["all_tables"]:
            aggregated["document_type"] = "table_document"
        
        return aggregated
    
    def _format_results(self, results):
        """Format the raw OCR results into readable text"""
        text_blocks = []
        for (bbox, text, prob) in results:
            text_blocks.append(text)
        return "\n".join(text_blocks)
    
    def export_analysis_report(self, results: Dict, output_path: str):
        """Export detailed analysis report to JSON file"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            print(f"Analysis report exported to: {output_path}")
        except Exception as e:
            print(f"Error exporting report: {str(e)}")

def call_gemini_api(prompt, text):
    try:
        import google.generativeai as genai
    except ImportError:
        return "Gemini API client not installed. Please install google-generativeai."
    api_key = "AIzaSyAai4D3N3tAlT06tplfCQ8qaZDlRr56a5Q"
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content([prompt, text])
        return response.text if hasattr(response, 'text') else str(response)
    except Exception as e:
        return f"Gemini API error: {str(e)}"

class EnhancedOCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced OCR Processor - Smart Document Analysis")
        self.root.geometry("1200x900")
        self.root.configure(bg='#f0f0f0')
        
        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.ocr = None
        self.current_results = None
        self.processing_thread = None
        
        # For Undo/Redo functionality
        self.text_history = []
        self.text_history_index = -1
        self.max_history_size = 20 # Limit history size to prevent excessive memory usage
        
        self._setup_ui()
        self._check_dependencies()
        
    def _setup_ui(self):
        """Setup the complete user interface"""
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title_frame = ttk.Frame(main_container)
        title_frame.pack(fill="x", pady=(0, 10))
        
        title_label = ttk.Label(title_frame, text="Enhanced OCR Processor", 
                               font=("Arial", 16, "bold"))
        title_label.pack()
        
        subtitle_label = ttk.Label(title_frame, text="Smart Document Analysis with AI-Powered Text Processing", 
                                  font=("Arial", 10))
        subtitle_label.pack()
        
        # Create main notebook
        self.main_notebook = ttk.Notebook(main_container)
        self.main_notebook.pack(fill="both", expand=True)
        
        # Setup tabs
        self._setup_processing_tab()
        self._setup_analysis_tab()
        self._setup_settings_tab()
        self._setup_help_tab()
        
    def _setup_processing_tab(self):
        """Setup the main processing tab"""
        self.processing_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.processing_frame, text="📄 OCR Processing")
        
        # Left panel for controls
        left_panel = ttk.Frame(self.processing_frame)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10)) # Changed from pack to grid
        self.processing_frame.grid_columnconfigure(0, weight=0) # Left panel fixed width initially
        
        # Right panel for results
        right_panel = ttk.Frame(self.processing_frame)
        right_panel.grid(row=0, column=1, sticky="nsew") # Changed from pack to grid
        self.processing_frame.grid_columnconfigure(1, weight=1) # Make right panel expandable
        self.processing_frame.grid_rowconfigure(0, weight=1) # Make right panel expandable
        
        # === LEFT PANEL CONTROLS ===
        
        # File Selection Group
        file_group = ttk.LabelFrame(left_panel, text="📁 File Selection")
        file_group.pack(fill="x", pady=(0, 10))
        
        # File type selection
        ttk.Label(file_group, text="File Type:").pack(anchor="w", padx=5, pady=(5, 0))
        self.file_type = tk.StringVar(value="image")
        
        file_type_frame = ttk.Frame(file_group)
        file_type_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Radiobutton(file_type_frame, text="📷 Image", variable=self.file_type, 
                       value="image").pack(side="left")
        ttk.Radiobutton(file_type_frame, text="📋 PDF", variable=self.file_type, 
                       value="pdf").pack(side="left", padx=(20, 0))
        
        # File selection button
        self.select_button = ttk.Button(file_group, text="🔍 Select File", 
                                       command=self.select_file, width=20)
        self.select_button.pack(pady=10)
        
        # Selected file display
        self.selected_file_var = tk.StringVar(value="No file selected")
        selected_file_label = ttk.Label(file_group, textvariable=self.selected_file_var, 
                                       wraplength=200, font=("Arial", 8))
        selected_file_label.pack(padx=5, pady=(0, 5))
        
        # Processing Configuration Group
        config_group = ttk.LabelFrame(left_panel, text="⚙️ Processing Configuration")
        config_group.pack(fill="x", pady=(0, 10))
        
        # GPU/CPU Selection
        ttk.Label(config_group, text="Processing Device:").pack(anchor="w", padx=5, pady=(5, 0))
        self.gpu_var = tk.BooleanVar(value=True)
        
        device_frame = ttk.Frame(config_group)
        device_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Radiobutton(device_frame, text="🚀 GPU", variable=self.gpu_var, 
                       value=True).pack(side="left")
        ttk.Radiobutton(device_frame, text="💻 CPU", variable=self.gpu_var, 
                       value=False).pack(side="left", padx=(20, 0))
        
        # Language Selection
        ttk.Label(config_group, text="Languages:").pack(anchor="w", padx=5, pady=(10, 0))
        
        lang_frame = ttk.Frame(config_group)
        lang_frame.pack(fill="x", padx=5, pady=5)
        
        self.lang_en = tk.BooleanVar(value=True)
        self.lang_ar = tk.BooleanVar(value=True)
        
        ttk.Checkbutton(lang_frame, text="🇺🇸 English", variable=self.lang_en).pack(anchor="w")
        ttk.Checkbutton(lang_frame, text="🇸🇦 Arabic", variable=self.lang_ar).pack(anchor="w")
        # Confidence Threshold
        ttk.Label(config_group, text="Confidence Threshold:").pack(anchor="w", padx=5, pady=(10, 0))
        
        conf_frame = ttk.Frame(config_group)
        conf_frame.pack(fill="x", padx=5, pady=5)
        
        self.confidence_var = tk.DoubleVar(value=0.5)
        confidence_scale = ttk.Scale(conf_frame, from_=0.0, to=1.0, 
                                   variable=self.confidence_var, orient="horizontal")
        confidence_scale.pack(fill="x")
        
        self.confidence_label = ttk.Label(conf_frame, text="0.50")
        self.confidence_label.pack()
        confidence_scale.configure(command=self._update_confidence_label)
        
        # Smart Processing Options Group
        smart_group = ttk.LabelFrame(left_panel, text="🧠 Smart Processing")
        smart_group.pack(fill="x", pady=(0, 10))
        
        self.smart_processing_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(smart_group, text="Enable Smart Analysis", 
                       variable=self.smart_processing_var).pack(anchor="w", padx=5, pady=5)
        
        self.spell_check_var = tk.BooleanVar(value=SPELLCHECK_AVAILABLE)
        spell_check_cb = ttk.Checkbutton(smart_group, text="Spell Check & Correction", 
                                        variable=self.spell_check_var)
        spell_check_cb.pack(anchor="w", padx=5, pady=2)
        if not SPELLCHECK_AVAILABLE:
            spell_check_cb.configure(state="disabled")
        
        self.lang_detect_var = tk.BooleanVar(value=LANGDETECT_AVAILABLE)
        lang_detect_cb = ttk.Checkbutton(smart_group, text="Language Detection", 
                                        variable=self.lang_detect_var)
        lang_detect_cb.pack(anchor="w", padx=5, pady=2)
        if not LANGDETECT_AVAILABLE:
            lang_detect_cb.configure(state="disabled")
        
        self.structure_analysis_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(smart_group, text="Document Structure Analysis", 
                       variable=self.structure_analysis_var).pack(anchor="w", padx=5, pady=2)
        
        self.form_extraction_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(smart_group, text="Form Field Extraction", 
                       variable=self.form_extraction_var).pack(anchor="w", padx=5, pady=2)
        
        self.invoice_parsing_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(smart_group, text="Invoice/Receipt Parsing", 
                       variable=self.invoice_parsing_var).pack(anchor="w", padx=5, pady=2)
        
        # Action Buttons Group
        action_group = ttk.LabelFrame(left_panel, text="🎯 Actions")
        action_group.pack(fill="x", pady=(0, 10))
        
        self.process_button = ttk.Button(action_group, text="🚀 Start Processing", 
                                        command=self.start_processing, width=20)
        self.process_button.pack(pady=5)
        
        self.export_button = ttk.Button(action_group, text="💾 Export Report", 
                                       command=self.export_report, width=20, state="disabled")
        self.export_button.pack(pady=5)
        
        self.clear_button = ttk.Button(action_group, text="🗑️ Clear Results", 
                                      command=self.clear_results, width=20)
        self.clear_button.pack(pady=5)
        
        # Progress Group
        progress_group = ttk.LabelFrame(left_panel, text="📊 Progress")
        progress_group.pack(fill="x")
        
        self.progress_var = tk.StringVar(value="Ready")
        self.progress_label = ttk.Label(progress_group, textvariable=self.progress_var)
        self.progress_label.pack(padx=5, pady=5)
        
        self.progress_bar = ttk.Progressbar(progress_group, mode='indeterminate')
        self.progress_bar.pack(fill="x", padx=5, pady=(0, 5))
        
        # === RIGHT PANEL RESULTS ===
        
        # Results notebook
        self.results_notebook = ttk.Notebook(right_panel)
        self.results_notebook.grid(row=0, column=0, sticky="nsew") # Placed in grid
        
        # Basic OCR Results Tab
        self.basic_results_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(self.basic_results_frame, text="📝 OCR Text")
        
        basic_results_label = ttk.Label(self.basic_results_frame, text="Extracted Text:")
        basic_results_label.pack(anchor="w", padx=5, pady=(5, 0))
        
        # Create a frame for the text widget and its scrollbars
        text_widget_container = ttk.Frame(self.basic_results_frame)
        text_widget_container.pack(fill="both", expand=True, padx=5, pady=5)

        text_vsb = ttk.Scrollbar(text_widget_container, orient="vertical")
        text_hsb = ttk.Scrollbar(text_widget_container, orient="horizontal")

        self.basic_results_text = tk.Text(
            text_widget_container,
            height=20,
            wrap="none",  # Allow horizontal scrolling
            yscrollcommand=text_vsb.set,
            xscrollcommand=text_hsb.set
        )

        text_vsb.config(command=self.basic_results_text.yview)
        text_hsb.config(command=self.basic_results_text.xview)

        self.basic_results_text.grid(row=0, column=0, sticky="nsew")
        text_vsb.grid(row=0, column=1, sticky="ns")
        text_hsb.grid(row=1, column=0, sticky="ew")

        text_widget_container.grid_rowconfigure(0, weight=1)
        text_widget_container.grid_columnconfigure(0, weight=1)
        
        # Table Editor Tab (for Excel/CSV)
        self.table_editor_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(self.table_editor_frame, text="📊 Table Editor")

        # Create a notebook specifically for table-related AI features
        self.table_ai_notebook = ttk.Notebook(self.table_editor_frame)
        self.table_ai_notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # Tab 1: Main Table Editor
        self.main_table_frame = ttk.Frame(self.table_ai_notebook)
        self.table_ai_notebook.add(self.main_table_frame, text="Table Data")
        
        # Create a frame for the table and its scrollbars
        table_widget_container = ttk.Frame(self.main_table_frame)
        table_widget_container.pack(fill="both", expand=True, padx=5, pady=5)

        table_vsb = ttk.Scrollbar(table_widget_container, orient="vertical")
        table_hsb = ttk.Scrollbar(table_widget_container, orient="horizontal")

        self.table_tree = ttk.Treeview(
            table_widget_container,
            show="headings",
            yscrollcommand=table_vsb.set,
            xscrollcommand=table_hsb.set
        )

        table_vsb.config(command=self.table_tree.yview)
        table_hsb.config(command=self.table_tree.xview)

        self.table_tree.grid(row=0, column=0, sticky="nsew")
        table_vsb.grid(row=0, column=1, sticky="ns")
        table_hsb.grid(row=1, column=0, sticky="ew")

        table_widget_container.grid_rowconfigure(0, weight=1)
        table_widget_container.grid_columnconfigure(0, weight=1)
        
        # Table manipulation controls (will be placed inside main_table_frame as well)
        table_controls_frame = ttk.Frame(self.main_table_frame)
        table_controls_frame.pack(fill="x", pady=5)

        self.add_column_button = ttk.Button(table_controls_frame, text="➕ Add Column", command=self.add_column)
        self.add_column_button.pack(side="left", padx=5)

        self.add_row_button = ttk.Button(table_controls_frame, text="➕ Add Row", command=self.add_row_manual)
        self.add_row_button.pack(side="left", padx=5)

        self.add_row_ai_button = ttk.Button(table_controls_frame, text="➕ Add Row (AI)", command=self.add_row_with_gemini)
        self.add_row_ai_button.pack(side="left", padx=5)

        self.add_column_ai_button = ttk.Button(table_controls_frame, text="➕ Add Column (AI)", command=self.add_column_with_gemini)
        self.add_column_ai_button.pack(side="left", padx=5)

        self.rename_columns_ai_button = ttk.Button(table_controls_frame, text="📝 Rename Columns (AI)", command=self.rename_columns_with_gemini)
        self.rename_columns_ai_button.pack(side="left", padx=5)

        self.explain_table_ai_button = ttk.Button(table_controls_frame, text="❓ Explain Table (AI)", command=self.explain_table_with_gemini)
        self.explain_table_ai_button.pack(side="left", padx=5)

        self.suggest_table_ai_button = ttk.Button(table_controls_frame, text="💡 Suggestions (AI)", command=self.suggest_table_actions_with_gemini)
        self.suggest_table_ai_button.pack(side="left", padx=5)

        self.how_it_works_table_button = ttk.Button(table_controls_frame, text="ℹ️ How it Works (Table)", command=self.show_table_editor_help)
        self.how_it_works_table_button.pack(side="left", padx=5)

        self.table_command_ai_button = ttk.Button(table_controls_frame, text="⚡ Table Command (AI)", command=self.generate_table_instructions_with_gemini)
        self.table_command_ai_button.pack(side="left", padx=5)

        self.export_table_button = ttk.Button(table_controls_frame, text="💾 Export Table", command=self.export_table)
        self.export_table_button.pack(side="right", padx=5)
        
        # Bind for cell editing
        self.table_tree.bind("<Double-1>", self._on_table_double_click)

        # Tab 2: Table Explanation (AI)
        self.table_explain_frame = ttk.Frame(self.table_ai_notebook)
        self.table_ai_notebook.add(self.table_explain_frame, text="Explanation (AI)")
        self.explain_text = scrolledtext.ScrolledText(self.table_explain_frame, height=20, wrap=tk.WORD)
        self.explain_text.pack(fill="both", expand=True, padx=5, pady=5)

        # Tab 3: Table Suggestions (AI)
        self.table_suggest_frame = ttk.Frame(self.table_ai_notebook)
        self.table_ai_notebook.add(self.table_suggest_frame, text="Suggestions (AI)")
        self.suggestions_text = scrolledtext.ScrolledText(self.table_suggest_frame, height=20, wrap=tk.WORD)
        self.suggestions_text.pack(fill="both", expand=True, padx=5, pady=5)

        # Processing Info Tab
        self.info_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(self.info_frame, text="ℹ️ Processing Info")
        
        self.info_text = scrolledtext.ScrolledText(self.info_frame, height=20, wrap=tk.WORD)
        self.info_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Add Gemini AI and Undo buttons below the results notebook
        action_buttons_frame = ttk.Frame(right_panel)
        action_buttons_frame.grid(row=1, column=0, sticky="ew", pady=5) # Placed in grid

        self.summary_button = ttk.Button(action_buttons_frame, text="🧠 Summarize with Gemini", command=self.summarize_with_gemini)
        self.summary_button.pack(side="left", padx=5)

        self.write_to_ai_button = ttk.Button(action_buttons_frame, text="💬 Write to AI", command=self.write_to_ai)
        self.write_to_ai_button.pack(side="left", padx=5)

        self.rewrite_with_ai_button = ttk.Button(action_buttons_frame, text="✨ Rewrite with AI", command=self.rewrite_with_gemini)
        self.rewrite_with_ai_button.pack(side="left", padx=5)

        self.undo_button = ttk.Button(action_buttons_frame, text="↩️ Undo", command=self.undo_text_change, state="disabled")
        self.undo_button.pack(side="right", padx=5)

        # Configure grid weights for right_panel's children
        right_panel.grid_rowconfigure(0, weight=1) # results_notebook expands vertically
        right_panel.grid_columnconfigure(0, weight=1) # Allows contents to expand horizontally
    
    def _setup_analysis_tab(self):
        """Setup the smart analysis results tab"""
        self.analysis_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.analysis_frame, text="🔍 Smart Analysis")
        
        # Create analysis notebook
        self.analysis_notebook = ttk.Notebook(self.analysis_frame)
        self.analysis_notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Language Analysis Tab
        self.lang_analysis_frame = ttk.Frame(self.analysis_notebook)
        self.analysis_notebook.add(self.lang_analysis_frame, text="🌐 Language Analysis")
        
        lang_info_frame = ttk.LabelFrame(self.lang_analysis_frame, text="Language Detection Results")
        lang_info_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.language_analysis_text = scrolledtext.ScrolledText(lang_info_frame, height=15)
        self.language_analysis_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Document Structure Tab
        self.structure_frame = ttk.Frame(self.analysis_notebook)
        self.analysis_notebook.add(self.structure_frame, text="📋 Document Structure")
        
        # Create sub-tabs for structure elements
        self.structure_notebook = ttk.Notebook(self.structure_frame)
        self.structure_notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Headers/Footers
        self.headers_frame = ttk.Frame(self.structure_notebook)
        self.structure_notebook.add(self.headers_frame, text="📄 Headers/Footers")
        self.headers_text = scrolledtext.ScrolledText(self.headers_frame, height=12)
        self.headers_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Paragraphs
        self.paragraphs_frame = ttk.Frame(self.structure_notebook)
        self.structure_notebook.add(self.paragraphs_frame, text="📝 Paragraphs")
        self.paragraphs_text = scrolledtext.ScrolledText(self.paragraphs_frame, height=12)
        self.paragraphs_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Form Fields Tab
        self.forms_frame = ttk.Frame(self.analysis_notebook)
        self.analysis_notebook.add(self.forms_frame, text="📋 Form Fields")
        
        forms_info_frame = ttk.LabelFrame(self.forms_frame, text="Detected Form Fields")
        forms_info_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.forms_text = scrolledtext.ScrolledText(forms_info_frame, height=15)
        self.forms_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Invoice Data Tab
        self.invoice_frame = ttk.Frame(self.analysis_notebook)
        self.analysis_notebook.add(self.invoice_frame, text="🧾 Invoice Data")
        
        invoice_info_frame = ttk.LabelFrame(self.invoice_frame, text="Extracted Invoice Information")
        invoice_info_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.invoice_text = scrolledtext.ScrolledText(invoice_info_frame, height=15)
        self.invoice_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Tables Tab
        self.tables_frame = ttk.Frame(self.analysis_notebook)
        self.analysis_notebook.add(self.tables_frame, text="📊 Tables")
        
        tables_info_frame = ttk.LabelFrame(self.tables_frame, text="Detected Tables")
        tables_info_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.tables_text = scrolledtext.ScrolledText(tables_info_frame, height=15)
        self.tables_text.pack(fill="both", expand=True, padx=5, pady=5)
    
    def _setup_settings_tab(self):
        """Setup the settings and configuration tab"""
        self.settings_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.settings_frame, text="⚙️ Settings")
        
        settings_container = ttk.Frame(self.settings_frame)
        settings_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # OCR Engine Settings
        ocr_settings_group = ttk.LabelFrame(settings_container, text="OCR Engine Settings")
        ocr_settings_group.pack(fill="x", pady=(0, 20))
        
        # Model download info
        ttk.Label(ocr_settings_group, text="EasyOCR Model Management:", 
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        model_info_text = """
• Models are automatically downloaded on first use
• English model: ~47MB
• Arabic model: ~43MB
• Models are cached locally for faster subsequent use
        """
        ttk.Label(ocr_settings_group, text=model_info_text, justify="left").pack(anchor="w", padx=20, pady=5)
        
        # Performance Settings
        perf_settings_group = ttk.LabelFrame(settings_container, text="Performance Settings")
        perf_settings_group.pack(fill="x", pady=(0, 20))
        
        ttk.Label(perf_settings_group, text="Default Processing Settings:", 
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        # Default confidence threshold
        conf_default_frame = ttk.Frame(perf_settings_group)
        conf_default_frame.pack(fill="x", padx=20, pady=5)
        
        ttk.Label(conf_default_frame, text="Default Confidence Threshold:").pack(side="left")
        self.default_confidence_var = tk.DoubleVar(value=0.5)
        default_conf_scale = ttk.Scale(conf_default_frame, from_=0.0, to=1.0, 
                                     variable=self.default_confidence_var, orient="horizontal", length=200)
        default_conf_scale.pack(side="left", padx=10)
        
        self.default_conf_label = ttk.Label(conf_default_frame, text="0.50")
        self.default_conf_label.pack(side="left", padx=5)
        default_conf_scale.configure(command=self._update_default_confidence_label)
        
        # Export Settings
        export_settings_group = ttk.LabelFrame(settings_container, text="Export Settings")
        export_settings_group.pack(fill="x", pady=(0, 20))
        
        self.include_raw_results_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(export_settings_group, text="Include raw OCR results in export", 
                       variable=self.include_raw_results_var).pack(anchor="w", padx=10, pady=5)
        
        self.include_confidence_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(export_settings_group, text="Include confidence scores", 
                       variable=self.include_confidence_var).pack(anchor="w", padx=10, pady=5)
        
        self.pretty_format_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(export_settings_group, text="Pretty format JSON export", 
                       variable=self.pretty_format_var).pack(anchor="w", padx=10, pady=5)
        
        # Save/Load Settings
        settings_buttons_frame = ttk.Frame(settings_container)
        settings_buttons_frame.pack(fill="x", pady=20)
        
        ttk.Button(settings_buttons_frame, text="💾 Save Settings", 
                  command=self.save_settings).pack(side="left", padx=(0, 10))
        ttk.Button(settings_buttons_frame, text="📂 Load Settings", 
                  command=self.load_settings).pack(side="left", padx=(0, 10))
        ttk.Button(settings_buttons_frame, text="🔄 Reset to Defaults", 
                  command=self.reset_settings).pack(side="left")
        
    def _setup_help_tab(self):
        """Setup the help and information tab"""
        self.help_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.help_frame, text="❓ Help")
        
        help_container = ttk.Frame(self.help_frame)
        help_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Help notebook
        help_notebook = ttk.Notebook(help_container)
        help_notebook.pack(fill="both", expand=True)
        
        # Quick Start Guide
        quick_start_frame = ttk.Frame(help_notebook)
        help_notebook.add(quick_start_frame, text="🚀 Quick Start")
        
        quick_start_text = scrolledtext.ScrolledText(quick_start_frame, wrap=tk.WORD)
        quick_start_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        quick_start_content = """
QUICK START GUIDE
=================

1. SELECT FILE TYPE
   • Choose between Image (PNG, JPG, JPEG, BMP) or PDF files
   • Use the radio buttons in the File Selection section

2. CONFIGURE PROCESSING
   • GPU vs CPU: GPU is faster but requires CUDA-compatible graphics card
   • Languages: Select English and/or Arabic based on your document
   • Confidence Threshold: Higher values = more accurate but fewer results

3. ENABLE SMART FEATURES
   • Smart Analysis: Advanced document structure recognition
   • Spell Check: Automatic correction of OCR errors (requires pyspellchecker)
   • Language Detection: Automatic language identification (requires langdetect)
   • Structure Analysis: Identifies headers, footers, paragraphs
   • Form Extraction: Detects form fields like names, emails, phones
   • Invoice Parsing: Extracts invoice numbers, dates, totals

4. PROCESS DOCUMENT
   • Click "Select File" to choose your document
   • Click "Start Processing" to begin OCR
   • View results in the different tabs

5. EXPORT RESULTS
   • Use "Export Report" to save detailed analysis as JSON
   • Configure export options in the Settings tab

TIPS:
• For best results, use high-resolution, clear images
• PDF files are processed page by page
• Processing time depends on document size and complexity
• GPU processing is significantly faster for large documents
        """
        
        quick_start_text.insert("1.0", quick_start_content)
        quick_start_text.configure(state="disabled")
        
        # Features Guide
        features_frame = ttk.Frame(help_notebook)
        help_notebook.add(features_frame, text="✨ Features")
        
        features_text = scrolledtext.ScrolledText(features_frame, wrap=tk.WORD)
        features_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        features_content = """
ADVANCED FEATURES
=================

🔍 SMART TEXT PROCESSING
• Language Detection: Automatically identifies document language
• Spell Checking: Corrects common OCR errors using dictionary
• Text Cleaning: Removes artifacts and normalizes formatting
• Confidence Filtering: Filters results based on OCR confidence

📋 DOCUMENT STRUCTURE ANALYSIS
• Header Detection: Identifies document headers (top 15% of page)
• Footer Detection: Identifies document footers (bottom 15% of page)
• Paragraph Grouping: Groups text blocks into logical paragraphs
• Reading Order: Maintains proper text flow and structure

📝 FORM FIELD EXTRACTION
Automatically detects and extracts:
• Names and personal information
• Email addresses
• Phone numbers
• Addresses
• Dates of birth
• Social security numbers
• Custom field patterns

🧾 INVOICE/RECEIPT PARSING
Specialized extraction for business documents:
• Invoice numbers
• Invoice dates
• Total amounts
• Vendor information
• Line items
• Tax information

📊 TABLE DETECTION
• Identifies tabular data structures
• Extracts table content with row/column organization
• Maintains data relationships
• Exports structured table data

🌐 MULTI-LANGUAGE SUPPORT
• English text recognition
• Arabic text recognition
• Mixed language documents
• Language confidence scoring
• Automatic language switching

⚡ PERFORMANCE OPTIMIZATION
• GPU acceleration support
• Batch processing for PDFs
• Confidence-based filtering
• Memory-efficient processing
• Progress tracking

💾 EXPORT CAPABILITIES
• JSON format with full analysis
• Structured data export
• Raw OCR results
• Confidence scores
• Processing metadata
        """
        
        features_text.insert("1.0", features_content)
        features_text.configure(state="disabled")
        
        # Troubleshooting
        troubleshooting_frame = ttk.Frame(help_notebook)
        help_notebook.add(troubleshooting_frame, text="🔧 Troubleshooting")
        
        troubleshooting_text = scrolledtext.ScrolledText(troubleshooting_frame, wrap=tk.WORD)
        troubleshooting_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        troubleshooting_content = """
TROUBLESHOOTING GUIDE
====================

❌ COMMON ISSUES AND SOLUTIONS

1. "Cannot import easyocr" Error
   SOLUTION: Install EasyOCR
   pip install easyocr

2. "CUDA out of memory" Error
   SOLUTION: Switch to CPU processing or reduce image size

3. "Cannot import bidi" Error
   SOLUTION: Install python-bidi
   pip install python-bidi==0.4.2

4. Spell check not working
   SOLUTION: Install pyspellchecker
   pip install pyspellchecker

5. Language detection not working
   SOLUTION: Install langdetect
   pip install langdetect

6. Poor OCR accuracy
   SOLUTIONS:
   • Use higher resolution images
   • Ensure good lighting and contrast
   • Remove noise and artifacts
   • Increase confidence threshold
   • Try different preprocessing

7. Slow processing
   SOLUTIONS:
   • Enable GPU processing
   • Reduce image resolution
   • Disable unnecessary smart features
   • Process smaller batches

8. Memory issues with large PDFs
   SOLUTIONS:
   • Process pages individually
   • Reduce image resolution
   • Use CPU processing
   • Close other applications

⚠️ SYSTEM REQUIREMENTS
• Python 3.7 or higher
• OpenCV (cv2)
• PyMuPDF (fitz)
• Pillow (PIL)
• NumPy
• Tkinter (usually included with Python)

🖥️ OPTIONAL REQUIREMENTS
• CUDA-compatible GPU for acceleration
• pyspellchecker for spell checking
• langdetect for language detection

📞 GETTING HELP
If you encounter issues not covered here:
1. Check the console output for detailed error messages
2. Verify all dependencies are installed
3. Try with a simple test image first
4. Check file permissions and paths
5. Restart the application

💡 PERFORMANCE TIPS
• Use PNG or high-quality JPEG images
• Ensure text is clearly visible and not skewed
• Remove backgrounds and noise when possible
• Use appropriate confidence thresholds
• Enable only needed smart features
        """
        
        troubleshooting_text.insert("1.0", troubleshooting_content)
        troubleshooting_text.configure(state="disabled")
        
        # About
        about_frame = ttk.Frame(help_notebook)
        help_notebook.add(about_frame, text="ℹ️ About")
        
        about_text = scrolledtext.ScrolledText(about_frame, wrap=tk.WORD)
        about_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        about_content = """
ENHANCED OCR PROCESSOR
======================

Version: 2.0.0
Author: AI Assistant
License: MIT

DESCRIPTION
This application provides advanced Optical Character Recognition (OCR) 
capabilities with intelligent document analysis features. It combines 
the power of EasyOCR with smart text processing, document structure 
recognition, and specialized data extraction.

KEY TECHNOLOGIES
• EasyOCR: Deep learning-based OCR engine
• OpenCV: Computer vision and image processing
• PyMuPDF: PDF processing and conversion
• Tkinter: Cross-platform GUI framework
• Python: Core programming language

SUPPORTED FORMATS
Input:
• Images: PNG, JPG, JPEG, BMP
• Documents: PDF (multi-page support)

Output:
• JSON: Structured analysis reports
• Text: Plain text extraction
• Data: Structured form and invoice data

FEATURES OVERVIEW
✅ Multi-language OCR (English, Arabic)
✅ GPU acceleration support
✅ Smart text processing and correction
✅ Document structure analysis
✅ Form field extraction
✅ Invoice/receipt parsing
✅ Table detection and extraction
✅ Language detection
✅ Confidence-based filtering
✅ Batch PDF processing
✅ Comprehensive reporting

ACKNOWLEDGMENTS
• EasyOCR team for the excellent OCR engine
• OpenCV community for computer vision tools
• PyMuPDF developers for PDF processing
• Python community for the ecosystem

COPYRIGHT NOTICE
This software is provided "as is" without warranty of any kind. 
Use at your own risk. The authors are not responsible for any 
data loss or damage resulting from the use of this software.

For updates and documentation, please check the project repository.
        """
        
        about_text.insert("1.0", about_content)
        about_text.configure(state="disabled")
    
    def _check_dependencies(self):
        """Check and display dependency status"""
        missing_deps = []
        
        if not SPELLCHECK_AVAILABLE:
            missing_deps.append("pyspellchecker (for spell checking)")
        
        if not LANGDETECT_AVAILABLE:
            missing_deps.append("langdetect (for language detection)")
        
        if missing_deps:
            self.progress_var.set(f"Optional dependencies missing: {', '.join(missing_deps)}")
        else:
            self.progress_var.set("All dependencies available")
    
    def _update_confidence_label(self, value):
        """Update confidence threshold label"""
        self.confidence_label.config(text=f"{float(value):.2f}")
    
    def _update_default_confidence_label(self, value):
        """Update default confidence threshold label"""
        self.default_conf_label.config(text=f"{float(value):.2f}")
    
    def select_file(self):
        """Handle file selection"""
        file_types = [
            ('All Supported', '*.png *.jpg *.jpeg *.bmp *.tiff *.gif *.pdf *.xlsx *.xls *.csv *.txt'),
            ('Image files', '*.png *.jpg *.jpeg *.bmp *.tiff *.gif'),
            ('PDF files', '*.pdf'),
            ('Excel files', '*.xlsx *.xls'),
            ('CSV files', '*.csv'),
            ('Text files', '*.txt'),
            ('All files', '*.*')
        ]
        filename = filedialog.askopenfilename(
            title="Select File",
            filetypes=file_types
        )
        if filename:
            # Display selected file
            display_name = os.path.basename(filename)
            if len(display_name) > 30:
                display_name = display_name[:27] + "..."
            self.selected_file_var.set(display_name)
            # Store full path
            self.selected_file_path = filename
            # Enable process button
            self.process_button.configure(state="normal")
            self.progress_var.set(f"File selected: {display_name}")
    
    def start_processing(self):
        """Start OCR processing in a separate thread"""
        if not hasattr(self, 'selected_file_path'):
            messagebox.showerror("Error", "Please select a file first!")
            return
        
        # Disable buttons during processing
        self.process_button.configure(state="disabled")
        self.select_button.configure(state="disabled")
        
        # Start progress bar
        self.progress_bar.start()
        self.progress_var.set("Processing... Please wait")
        
        # Clear previous results
        self.clear_results()
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self._process_file_thread)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
        # Check thread status
        self.root.after(100, self._check_processing_thread)
    
    def _process_file_thread(self):
        """Process file in separate thread"""
        try:
            # Get selected languages
            languages = []
            if self.lang_en.get():
                languages.append('en')
            if self.lang_ar.get():
                languages.append('ar')
            
            if not languages:
                languages = ['en']  # Default to English
            
            file_path = self.selected_file_path
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.xlsx', '.xls', '.csv']:
                # Process Excel/CSV
                self.progress_var.set("Reading Excel/CSV file...")
                self.progress_bar.start()
                self.root.update_idletasks()
                try:
                    if ext == '.csv':
                        self.progress_var.set("Processing CSV file...")
                        self.root.update_idletasks()
                        df = pd.read_csv(file_path)

                        # Convert DataFrame to pretty text
                        text = df.to_string(index=False)

                        # Add header with row and column count for clarity
                        num_rows, num_cols = df.shape
                        header_info = f"[CSV Table Data - {num_rows} Rows, {num_cols} Columns]\n"
                        text = header_info + text

                        self.current_results = {
                            "text": text,
                            "raw_results": df.to_dict(orient='records'),
                            "processing_time": 0,
                            "source_type": "table",
                            "source_path": file_path,
                            "sheets": [{"name": "CSV Data", "data": df.to_dict(orient='records'), "rows": num_rows, "cols": num_cols}]
                        }

                    elif ext in ['.xlsx', '.xls']:
                        self.progress_var.set("Reading Excel file structure...")
                        self.root.update_idletasks()

                        # Read all sheets from Excel file
                        if ext == '.xlsx':
                            excel_file = pd.ExcelFile(file_path, engine='openpyxl')
                        else:  # .xls
                            try:
                                excel_file = pd.ExcelFile(file_path, engine='xlrd')
                            except ImportError:
                                # Fallback if xlrd is not installed
                                excel_file = pd.ExcelFile(file_path)

                        sheet_names = excel_file.sheet_names
                        self.progress_var.set(f"Found {len(sheet_names)} sheet(s). Processing all sheets...")
                        self.root.update_idletasks()

                        all_sheets_data = []
                        combined_text = ""
                        combined_raw_results = []
                        total_rows = 0
                        total_cols = 0

                        for i, sheet_name in enumerate(sheet_names):
                            self.progress_var.set(f"Processing sheet {i+1}/{len(sheet_names)}: '{sheet_name}'...")
                            self.root.update_idletasks()

                            df = pd.read_excel(excel_file, sheet_name=sheet_name)

                            if not df.empty:
                                # Convert DataFrame to pretty text
                                sheet_text = df.to_string(index=False)

                                # Add sheet header
                                num_rows, num_cols = df.shape
                                sheet_header = f"\n=== SHEET: '{sheet_name}' ({num_rows} Rows, {num_cols} Columns) ===\n"
                                combined_text += sheet_header + sheet_text + "\n"

                                # Store sheet data
                                sheet_data = {
                                    "name": sheet_name,
                                    "data": df.to_dict(orient='records'),
                                    "rows": num_rows,
                                    "cols": num_cols
                                }
                                all_sheets_data.append(sheet_data)
                                combined_raw_results.extend(df.to_dict(orient='records'))

                                total_rows += num_rows
                                total_cols = max(total_cols, num_cols)
                            else:
                                # Empty sheet
                                sheet_header = f"\n=== SHEET: '{sheet_name}' (Empty) ===\n"
                                combined_text += sheet_header + "[No data in this sheet]\n"

                                sheet_data = {
                                    "name": sheet_name,
                                    "data": [],
                                    "rows": 0,
                                    "cols": 0
                                }
                                all_sheets_data.append(sheet_data)

                        # Add overall header
                        header_info = f"[Excel File - {len(sheet_names)} Sheet(s), Total: {total_rows} Rows]\n"
                        combined_text = header_info + combined_text

                        self.current_results = {
                            "text": combined_text,
                            "raw_results": combined_raw_results,
                            "processing_time": 0,
                            "source_type": "table",
                            "source_path": file_path,
                            "sheets": all_sheets_data,
                            "total_sheets": len(sheet_names)
                        }

                        excel_file.close()

                except Exception as e:
                    self.current_results = {
                        "error": f"Failed to read Excel/CSV: {str(e)}. "
                                 "Make sure you have 'pandas', 'openpyxl' (for .xlsx), and 'xlrd' (for .xls) installed."
                    }
                finally:
                    self.progress_bar.stop()
                return

            # Initialize OCR processor
            self.progress_var.set("Initializing OCR engine...")
            self.root.update_idletasks()

            self.ocr = EnhancedOCRProcessor(
                languages=languages,
                use_gpu=self.gpu_var.get(),
                confidence_threshold=self.confidence_var.get()
            )

            # Process file
            enable_smart = self.smart_processing_var.get()

            # Define progress callback function
            def progress_callback(message):
                self.progress_var.set(message)
                self.root.update_idletasks()

            if self.file_type.get() == "image":
                self.current_results = self.ocr.process_image(
                    self.selected_file_path,
                    enable_smart_processing=enable_smart,
                    progress_callback=progress_callback
                )
            else:
                self.current_results = self.ocr.process_pdf(
                    self.selected_file_path,
                    enable_smart_processing=enable_smart,
                    progress_callback=progress_callback
                )
            
        except Exception as e:
            self.current_results = {"error": f"Processing error: {str(e)}"}
    
    def _check_processing_thread(self):
        """Check if processing thread is complete"""
        if self.processing_thread and self.processing_thread.is_alive():
            # Still processing, check again
            self.root.after(100, self._check_processing_thread)
        else:
            # Processing complete
            self._processing_complete()
    
    def _processing_complete(self):
        """Handle processing completion"""
        # Stop progress bar
        self.progress_bar.stop()
        
        # Re-enable buttons
        self.process_button.configure(state="normal")
        self.select_button.configure(state="normal")
        
        if self.current_results:
            if "error" in self.current_results:
                self.progress_var.set(f"Error: {self.current_results['error']}")
                messagebox.showerror("Processing Error", self.current_results['error'])
            else:
                # Display results
                self._display_results()
                self.export_button.configure(state="normal")
                
                # Update progress
                processing_time = self.current_results.get('processing_time', 0)
                self.progress_var.set(f"Processing complete in {processing_time:.2f}s")
        else:
            self.progress_var.set("Processing failed - no results")
    
    def _display_results(self):
        """Display processing results in all tabs"""
        if not self.current_results:
            return
        
        # Display basic OCR results
        self._display_basic_results()
        
        # Display processing info
        self._display_processing_info()
        
        # Display smart analysis if available
        if "smart_processing" in self.current_results or \
           (self.current_results.get("pages") and "smart_processing" in self.current_results["pages"][0]):
            self._display_smart_analysis()

        # Display table data if it's a table source type
        if self.current_results.get("source_type") == "table":
            self._display_table_in_treeview()
            self.results_notebook.select(self.table_editor_frame) # Switch to table editor tab
    
    def _display_basic_results(self):
        """Display basic OCR text results"""
        self._save_text_state() # Save state before updating
        self.basic_results_text.delete("1.0", tk.END)
        
        if self.current_results.get("source_type") == "image":
            text = self.current_results.get("text", "No text extracted")
            self.basic_results_text.insert("1.0", text)
        elif self.current_results.get("source_type") == "pdf":
            for page in self.current_results.get("pages", []):
                self.basic_results_text.insert(tk.END, f"\n--- Page {page['page_num']} ---\n")
                self.basic_results_text.insert(tk.END, page.get("text", "No text extracted"))
                self.basic_results_text.insert(tk.END, "\n")
        elif self.current_results.get("source_type") == "table":
            self.basic_results_text.insert("1.0", "[Excel/CSV Table Data - View in '\ud83d\udcca Table Editor' tab]")
        self._update_undo_button_state() # Update button state after display
    
    def _display_processing_info(self):
        """Display processing information and statistics"""
        self.info_text.delete("1.0", tk.END)
        
        info_content = "PROCESSING INFORMATION\n"
        info_content += "=" * 50 + "\n\n"
        
        # Basic info
        info_content += f"Source Type: {self.current_results.get('source_type', 'Unknown')}\n"
        info_content += f"Source Path: {self.current_results.get('source_path', 'Unknown')}\n"
        info_content += f"Processing Time: {self.current_results.get('processing_time', 0):.2f} seconds\n\n"
        
        if self.current_results.get("source_type") == "image":
            # Image-specific info
            dims = self.current_results.get("image_dimensions", {})
            info_content += f"Image Dimensions: {dims.get('width', 0)}x{dims.get('height', 0)} pixels\n"
            
            raw_results = self.current_results.get("raw_results", [])
            info_content += f"Text Blocks Detected: {len(raw_results)}\n"
            
            if raw_results:
                confidences = [result[2] for result in raw_results]
                avg_confidence = sum(confidences) / len(confidences)
                info_content += f"Average Confidence: {avg_confidence:.3f}\n"
                info_content += f"Min Confidence: {min(confidences):.3f}\n"
                info_content += f"Max Confidence: {max(confidences):.3f}\n"
        
        elif self.current_results.get("source_type") == "pdf":
            # PDF-specific info
            info_content += f"Total Pages: {self.current_results.get('total_pages', 0)}\n"
            
            pages = self.current_results.get("pages", [])
            if pages:
                total_blocks = sum(len(page.get("raw_results", [])) for page in pages)
                info_content += f"Total Text Blocks: {total_blocks}\n"
                
                all_confidences = []
                for page in pages:
                    raw_results = page.get("raw_results", [])
                    all_confidences.extend([result[2] for result in raw_results])
                
                if all_confidences:
                    avg_confidence = sum(all_confidences) / len(all_confidences)
                    info_content += f"Average Confidence: {avg_confidence:.3f}\n"
                    info_content += f"Min Confidence: {min(all_confidences):.3f}\n"
                    info_content += f"Max Confidence: {max(all_confidences):.3f}\n"
        
        # Smart processing info
        if "smart_processing" in self.current_results:
            smart = self.current_results["smart_processing"]
            info_content += "\nSMART PROCESSING RESULTS\n"
            info_content += "=" * 30 + "\n"
            
            # Language detection
            if "language_detection" in smart:
                lang_data = smart["language_detection"]
                info_content += f"Primary Language: {lang_data.get('primary_language', 'Unknown')}\n"
            
            # Confidence filtering
            if "confidence_filtering" in smart:
                conf_data = smart["confidence_filtering"]
                info_content += f"Confidence Threshold: {conf_data.get('threshold', 0)}\n"
                info_content += f"High Confidence Blocks: {conf_data.get('high_confidence_blocks', 0)}/{conf_data.get('total_blocks', 0)}\n"
                info_content += f"Quality Score: {conf_data.get('filtered_percentage', 0):.1f}%\n"
            
            # Spell check
            if "spell_check" in smart:
                spell_data = smart["spell_check"]
                corrections = spell_data.get("corrections", [])
                info_content += f"Spelling Corrections Made: {len(corrections)}\n"
        
        # Aggregated analysis for PDFs
        if "aggregated_analysis" in self.current_results:
            agg = self.current_results["aggregated_analysis"]
            info_content += "\nDOCUMENT ANALYSIS SUMMARY\n"
            info_content += "=" * 30 + "\n"
            info_content += f"Document Type: {agg.get('document_type', 'Unknown')}\n"
            info_content += f"Languages Detected: {', '.join(agg.get('languages_detected', []))}\n"
            info_content += f"Total Form Fields: {len(agg.get('all_form_fields', []))}\n"
            info_content += f"Total Tables: {len(agg.get('all_tables', []))}\n"
            info_content += f"Total Corrections: {agg.get('total_corrections', 0)}\n"
        
        self.info_text.insert("1.0", info_content)
    
    def _display_smart_analysis(self):
        """Display smart analysis results"""
        # Get smart processing data
        smart_data = None
        structure_data = None
        
        if self.current_results.get("source_type") == "image":
            smart_data = self.current_results.get("smart_processing")
            structure_data = self.current_results.get("document_structure")
        elif self.current_results.get("source_type") == "pdf":
            pages = self.current_results.get("pages", [])
            if pages and "smart_processing" in pages[0]:
                smart_data = pages[0]["smart_processing"]
                structure_data = pages[0].get("document_structure")
        
        # Display language analysis
        self._display_language_analysis(smart_data)
        
        # Display document structure
        self._display_structure_analysis(structure_data)
        
        # Display form fields
        self._display_form_analysis(structure_data)
        
        # Display invoice data
        self._display_invoice_analysis(structure_data)
        
        # Display tables
        self._display_table_analysis(structure_data)
    
    def _display_language_analysis(self, smart_data):
        """Display language analysis results"""
        self.language_analysis_text.delete("1.0", tk.END)
        
        if not smart_data:
            self.language_analysis_text.insert("1.0", "No language analysis data available.")
            return
        
        content = "LANGUAGE ANALYSIS RESULTS\n"
        content += "=" * 40 + "\n\n"
        
        # Language detection
        if "language_detection" in smart_data:
            lang_data = smart_data["language_detection"]
            content += f"\ud83c\udf10 PRIMARY LANGUAGE: {lang_data.get('primary_language', 'Unknown').upper()}\n\n"
            
            lang_confidence = lang_data.get("language_confidence", [])
            if lang_confidence:
                content += "Language Confidence Scores:\n"
                content += "-" * 30 + "\n"
                for lang_conf in lang_confidence:
                    content += f"  {lang_conf['lang']}: {lang_conf['confidence']:.3f}\n"
                content += "\n"
        
        # Spell check results
        if "spell_check" in smart_data:
            spell_data = smart_data["spell_check"]
            corrections = spell_data.get("corrections", [])
            
            content += f"\ud83d\udcdd SPELL CHECK RESULTS\n"
            content += f"Total corrections made: {len(corrections)}\n\n"
            
            if corrections:
                content += "Corrections Applied:\n"
                content += "-" * 20 + "\n"
                for i, correction in enumerate(corrections[:10]):  # Show first 10
                    content += f"{i+1:2d}. '{correction['original']}' \u2192 '{correction['corrected']}'\n"
                
                if len(corrections) > 10:
                    content += f"... and {len(corrections) - 10} more corrections\n"
                content += "\n"
            
            # Show corrected text sample
            if spell_data.get("corrected") != spell_data.get("original"):
                content += "\ud83d\udcc4 CORRECTED TEXT SAMPLE (first 200 chars):\n"
                content += "-" * 45 + "\n"
                corrected_sample = spell_data.get("corrected", "")[:200]
                content += corrected_sample
                if len(spell_data.get("corrected", "")) > 200:
                    content += "..."
                content += "\n\n"
        
        # Confidence filtering
        if "confidence_filtering" in smart_data:
            conf_data = smart_data["confidence_filtering"]
            content += "\ud83c\udfaf CONFIDENCE FILTERING\n"
            content += f"Threshold used: {conf_data.get('threshold', 0):.2f}\n"
            content += f"Total text blocks: {conf_data.get('total_blocks', 0)}\n"
            content += f"High confidence blocks: {conf_data.get('high_confidence_blocks', 0)}\n"
            content += f"Quality percentage: {conf_data.get('filtered_percentage', 0):.1f}%\n\n"
        
        # Text cleaning info
        if "cleaned_text" in smart_data:
            content += "\ud83e\uddf9 TEXT CLEANING\n"
            content += "Applied text normalization and artifact removal\n"
            cleaned_sample = smart_data.get("cleaned_text", "")[:200]
            content += f"Cleaned text sample: {cleaned_sample}"
            if len(smart_data.get("cleaned_text", "")) > 200:
                content += "..."
            content += "\n"
        
        self.language_analysis_text.insert("1.0", content)
    
    def _display_structure_analysis(self, structure_data):
        """Display document structure analysis"""
        if not structure_data:
            self.headers_text.delete("1.0", tk.END)
            self.headers_text.insert("1.0", "No document structure data available.")
            self.paragraphs_text.delete("1.0", tk.END)
            self.paragraphs_text.insert("1.0", "No paragraph data available.")
            return
        
        # Headers and Footers
        self.headers_text.delete("1.0", tk.END)
        
        headers_content = "DOCUMENT HEADERS\n"
        headers_content += "=" * 30 + "\n\n"
        
        headers = structure_data.get("headers", [])
        if headers:
            for i, header in enumerate(headers, 1):
                headers_content += f"Header {i}:\n"
                headers_content += f"  Text: {header['text']}\n"
                headers_content += f"  Confidence: {header['confidence']:.3f}\n"
                headers_content += f"  Position: ({header['position']['x']}, {header['position']['y']})\n\n"
        else:
            headers_content += "No headers detected.\n\n"
        
        headers_content += "\nDOCUMENT FOOTERS\n"
        headers_content += "=" * 30 + "\n\n"
        
        footers = structure_data.get("footers", [])
        if footers:
            for i, footer in enumerate(footers, 1):
                headers_content += f"Footer {i}:\n"
                headers_content += f"  Text: {footer['text']}\n"
                headers_content += f"  Confidence: {footer['confidence']:.3f}\n"
                headers_content += f"  Position: ({footer['position']['x']}, {footer['position']['y']})\n\n"
        else:
            headers_content += "No footers detected.\n"
        
        self.headers_text.insert("1.0", headers_content)
        
        # Paragraphs
        self.paragraphs_text.delete("1.0", tk.END)
        
        paragraphs_content = "DOCUMENT PARAGRAPHS\n"
        paragraphs_content += "=" * 35 + "\n\n"
        
        paragraphs = structure_data.get("paragraphs", [])
        if paragraphs:
            for i, paragraph in enumerate(paragraphs, 1):
                paragraphs_content += f"Paragraph {i}:\n"
                paragraphs_content += f"  Word Count: {paragraph['word_count']}\n"
                paragraphs_content += f"  Confidence: {paragraph['confidence']:.3f}\n"
                paragraphs_content += f"  Text: {paragraph['text'][:100]}"
                if len(paragraph['text']) > 100:
                    paragraphs_content += "..."
                paragraphs_content += "\n\n"
        else:
            paragraphs_content += "No paragraphs detected.\n"
        
        self.paragraphs_text.insert("1.0", paragraphs_content)
    
    def _display_form_analysis(self, structure_data):
        """Display form field analysis"""
        self.forms_text.delete("1.0", tk.END)
        
        if not structure_data:
            self.forms_text.insert("1.0", "No form field data available.")
            return
        
        form_content = "DETECTED FORM FIELDS\n"
        form_content += "=" * 35 + "\n\n"
        
        form_fields = structure_data.get("form_fields", [])
        if form_fields:
            for i, field in enumerate(form_fields, 1):
                form_content += f"Field {i}: {field['field_name'].upper()}\n"
                form_content += f"  Type: {field['field_type']}\n"
                form_content += f"  Extracted Value: {field['extracted_value']}\n"
                form_content += f"  Raw Text: {field['raw_text']}\n"
                form_content += f"  Confidence: {field['confidence']:.3f}\n"
                form_content += "-" * 40 + "\n\n"
        else:
            form_content += "No form fields detected.\n\n"
            form_content += "SUPPORTED FORM FIELDS:\n"
            form_content += "• Names and personal information\n"
            form_content += "• Email addresses\n"
            form_content += "• Phone numbers\n"
            form_content += "• Addresses\n"
            form_content += "• Dates of birth\n"
            form_content += "• Social security numbers\n"
        
        self.forms_text.insert("1.0", form_content)
    
    def _display_invoice_analysis(self, structure_data):
        """Display invoice data analysis"""
        self.invoice_text.delete("1.0", tk.END)
        
        if not structure_data:
            self.invoice_text.insert("1.0", "No invoice data available.")
            return
        
        invoice_content = "EXTRACTED INVOICE DATA\n"
        invoice_content += "=" * 40 + "\n\n"
        
        invoice_data = structure_data.get("invoice_data", {})
        if any(invoice_data.values()):
            for key, value in invoice_data.items():
                if value:
                    field_name = key
                    field_name = key.replace('_', ' ').title()
                    invoice_content += f"{field_name}: {value}\n"
            
            invoice_content += "\n" + "=" * 40 + "\n"
            invoice_content += "\u2705 Invoice document detected and parsed successfully!"
        else:
            invoice_content += "No invoice data detected.\n\n"
            invoice_content += "SUPPORTED INVOICE FIELDS:\n"
            invoice_content += "• Invoice numbers\n"
            invoice_content += "• Invoice dates\n"
            invoice_content += "• Total amounts\n"
            invoice_content += "• Vendor information\n"
            invoice_content += "• Line items\n"
            invoice_content += "• Tax information\n\n"
            invoice_content += "\ud83d\udca1 TIP: For better invoice recognition, ensure:\n"
            invoice_content += "• Clear, high-resolution images\n"
            invoice_content += "• Standard invoice format\n"
            invoice_content += "• Visible text without skew or distortion\n"
        
        self.invoice_text.insert("1.0", invoice_content)
    
    def _display_table_analysis(self, structure_data):
        """Display table analysis"""
        self.tables_text.delete("1.0", tk.END)

        # If the current results are from a table file (Excel/CSV), show the table here
        if self.current_results and self.current_results.get("source_type") == "table":
            table_content = "EXCEL/CSV TABLE DATA\n" + "=" * 30 + "\n\n"
            table_content += self.current_results.get("text", "No table data extracted")
            self.tables_text.insert("1.0", table_content)
            return

        if not structure_data:
            self.tables_text.insert("1.0", "No table data available.")
            return

        table_content = "DETECTED TABLES\n"
        table_content += "=" * 30 + "\n\n"

        tables = structure_data.get("tables", [])
        if tables:
            for i, table in enumerate(tables, 1):
                table_content += f"Table {i}:\n"
                table_content += f"  Dimensions: {table['rows']} rows \u00d7 {table['columns']} columns\n"
                table_content += f"  Type: {table['type']}\n\n"
                table_content += "  Data Preview:\n"
                table_content += "  " + "-" * 50 + "\n"
                table_data = table.get("data", [])
                for row_idx, row in enumerate(table_data[:5]):  # Show first 5 rows
                    row_str = " | ".join([str(cell)[:15] for cell in row])
                    table_content += f"  {row_str}\n"
                if len(table_data) > 5:
                    table_content += f"  ... and {len(table_data) - 5} more rows\n"
                table_content += "\n" + "=" * 50 + "\n\n"
        else:
            table_content += "No tables detected.\n\n"
            table_content += "TABLE DETECTION CRITERIA:\n"
            table_content += "• Minimum 3 columns\n"
            table_content += "• Minimum 2 rows\n"
            table_content += "• Aligned text blocks\n"
            table_content += "• Consistent spacing\n\n"
            table_content += "\ud83d\udca1 TIP: For better table detection:\n"
            table_content += "• Use clear table borders\n"
            table_content += "• Ensure consistent alignment\n"
            table_content += "• Avoid merged cells when possible\n"
        self.tables_text.insert("1.0", table_content)
    
    def export_report(self):
        """Export detailed analysis report"""
        if not self.current_results:
            messagebox.showwarning("No Data", "No results to export. Please process a document first.")
            return
        
        # Get export filename
        filename = filedialog.asksaveasfilename(
            title="Export Analysis Report",
            defaultextension=".json",
            filetypes=[
                ("JSON files", "*.json"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if filename:
            try:
                self.progress_var.set("Exporting report...")
                self.progress_bar.start()
                self.root.update_idletasks()

                # Prepare export data
                export_data = self.current_results.copy()
                
                # Apply export settings
                if not self.include_raw_results_var.get():
                    # Remove raw results to reduce file size
                    if "raw_results" in export_data:
                        del export_data["raw_results"]
                    
                    if "pages" in export_data:
                        for page in export_data["pages"]:
                            if "raw_results" in page:
                                del page["raw_results"]
                
                if not self.include_confidence_var.get():
                    # Remove confidence scores
                    self._remove_confidence_scores(export_data)
                
                # Add export metadata
                export_data["export_info"] = {
                    "export_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "export_version": "2.0.0",
                    "settings_used": {
                        "confidence_threshold": self.confidence_var.get(),
                        "gpu_processing": self.gpu_var.get(),
                        "smart_processing": self.smart_processing_var.get(),
                        "languages": [lang for lang, var in [("en", self.lang_en), ("ar", self.lang_ar)] if var.get()]
                    }
                }
                
                # Export based on file extension
                if filename.lower().endswith('.json'):
                    with open(filename, 'w', encoding='utf-8') as f:
                        if self.pretty_format_var.get():
                            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
                        else:
                            json.dump(export_data, f, ensure_ascii=False, default=str)
                else:
                    # Export as text
                    with open(filename, 'w', encoding='utf-8') as f:
                        self._write_text_report(f, export_data)
                
                messagebox.showinfo("Export Successful", f"Report exported successfully to:\n{filename}")
                self.progress_var.set(f"Report exported to {os.path.basename(filename)}")
                
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export report:\n{str(e)}")
                self.progress_var.set("Export failed.")
            finally:
                self.progress_bar.stop()
    
    def _remove_confidence_scores(self, data):
        """Recursively remove confidence scores from data"""
        if isinstance(data, dict):
            keys_to_remove = [k for k in data.keys() if 'confidence' in k.lower()]
            for key in keys_to_remove:
                del data[key]
            
            for value in data.values():
                self._remove_confidence_scores(value)
        elif isinstance(data, list):
            for item in data:
                self._remove_confidence_scores(item)
    
    def _write_text_report(self, file, data):
        """Write a formatted text report"""
        file.write("ENHANCED OCR PROCESSING REPORT\n")
        file.write("=" * 50 + "\n\n")
        
        # Basic information
        file.write(f"Source: {data.get('source_path', 'Unknown')}\n")
        file.write(f"Type: {data.get('source_type', 'Unknown')}\n")
        file.write(f"Processing Time: {data.get('processing_time', 0):.2f} seconds\n")
        
        if data.get('source_type') == 'pdf':
            file.write(f"Total Pages: {data.get('total_pages', 0)}\n")
        
        file.write("\n" + "=" * 50 + "\n")
        file.write("EXTRACTED TEXT\n")
        file.write("=" * 50 + "\n\n")
        
        # Write extracted text
        if data.get('source_type') == 'image':
            file.write(data.get('text', 'No text extracted'))
        elif data.get('source_type') == 'pdf':
            for page in data.get('pages', []):
                file.write(f"\n--- Page {page['page_num']} ---\n")
                file.write(page.get('text', 'No text extracted'))
                file.write("\n")
        
        # Write smart analysis if available
        if 'smart_processing' in data or (data.get('pages') and 'smart_processing' in data['pages'][0]):
            file.write("\n\n" + "=" * 50 + "\n")
            file.write("SMART ANALYSIS RESULTS\n")
            file.write("=" * 50 + "\n")
            
            # Get smart data
            smart_data = data.get('smart_processing')
            if not smart_data and data.get('pages'):
                smart_data = data['pages'][0].get('smart_processing')
            
            if smart_data:
                # Language detection
                if 'language_detection' in smart_data:
                    lang_data = smart_data['language_detection']
                    file.write(f"\nPrimary Language: {lang_data.get('primary_language', 'Unknown')}\n")
                
                # Spell check
                if 'spell_check' in smart_data:
                    spell_data = smart_data['spell_check']
                    corrections = spell_data.get('corrections', [])
                    file.write(f"Spelling Corrections: {len(corrections)}\n")
        
        # Export timestamp
        file.write(f"\n\nReport generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    def clear_results(self):
        """Clear all results and reset UI"""
        # Clear text widgets
        self.basic_results_text.delete("1.0", tk.END)
        self.info_text.delete("1.0", tk.END)
        self.language_analysis_text.delete("1.0", tk.END)
        self.headers_text.delete("1.0", tk.END)
        self.paragraphs_text.delete("1.0", tk.END)
        self.forms_text.delete("1.0", tk.END)
        self.invoice_text.delete("1.0", tk.END)
        self.tables_text.delete("1.0", tk.END)
        
        # Clear the Treeview as well
        for item in self.table_tree.get_children():
            self.table_tree.delete(item)
        self.table_tree["columns"] = () # Also clear columns

        # Reset variables
        self.current_results = None
        self.export_button.configure(state="disabled")
        
        # Clear undo history
        self.text_history = []
        self.text_history_index = -1
        self._update_undo_button_state()
        
        # Reset progress
        self.progress_var.set("Results cleared")
    
    def save_settings(self):
        """Save current settings to file"""
        filename = filedialog.asksaveasfilename(
            title="Save Settings",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.* подойдут")]
        )
        
        if filename:
            try:
                self.progress_var.set("Saving settings...")
                self.progress_bar.start()
                self.root.update_idletasks()

                settings = {
                    "processing": {
                        "use_gpu": self.gpu_var.get(),
                        "confidence_threshold": self.confidence_var.get(),
                        "default_confidence": self.default_confidence_var.get(),
                        "languages": {
                            "english": self.lang_en.get(),
                            "arabic": self.lang_ar.get()
                        }
                    },
                    "smart_processing": {
                        "enabled": self.smart_processing_var.get(),
                        "spell_check": self.spell_check_var.get(),
                        "language_detection": self.lang_detect_var.get(),
                        "structure_analysis": self.structure_analysis_var.get(),
                        "form_extraction": self.form_extraction_var.get(),
                        "invoice_parsing": self.invoice_parsing_var.get()
                    },
                    "export": {
                        "include_raw_results": self.include_raw_results_var.get(),
                        "include_confidence": self.include_confidence_var.get(),
                        "pretty_format": self.pretty_format_var.get()
                    }
                }
                
                with open(filename, 'w') as f:
                    json.dump(settings, f, indent=2)
                messagebox.showinfo("Settings Saved", f"Settings saved to:\n{filename}")
                self.progress_var.set("Settings saved.")
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save settings:\n{str(e)}")
                self.progress_var.set("Save failed.")
            finally:
                self.progress_bar.stop()
    
    def load_settings(self):
        """Load settings from file"""
        filename = filedialog.askopenfilename(
            title="Load Settings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.* подойдут")]
        )
        
        if filename:
            try:
                self.progress_var.set("Loading settings...")
                self.progress_bar.start()
                self.root.update_idletasks()

                with open(filename, 'r') as f:
                    settings = json.load(f)
                
                # Apply processing settings
                if "processing" in settings:
                    proc = settings["processing"]
                    self.gpu_var.set(proc.get("use_gpu", True))
                    self.confidence_var.set(proc.get("confidence_threshold", 0.5))
                    self.default_confidence_var.set(proc.get("default_confidence", 0.5))
                    
                    if "languages" in proc:
                        langs = proc["languages"]
                        self.lang_en.set(langs.get("english", True))
                        self.lang_ar.set(langs.get("arabic", True))
                
                # Apply smart processing settings
                if "smart_processing" in settings:
                    smart = settings["smart_processing"]
                    self.smart_processing_var.set(smart.get("enabled", True))
                    self.spell_check_var.set(smart.get("spell_check", SPELLCHECK_AVAILABLE))
                    self.lang_detect_var.set(smart.get("language_detection", LANGDETECT_AVAILABLE))
                    self.structure_analysis_var.set(smart.get("structure_analysis", True))
                    self.form_extraction_var.set(smart.get("form_extraction", True))
                    self.invoice_parsing_var.set(smart.get("invoice_parsing", True))
                
                # Apply export settings
                if "export" in settings:
                    export = settings["export"]
                    self.include_raw_results_var.set(export.get("include_raw_results", True))
                    self.include_confidence_var.set(export.get("include_confidence", True))
                    self.pretty_format_var.set(export.get("pretty_format", True))
                
                # Update labels
                self._update_confidence_label(self.confidence_var.get())
                self._update_default_confidence_label(self.default_confidence_var.get())
                
                messagebox.showinfo("Settings Loaded", f"Settings loaded from:\n{filename}")
                self.progress_var.set("Settings loaded.")
                
            except Exception as e:
                messagebox.showerror("Load Error", f"Failed to load settings:\n{str(e)}")
                self.progress_var.set("Load failed.")
            finally:
                self.progress_bar.stop()
    
    def reset_settings(self):
        """Reset all settings to defaults"""
        if messagebox.askyesno("Reset Settings", "Are you sure you want to reset all settings to defaults?"):
            try:
                self.progress_var.set("Resetting settings...")
                self.progress_bar.start()
                self.root.update_idletasks()

                # Reset processing settings
                self.gpu_var.set(True)
                self.confidence_var.set(0.5)
                self.default_confidence_var.set(0.5)
                self.lang_en.set(True)
                self.lang_ar.set(True)
                
                # Reset smart processing settings
                self.smart_processing_var.set(True)
                self.spell_check_var.set(SPELLCHECK_AVAILABLE)
                self.lang_detect_var.set(LANGDETECT_AVAILABLE)
                self.structure_analysis_var.set(True)
                self.form_extraction_var.set(True)
                self.invoice_parsing_var.set(True)
                
                # Reset export settings
                self.include_raw_results_var.set(True)
                self.include_confidence_var.set(True)
                self.pretty_format_var.set(True)
                
                # Update labels
                self._update_confidence_label(0.5)
                self._update_default_confidence_label(0.5)
                
                messagebox.showinfo("Settings Reset", "All settings have been reset to defaults.")
                self.progress_var.set("Settings reset to defaults.")
            except Exception as e:
                messagebox.showerror("Reset Error", f"Failed to reset settings:\n{str(e)}")
                self.progress_var.set("Reset failed.")
            finally:
                self.progress_bar.stop()

    def summarize_with_gemini(self):
        text = self.basic_results_text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("No Text", "No OCR text to summarize.")
            return
        self.progress_var.set("Summarizing with Gemini...")
        self.root.update_idletasks()
        self.progress_bar.start() # Start progress bar
        self._save_text_state() # Save state before updating
        try:
            summary = call_gemini_api("Summarize the following text:", text)
            self.basic_results_text.delete("1.0", "end")
            self.basic_results_text.insert("1.0", summary)
            self.basic_results_text.see("1.0")
            self.progress_var.set("Summary complete.")
        except Exception as e:
            messagebox.showerror("Gemini API Error", f"Failed to summarize: {str(e)}")
            self.progress_var.set("Summary failed.")
        finally:
            self.progress_bar.stop()
            self._update_undo_button_state() # Update button state after display

    def write_to_ai(self):
        text = self.basic_results_text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("No Text", "No OCR text to send to AI.")
            return
        prompt = tk.simpledialog.askstring("Write to AI", "What do you want Gemini to do with the text?")
        if not prompt:
            return
        self.progress_var.set("Sending to Gemini...")
        self.root.update_idletasks()
        self.progress_bar.start() # Start progress bar
        self._save_text_state() # Save state before updating
        try:
            response = call_gemini_api(prompt, text)
            self.basic_results_text.delete("1.0", "end")
            self.basic_results_text.insert("1.0", response)
            self.basic_results_text.see("1.0")
            self.progress_var.set("AI response complete.")
        except Exception as e:
            messagebox.showerror("Gemini API Error", f"Failed to get AI response: {str(e)}")
            self.progress_var.set("AI response failed.")
        finally:
            self.progress_bar.stop()
            self._update_undo_button_state() # Update button state after display

    def rewrite_with_gemini(self):
        text = self.basic_results_text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("No Text", "No text to rewrite.")
            return

        style = tk.simpledialog.askstring(
            "Rewrite with AI",
            "Enter desired rewrite style (e.g., Professional, Casual, Humorous, Concise, Detailed):"
        )
        if not style:
            return

        self.progress_var.set(f"Rewriting with Gemini ({style})...")
        self.root.update_idletasks()
        self.progress_bar.start() # Start progress bar

        self._save_text_state() # Save state before updating

        try:
            gemini_prompt = f"Rewrite the following text in a {style} style: "
            response = call_gemini_api(gemini_prompt, text)
            self.basic_results_text.delete("1.0", "end")
            self.basic_results_text.insert("1.0", response)
            self.basic_results_text.see("1.0")
            self.progress_var.set("Rewrite complete.")
        except Exception as e:
            messagebox.showerror("AI Rewrite Error", f"Failed to rewrite with AI: {str(e)}")
            self.progress_var.set("Rewrite failed.")
        finally:
            self.progress_bar.stop()
            self._update_undo_button_state() # Update button state after display

    def _save_text_state(self):
        current_text = self.basic_results_text.get("1.0", tk.END).strip()
        if not self.text_history or self.text_history[self.text_history_index] != current_text:
            # If we are not at the end of history (meaning undo was used), truncate the redo history
            if self.text_history_index < len(self.text_history) - 1:
                self.text_history = self.text_history[:self.text_history_index + 1]
            
            self.text_history.append(current_text)
            if len(self.text_history) > self.max_history_size:
                self.text_history.pop(0) # Remove oldest entry
            self.text_history_index = len(self.text_history) - 1
        self._update_undo_button_state()

    def undo_text_change(self):
        if self.text_history_index > 0:
            self.text_history_index -= 1
            self._load_text_from_history(self.text_history_index)
        self._update_undo_button_state()

    def _load_text_from_history(self, index):
        if 0 <= index < len(self.text_history):
            self.basic_results_text.delete("1.0", tk.END)
            self.basic_results_text.insert("1.0", self.text_history[index])
            self.basic_results_text.see("1.0")
            self.text_history_index = index
        self._update_undo_button_state()

    def _update_undo_button_state(self):
        self.undo_button.config(state="normal" if self.text_history_index > 0 else "disabled")

    def _display_table_in_treeview(self):
        """Display table data from current_results in the Treeview widget"""
        for item in self.table_tree.get_children():
            self.table_tree.delete(item) # Clear existing data

        # Clear existing columns
        self.table_tree["columns"] = ()

        if self.current_results and self.current_results.get("source_type") == "table":
            # Check if we have multiple sheets
            sheets = self.current_results.get("sheets", [])
            if sheets and len(sheets) > 1:
                # Multiple sheets - display the first non-empty sheet by default
                # and add a note about multiple sheets
                selected_sheet = None
                for sheet in sheets:
                    if sheet.get("data") and len(sheet["data"]) > 0:
                        selected_sheet = sheet
                        break

                if not selected_sheet:
                    # All sheets are empty, use the first one
                    selected_sheet = sheets[0] if sheets else None

                if selected_sheet:
                    raw_data = selected_sheet["data"]
                    sheet_name = selected_sheet["name"]

                    # Add information about multiple sheets to the progress
                    self.progress_var.set(f"Displaying sheet: '{sheet_name}' ({len(sheets)} total sheets)")
                else:
                    raw_data = []
            else:
                # Single sheet or CSV
                raw_data = self.current_results.get("raw_results", [])

            if raw_data:
                headers = list(raw_data[0].keys())
                self.table_tree["columns"] = headers

                # Configure the row number column
                self.table_tree.column("#0", width=40, anchor="center")
                self.table_tree.heading("#0", text="#")

                for col in headers:
                    self.table_tree.heading(col, text=col)
                    self.table_tree.column(col, width=100, anchor="w") # Set default width and alignment

                for i, row_data in enumerate(raw_data):
                    values = [row_data[col] for col in headers]
                    self.table_tree.insert("", tk.END, values=values, text=str(i + 1)) # Add row number
            else:
                # Display a message if no data
                self.table_tree["columns"] = ["Info"]
                self.table_tree.heading("Info", text="Info")
                self.table_tree.insert("", tk.END, values=["No table data to display."])
    
    def _on_table_double_click(self, event):
        """Handles double-clicks on both cells and headers for editing."""
        region = self.table_tree.identify_region(event.x, event.y)
        if region == "cell":
            self._edit_cell_value(event)
        elif region == "heading":
            self._edit_header_value(event)

    def _edit_cell_value(self, event):
        region = self.table_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.table_tree.identify_column(event.x)
            row = self.table_tree.identify_row(event.y)
            
            # Convert column identifier to index (e.g., #0 for first column, #1 for first data column)
            # We need to adjust for the hidden #0 column if it exists in the Treeview's internal structure
            col_index = int(column[1:]) - 1 # Remove '#' and convert to 0-indexed for display columns
            
            # Get the actual column index in the values tuple, considering the hidden #0 for row numbers
            if self.table_tree["displaycolumns"] == "#all":
                # If all columns are displayed, the actual data column index is col_index - 1
                # because #0 (row numbers) is at index 0
                actual_data_col_index = col_index - 1
            else:
                # If displaycolumns are specified, #0 might not be included in them,
                # so the col_index might directly correspond to the data column
                # This needs careful handling if displaycolumns is used, but for now assuming #all
                actual_data_col_index = col_index - 1 # Adjust for the hidden #0 column

            if row and column and actual_data_col_index >= 0: # Ensure a valid data column was clicked
                x, y, width, height = self.table_tree.bbox(row, column)
                
                # Get current cell value
                current_values = self.table_tree.item(row, 'values')
                current_value = current_values[actual_data_col_index] if actual_data_col_index < len(current_values) else ""
                
                entry_editor = ttk.Entry(self.table_tree, text=current_value)
                entry_editor.place(x=x, y=y, width=width, height=height)
                entry_editor.insert(0, current_value)
                entry_editor.focus()
                
                def on_edit_complete(event):
                    new_value = entry_editor.get()
                    current_values_list = list(self.table_tree.item(row, 'values'))
                    
                    # Ensure the list is long enough for the actual_data_col_index
                    while len(current_values_list) <= actual_data_col_index:
                        current_values_list.append("")
                        
                    current_values_list[actual_data_col_index] = new_value
                    self.table_tree.item(row, values=current_values_list)
                    entry_editor.destroy()
                    self.table_tree.focus_set() # Return focus to treeview

                entry_editor.bind("<Return>", on_edit_complete) # Save on Enter
                entry_editor.bind("<FocusOut>", on_edit_complete) # Save on losing focus

    def _edit_header_value(self, event):
        """Allows editing of column headers."""
        column_id = self.table_tree.identify_column(event.x)
        
        # Check if it's the hidden row number column, which should not be renamed
        if column_id == "#0":
            return

        # Get the current header name
        current_header = self.table_tree.heading(column_id, "text")

        x, y, width, height = self.table_tree.bbox(self.table_tree.get_children()[0], column_id)
        # Position the entry editor over the header
        entry_editor = ttk.Entry(self.table_tree, text=current_header)
        entry_editor.place(x=x, y=y, width=width, height=height)
        entry_editor.insert(0, current_header)
        entry_editor.focus()

        def on_edit_complete(event):
            new_header = entry_editor.get().strip()
            if new_header and new_header != current_header:
                self.table_tree.heading(column_id, text=new_header)
            entry_editor.destroy()
            self.table_tree.focus_set()

        entry_editor.bind("<Return>", on_edit_complete)
        entry_editor.bind("<FocusOut>", on_edit_complete)

    def add_column(self):
        """Adds a new column to the table editor"""
        new_column_name = tk.simpledialog.askstring("Add Column", "Enter new column name:")
        if new_column_name:
            current_columns = list(self.table_tree["columns"])
            if new_column_name not in current_columns:
                current_columns.append(new_column_name)
                self.table_tree["columns"] = current_columns
                self.table_tree.heading(new_column_name, text=new_column_name)
                self.table_tree.column(new_column_name, width=100, anchor="w")
                
                # Add empty value for the new column in existing rows
                for item_id in self.table_tree.get_children():
                    current_values = list(self.table_tree.item(item_id, 'values'))
                    current_values.append("") # Add an empty string for the new column
                    self.table_tree.item(item_id, values=current_values)
            else:
                messagebox.showwarning("Duplicate Column", "Column with this name already exists.")

    def add_row_manual(self):
        """Adds a new empty row to the table editor and re-numbers rows."""
        current_columns = self.table_tree["columns"]
        # Exclude the row number column from the empty_values count if it's explicitly managed by Treeview
        # Here, it's handled by the text attribute, so we just need values for the data columns
        empty_values = ["" for _ in current_columns] 
        self.table_tree.insert("", tk.END, values=empty_values)
        self._re_number_rows() # Re-number all rows after adding a new one

    def export_table(self):
        """Exports the current table data to Excel or CSV"""
        if not self.table_tree.get_children():
            messagebox.showwarning("No Data", "No table data to export.")
            return

        filename = filedialog.asksaveasfilename(
            title="Export Table",
            defaultextension=".xlsx",
            filetypes=[
                ("Excel files", "*.xlsx"),
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            ]
        )

        if filename:
            try:
                # Get headers (excluding the #0 row number column if it's part of columns)
                headers = [self.table_tree.heading(col, "text") for col in self.table_tree["columns"]]
                
                # Get data (excluding the #0 text value, only the values)
                data = []
                for item_id in self.table_tree.get_children():
                    data.append(self.table_tree.item(item_id, 'values'))
                
                # Create DataFrame and export
                df = pd.DataFrame(data, columns=headers)
                
                ext = os.path.splitext(filename)[1].lower()
                if ext == '.csv':
                    df.to_csv(filename, index=False)
                else:
                    df.to_excel(filename, index=False, engine='openpyxl')
                
                messagebox.showinfo("Export Successful", f"Table exported successfully to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export table: {str(e)}")

    def _re_number_rows(self):
        """Re-numbers the rows in the Treeview after an addition or deletion."""
        for i, item_id in enumerate(self.table_tree.get_children()):
            self.table_tree.item(item_id, text=str(i + 1)) # Update the #0 column

    def add_column_with_gemini(self):
        """Adds new columns to the table based on Gemini AI suggestion"""
        if not self.table_tree.get_children():
            messagebox.showwarning("No Data", "Load an Excel/CSV file first to add columns with AI.")
            return

        prompt_text = tk.simpledialog.askstring(
            "Add Column with AI", 
            "Enter instructions for Gemini to add a column (e.g., 'Add a 'Status' column based on quantity'):"
        )
        if not prompt_text:
            return

        current_table_csv = self._get_treeview_data_as_csv()
        gemini_prompt = f"Given the following CSV table data:\n{current_table_csv}\n\n{prompt_text}. Provide the ENTIRE updated CSV table, including the new column and values for all rows. DO NOT include any introductory or concluding text, just the CSV data. Ensure values match the new column type."

        self.progress_var.set("Asking Gemini to add column...")
        self.root.update_idletasks()
        gemini_response = call_gemini_api(gemini_prompt, "")
        self.progress_var.set("Processing AI response...")

        try:
            response_reader = csv.reader(io.StringIO(gemini_response))
            response_rows = list(response_reader)

            if not response_rows:
                raise ValueError("Gemini returned empty or unparseable CSV data.")

            new_headers = response_rows[0]
            new_data_rows = response_rows[1:]

            # Update Treeview with new data
            self.table_tree.delete(*self.table_tree.get_children()) # Clear existing data
            self.table_tree["columns"] = new_headers

            # Configure the row number column and new data columns
            self.table_tree.column("#0", width=40, anchor="center")
            self.table_tree.heading("#0", text="#")

            for col in new_headers:
                self.table_tree.heading(col, text=col)
                self.table_tree.column(col, width=100, anchor="w")
            
            for i, row_data in enumerate(new_data_rows):
                self.table_tree.insert("", tk.END, values=row_data, text=str(i + 1))

            messagebox.showinfo("AI Column Added", "Gemini successfully added and populated the new column!")
        except Exception as e:
            messagebox.showerror("AI Column Error", f"Failed to add column with AI: {str(e)}\nGemini response: {gemini_response[:200]}...")
        finally:
            self.progress_var.set("Ready")

    def add_row_with_gemini(self):
        """Adds new rows to the table based on Gemini AI suggestion"""
        if not self.table_tree["columns"]:
            messagebox.showwarning("No Data", "Load an Excel/CSV file first to add rows with AI.")
            return

        prompt_text = tk.simpledialog.askstring(
            "Add Row with AI", 
            "Enter instructions for Gemini to add rows (e.g., 'Add 3 new entries for books'):"
        )
        if not prompt_text:
            return

        current_table_csv = self._get_treeview_data_as_csv()
        gemini_prompt = f"Given the following CSV table data:\n{current_table_csv}\n\n{prompt_text}. Provide ONLY the new rows in CSV format, without headers. Ensure values match existing column types. DO NOT include any introductory or concluding text."

        self.progress_var.set("Asking Gemini to add rows...")
        self.root.update_idletasks()
        gemini_response = call_gemini_api(gemini_prompt, "")
        self.progress_var.set("Processing AI response...")

        try:
            response_reader = csv.reader(io.StringIO(gemini_response))
            new_rows_data = list(response_reader)

            if not new_rows_data:
                raise ValueError("Gemini returned empty or unparseable CSV data.")
            
            num_current_cols = len(self.table_tree["columns"])

            for row_values in new_rows_data:
                if len(row_values) == num_current_cols:
                    self.table_tree.insert("", tk.END, values=row_values)
                else:
                    messagebox.showwarning("Row Skipped", f"Skipped a row from AI response due to column mismatch: {row_values}")

            self._re_number_rows() # Re-number all rows after adding new ones
            messagebox.showinfo("AI Rows Added", "Gemini successfully added new rows!")
        except Exception as e:
            messagebox.showerror("AI Row Error", f"Failed to add rows with AI: {str(e)}\nGemini response: {gemini_response[:200]}...")
        finally:
            self.progress_var.set("Ready")

    def _get_treeview_data_as_csv(self) -> str:
        """Extracts data from the Treeview and returns it as a CSV string."""
        # Get headers, excluding the row number column if it's explicitly a column
        headers = [self.table_tree.heading(col, "text") for col in self.table_tree["columns"]]
        if not headers:
            return ""

        data = []
        for item_id in self.table_tree.get_children():
            data.append(self.table_tree.item(item_id, 'values')) # Gets only the values, not the #0 text

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(data)
        return output.getvalue()

    def rename_columns_with_gemini(self):
        """Renames columns based on Gemini AI suggestion."""
        if not self.table_tree.get_children():
            messagebox.showwarning("No Data", "Load an Excel/CSV file first to rename columns with AI.")
            return

        current_headers = [self.table_tree.heading(col, "text") for col in self.table_tree["columns"]]
        current_headers_str = ", ".join(current_headers)

        prompt_text = tk.simpledialog.askstring(
            "Rename Columns with AI",
            f"Current columns: {current_headers_str}\n\nEnter instructions for Gemini to rename columns (e.g., 'Rename \"Quantity\" to \"Amount\", \"Price\" to \"Unit Cost\"'):"
        )
        if not prompt_text:
            return

        gemini_prompt = f"Given the following current column names: {current_headers_str}. {prompt_text}. Provide ONLY the new column names as a comma-separated list. DO NOT include any introductory or concluding text."

        self.progress_var.set("Asking Gemini to rename columns...")
        self.root.update_idletasks()
        gemini_response = call_gemini_api(gemini_prompt, "")
        self.progress_var.set("Processing AI response...")

        try:
            new_headers_list = [h.strip() for h in gemini_response.split(',')]
            
            if not new_headers_list or len(new_headers_list) != len(current_headers):
                raise ValueError("Gemini returned an invalid number of new column names.")

            # Apply new headers
            for i, col_id in enumerate(self.table_tree["columns"]):
                self.table_tree.heading(col_id, text=new_headers_list[i])

            messagebox.showinfo("AI Column Renamed", "Gemini successfully renamed columns!")

        except Exception as e:
            messagebox.showerror("AI Column Rename Error", f"Failed to rename columns with AI: {str(e)}\nGemini response: {gemini_response[:200]}...")
        finally:
            self.progress_var.set("Ready")

    def explain_table_with_gemini(self):
        """Explain table data with Gemini AI"""
        if not self.table_tree.get_children():
            messagebox.showwarning("No Data", "No table data to explain.")
            return

        current_table_csv = self._get_treeview_data_as_csv()
        if not current_table_csv:
            messagebox.showwarning("No Data", "Table is empty, nothing to explain.")
            return

        gemini_prompt = f"Explain the following CSV table data:\n{current_table_csv}\n\nProvide a detailed explanation of the data structure, any patterns, and any insights you can derive from it. Keep the explanation concise and to the point."

        self.progress_var.set("Asking Gemini to explain table...")
        self.root.update_idletasks()
        self.progress_bar.start() # Start progress bar

        try:
            response = call_gemini_api(gemini_prompt, "")
            self.explain_text.delete("1.0", tk.END)
            self.explain_text.insert("1.0", response)
            self.explain_text.see("1.0")
            self.progress_var.set("Explanation complete.")
            self.table_ai_notebook.select(self.table_explain_frame) # Switch to explanation tab
        except Exception as e:
            messagebox.showerror("Gemini API Error", f"Failed to explain table: {str(e)}")
            self.progress_var.set("Explanation failed.")
        finally:
            self.progress_bar.stop()

    def suggest_table_actions_with_gemini(self):
        """Suggest actions for table data with Gemini AI"""
        if not self.table_tree.get_children():
            messagebox.showwarning("No Data", "No table data to suggest actions for.")
            return

        current_table_csv = self._get_treeview_data_as_csv()
        if not current_table_csv:
            messagebox.showwarning("No Data", "Table is empty, no suggestions can be made.")
            return

        gemini_prompt = f"Given the following CSV table data:\n{current_table_csv}\n\nProvide concise suggestions for actions or analyses that can be performed on this data, such as data cleaning, visualization ideas, or potential insights. List them as bullet points."

        self.progress_var.set("Asking Gemini for suggestions...")
        self.root.update_idletasks()
        self.progress_bar.start() # Start progress bar

        try:
            response = call_gemini_api(gemini_prompt, "")
            self.suggestions_text.delete("1.0", tk.END)
            self.suggestions_text.insert("1.0", response)
            self.suggestions_text.see("1.0")
            self.progress_var.set("Suggestions received.")
            self.table_ai_notebook.select(self.table_suggest_frame) # Switch to suggestions tab
        except Exception as e:
            messagebox.showerror("Gemini API Error", f"Failed to get suggestions: {str(e)}")
            self.progress_var.set("Suggestions failed.")
        finally:
            self.progress_bar.stop()

    def show_table_editor_help(self):
        """Show help for the table editor"""
        help_content = """
TABLE EDITOR HELP
=================

This tab allows you to view, edit, and manipulate table data loaded from Excel or CSV files.

MANUAL FEATURES:
- Double-click a cell to edit its value.
- Double-click a column header to rename the column.
- '➕ Add Column': Adds a new empty column to the right.
- '➕ Add Row': Adds a new empty row to the bottom.
- '💾 Export Table': Exports the current table data to a new Excel (.xlsx) or CSV (.csv) file.

AI-POWERED FEATURES (powered by Gemini):
- '➕ Add Row (AI)': Prompts AI to add new rows based on your instructions and existing data patterns.
- '➕ Add Column (AI)': Prompts AI to add new columns and populate them based on your instructions and existing data.
- '📝 Rename Columns (AI)': Asks AI to suggest and apply more appropriate column names based on the table content.
- '❓ Explain Table (AI)': Asks AI to explain the data structure, patterns, and insights from the current table.
- '💡 Suggestions (AI)': Requests AI to provide suggestions for data analysis, visualization, or transformation based on the table data.

HOW IT WORKS:
- When an Excel/CSV file is loaded, its data is displayed in the 'Table Data' sub-tab.
- The first column (#) automatically shows row numbers for easy reference.
- All changes made in the table editor are temporary until exported.
        """
        messagebox.showinfo("Table Editor Help", help_content)

    def generate_table_instructions_with_gemini(self):
        """Generate table instructions with Gemini AI"""
        if not self.table_tree.get_children():
            messagebox.showwarning("No Data", "No table data to generate instructions for.")
            return

        current_table_csv = self._get_treeview_data_as_csv()
        if not current_table_csv:
            messagebox.showwarning("No Data", "Table is empty, no instructions can be generated.")
            return

        user_command = tk.simpledialog.askstring(
            "Table Command (AI)",
            "Enter your table manipulation command (e.g., 'Add 100 random rows', 'Delete rows where \"Status\" is \"Complete\"', 'Calculate sum of \"Quantity\" column'):"
        )
        if not user_command:
            return

        gemini_prompt = f"""
Given the following CSV table data:
{current_table_csv}

User command: {user_command}

Based on the user's command, provide a JSON object representing the action to be performed on the table.
The JSON object should have an "action" key, and other keys specific to the action.

Supported actions:
1.  "add_rows": {{"action": "add_rows", "count": int, "data_type": "empty" | "random"}}
    (e.g., for "Add 100 random rows": {{"action": "add_rows", "count": 100, "data_type": "random"}})
    (e.g., for "Add 5 empty rows": {{"action": "add_rows", "count": 5, "data_type": "empty"}})
2.  "delete_rows": {{"action": "delete_rows", "criteria": {{"column": str, "value": str}} | {{"first_n": int}} | {{"last_n": int}}}}
    (e.g., for "Delete rows where 'Status' is 'Complete'": {{"action": "delete_rows", "criteria": {{"column": "Status", "value": "Complete"}}}})
    (e.g., for "Delete first 10 rows": {{"action": "delete_rows", "criteria": {{"first_n": 10}}}})
    (e.g., for "Delete last 20 rows": {{"action": "delete_rows", "criteria": {{"last_n": 20}}}})
3.  "modify_cell": {{"action": "modify_cell", "row_index": int, "column_name": str, "new_value": str}}
    (e.g., for "Change cell at row 2, column 'Price' to 15.00": {{"action": "modify_cell", "row_index": 1, "column_name": "Price", "new_value": "15.00"}})
    (Note: row_index is 0-based for internal processing)
4.  "add_column": {{"action": "add_column", "name": str, "type": "empty" | "calculated", "formula": str (optional)}}
    (e.g., for "Add a new column 'Total' calculated as 'Quantity' * 'Price'": {{"action": "add_column", "name": "Total", "type": "calculated", "formula": "df['Quantity'] * df['Price']"}})
    (e.g., for "Add an empty column 'Notes'": {{"action": "add_column", "name": "Notes", "type": "empty"}})

If the command cannot be represented in the above JSON format, or if it's too complex for direct implementation, provide a JSON object:
{{"action": "manual_instructions", "instructions": "string_with_detailed_manual_steps"}}

Output only the JSON object. Do not include any other text or formatting outside the JSON.
"""

        self.progress_var.set(f"Executing table command ({user_command})...")
        self.root.update_idletasks()
        self.progress_bar.start() # Start progress bar

        try:
            response_text = call_gemini_api(gemini_prompt, "")
            self.progress_var.set("Processing AI response...")
            self.root.update_idletasks()

            try:
                # Attempt to parse as JSON
                # Look for JSON code block in the response
                json_match = re.search(r'```json\n(.*?)```', response_text, re.DOTALL)
                if json_match:
                    json_string = json_match.group(1).strip()
                    ai_command = json.loads(json_string)
                    self._execute_ai_table_command(ai_command) # Call the new executor
                    self.progress_var.set("Table command executed.")
                else:
                    # No JSON code block found, treat as manual instructions
                    raise json.JSONDecodeError("No JSON code block found in AI response", response_text, 0)
            except json.JSONDecodeError:
                # Not a valid JSON, treat as manual instructions
                self._save_text_state()
                self.basic_results_text.delete("1.0", tk.END)
                self.basic_results_text.insert("1.0", "AI could not parse command as structured data. Here are manual instructions:\n\n" + response_text)
                self.basic_results_text.see("1.0")
                self.progress_var.set("Manual instructions provided.")
            except Exception as ex:
                # Handle errors during command execution
                messagebox.showerror("Table Command Error", f"Failed to execute AI command: {str(ex)}")
                self._save_text_state()
                self.basic_results_text.delete("1.0", tk.END)
                self.basic_results_text.insert("1.0", f"Error executing command: {str(ex)}\n\nOriginal AI response:\n" + response_text)
                self.basic_results_text.see("1.0")
                self.progress_var.set("Command execution failed.")

        except Exception as e:
            messagebox.showerror("Gemini API Error", f"Failed to generate table command: {str(e)}")
            self.progress_var.set("Command generation failed.")
        finally:
            self.progress_bar.stop()
            self._update_undo_button_state()

    def _execute_ai_table_command(self, command: dict):
        """Executes a structured AI command on the table data."""
        action = command.get("action")

        if action == "add_rows":
            count = command.get("count", 1)
            data_type = command.get("data_type", "empty")
            if data_type == "empty":
                for _ in range(count):
                    self.add_row_manual()
            elif data_type == "random":
                headers = [self.table_tree.heading(col, "text") for col in self.table_tree["columns"]]
                if not headers:
                    messagebox.showwarning("No Columns", "Cannot add random rows: no columns exist in the table.")
                    return

                # Get existing data to infer types for better random data generation
                existing_data = []
                for item_id in self.table_tree.get_children():
                    existing_data.append(self.table_tree.item(item_id, 'values'))

                column_metadata = {}
                # Infer types and ranges/unique values based on existing data
                if existing_data:
                    for col_idx, col_name in enumerate(headers):
                        sample_values = [row[col_idx] for row in existing_data if len(row) > col_idx and row[col_idx] is not None and str(row[col_idx]).strip() != '']
                        
                        inferred_type = str # Default to string
                        numeric_values = []
                        string_values = set()

                        for val in sample_values:
                            try:
                                # Try converting to float first, then int
                                float_val = float(val)
                                numeric_values.append(float_val)
                                if '.' not in str(val):
                                    inferred_type = int # Prefer int if no decimal
                                else:
                                    inferred_type = float
                            except ValueError:
                                string_values.add(str(val))
                        
                        if numeric_values:
                            col_min = min(numeric_values)
                            col_max = max(numeric_values)
                            column_metadata[col_name] = {"type": inferred_type, "min": col_min, "max": col_max}
                        elif string_values:
                            column_metadata[col_name] = {"type": str, "unique_values": list(string_values)}
                        else:
                            column_metadata[col_name] = {"type": str} # Fallback to generic string
                else:
                    # If no existing data, default all columns to generic string type for random generation
                    for col_name in headers:
                        column_metadata[col_name] = {"type": str}

                import random
                for _ in range(count):
                    new_row_values = []
                    for col_name in headers:
                        col_meta = column_metadata.get(col_name, {"type": str})
                        generated_value = ""

                        if col_meta["type"] == int:
                            val_min = int(col_meta.get("min", 1))
                            val_max = int(col_meta.get("max", 100))
                            generated_value = random.randint(val_min, val_max)
                        elif col_meta["type"] == float:
                            val_min = col_meta.get("min", 1.0)
                            val_max = col_meta.get("max", 100.0)
                            generated_value = round(random.uniform(val_min, val_max), 2)
                        elif col_meta["type"] == str:
                            unique_vals = col_meta.get("unique_values")
                            if unique_vals:
                                generated_value = random.choice(unique_vals)
                            else:
                                # Fallback for string if no unique values found
                                generated_value = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789 ', k=random.randint(5, 15))).strip()
                        else:
                            generated_value = "" # Fallback
                        new_row_values.append(generated_value)
                    self.table_tree.insert("", tk.END, values=new_row_values)
                messagebox.showinfo("Random Rows Added", f"Successfully added {count} random rows related to existing data.")

            self._re_number_rows() # Re-number after adding rows
        elif action == "delete_rows":
            criteria = command.get("criteria", {})
            if "first_n" in criteria:
                num_to_delete = criteria["first_n"]
                items_to_delete = self.table_tree.get_children()[:num_to_delete]
                if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete the first {len(items_to_delete)} rows?"):
                    for item_id in items_to_delete:
                        self.table_tree.delete(item_id)
                    self._re_number_rows()
            elif "last_n" in criteria:
                num_to_delete = criteria["last_n"]
                all_items = self.table_tree.get_children()
                items_to_delete = all_items[len(all_items) - num_to_delete:]
                if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete the last {len(items_to_delete)} rows?"):
                    for item_id in items_to_delete:
                        self.table_tree.delete(item_id)
                    self._re_number_rows()
            elif "column" in criteria and "value" in criteria:
                column_name = criteria["column"]
                target_value = str(criteria["value"]) # Convert to string for comparison
                
                headers = [self.table_tree.heading(col, "text") for col in self.table_tree["columns"]]
                try:
                    col_index = headers.index(column_name)
                except ValueError:
                    messagebox.showwarning("Error", f"Column '{column_name}' not found for deletion criteria.")
                    return

                items_to_delete = []
                for item_id in self.table_tree.get_children():
                    values = self.table_tree.item(item_id, 'values')
                    if col_index < len(values) and str(values[col_index]) == target_value:
                        items_to_delete.append(item_id)
                
                if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete {len(items_to_delete)} rows where '{column_name}' is '{target_value}'?"):
                    for item_id in items_to_delete:
                        self.table_tree.delete(item_id)
                    self._re_number_rows()
            else:
                messagebox.showwarning("Unknown Command", "Unsupported delete_rows criteria. AI response for manual instructions may be in Extracted Text area.")
        elif action == "modify_cell":
            row_index = command.get("row_index")
            column_name = command.get("column_name")
            new_value = command.get("new_value")

            if row_index is None or column_name is None or new_value is None:
                messagebox.showwarning("Error", "Missing parameters for modify_cell command. AI response for manual instructions may be in Extracted Text area.")
                return

            all_items = self.table_tree.get_children()
            if not (0 <= row_index < len(all_items)):
                messagebox.showwarning("Error", f"Row index {row_index} out of bounds. AI response for manual instructions may be in Extracted Text area.")
                return

            item_id = all_items[row_index]
            headers = [self.table_tree.heading(col, "text") for col in self.table_tree["columns"]]
            try:
                col_index = headers.index(column_name)
            except ValueError:
                messagebox.showwarning("Error", f"Column '{column_name}' not found for modification. AI response for manual instructions may be in Extracted Text area.")
                return

            current_values = list(self.table_tree.item(item_id, 'values'))
            # Ensure the list is long enough for the target col_index, if not, pad with empty strings
            while len(current_values) <= col_index:
                current_values.append("")
            
            current_values[col_index] = new_value
            self.table_tree.item(item_id, values=current_values)
            self._re_number_rows() # Re-number in case of any implicit changes (though not direct deletion/addition)
        elif action == "add_column":
            column_name = command.get("name")
            column_type = command.get("type")
            column_formula = command.get("formula")

            if not column_name:
                messagebox.showwarning("Error", "Missing column name for add_column command. AI response for manual instructions may be in Extracted Text area.")
                return

            current_headers = [self.table_tree.heading(col, "text") for col in self.table_tree["columns"]]
            if column_name in current_headers:
                messagebox.showwarning("Duplicate Column", f"Column '{column_name}' already exists. AI response for manual instructions may be in Extracted Text area.")
                return

            # Add the new column to the Treeview headers
            new_columns_list = list(self.table_tree["columns"]) + [column_name]
            self.table_tree["columns"] = new_columns_list
            self.table_tree.heading(column_name, text=column_name)
            self.table_tree.column(column_name, width=100, anchor="w")

            # Add empty values for the new column in existing rows
            for item_id in self.table_tree.get_children():
                current_values = list(self.table_tree.item(item_id, 'values'))
                current_values.append("")  # Add an empty string for the new column
                self.table_tree.item(item_id, values=current_values)

            if column_type == "calculated" and column_formula:
                messagebox.showinfo("Not Implemented", f"Column '{column_name}' added as empty. AI cannot directly apply complex calculated formulas yet. Please use Python code if provided by AI in the Extracted Text area, or calculate manually.")
                # For now, it just adds an empty column. Further logic needed to execute formula.
            elif column_type == "empty":
                messagebox.showinfo("Column Added", f"Empty column '{column_name}' added.")
            self._re_number_rows() # Re-number after adding column if any hidden rows or order changes

        elif action == "manual_instructions":
            instructions = command.get("instructions", "No instructions provided.")
            self._save_text_state()
            self.basic_results_text.delete("1.0", tk.END)
            self.basic_results_text.insert("1.0", f"AI provides manual instructions:\n\n{instructions}")
            self.basic_results_text.see("1.0")
        else:
            messagebox.showwarning("Unknown Command", f"AI generated an unknown action: {action}. Displaying raw response in Extracted Text area.")
            self._save_text_state()
            self.basic_results_text.delete("1.0", tk.END)
            self.basic_results_text.insert("1.0", f"AI response could not be interpreted:\n\n{json.dumps(command, indent=2)}")
            self.basic_results_text.see("1.0")

def create_desktop_shortcut():
    """Create a desktop shortcut for the application"""
    try:
        import winshell
        from win32com.client import Dispatch
        
        desktop = winshell.desktop()
        path = os.path.join(desktop, "Enhanced OCR Processor.lnk")
        target = sys.executable
        wDir = os.path.dirname(os.path.abspath(__file__))
        icon = target
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(path)
        shortcut.Targetpath = target
        shortcut.Arguments = f'"{__file__}" --gui'
        shortcut.WorkingDirectory = wDir
        shortcut.IconLocation = icon
        shortcut.save()
        
        print(f"Desktop shortcut created: {path}")
        
    except ImportError:
        print("Desktop shortcut creation requires pywin32 package")
        print("Install with: pip install pywin32")
    except Exception as e:
        print(f"Failed to create desktop shortcut: {str(e)}")

def test_enhanced_ocr():
    """Test the enhanced OCR processor with command line interface"""
    # Initialize OCR processor
    ocr = EnhancedOCRProcessor(languages=['en', 'ar'])
    
    # Test with an image file
    image_path = input("Enter path to an image file (or press Enter to skip): ")
    if image_path:
        image_results = ocr.process_image(image_path, enable_smart_processing=True)
        print("\n--- Image OCR Results ---")
        print(f"Processing time: {image_results.get('processing_time', 0):.2f} seconds")
        print("\nExtracted Text:")
        print(image_results.get('text', 'No text extracted'))
        
        if 'smart_processing' in image_results:
            print("\nSmart Processing Results:")
            print(json.dumps(image_results['smart_processing'], indent=2))
    
    # Test with a PDF file
    pdf_path = input("\nEnter path to a PDF file (or press Enter to skip): ")
    if pdf_path:
        pdf_results = ocr.process_pdf(pdf_path, enable_smart_processing=True)
        print("\n--- PDF OCR Results ---")
        print(f"Total pages: {pdf_results.get('total_pages', 0)}")
        print(f"Processing time: {pdf_results.get('processing_time', 0):.2f} seconds")
        
        if 'pages' in pdf_results:
            for page in pdf_results['pages']:
                print(f"\n--- Page {page['page_num']} ---")
                print(page['text'])
                if 'smart_processing' in page:
                    print("\nSmart Processing Results:")
                    print(json.dumps(page['smart_processing'], indent=2))

def main():
    """Main application entry point"""
    import sys
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--cli":
            # Launch command line interface
            test_enhanced_ocr()
            return
        elif sys.argv[1] == "--config":
            # Create sample configuration
            create_sample_config()
            return
        elif sys.argv[1] == "--shortcut":
            # Create desktop shortcut
            create_desktop_shortcut()
            return
        elif sys.argv[1] == "--help":
            print("Enhanced OCR Processor")
            print("Usage:")
            print("  python ocr_processor_gui.py [--gui]     # Launch GUI (default)")
            print("  python ocr_processor_gui.py --cli       # Launch CLI")
            print("  python ocr_processor_gui.py --config    # Create sample config")
            print("  python ocr_processor_gui.py --shortcut  # Create desktop shortcut")
            print("  python ocr_processor_gui.py --help      # Show this help")
            return
    
    # Launch GUI application (default)
    try:
        root = tk.Tk()
        
        # Set application icon if available
        try:
            # Try to set a custom icon
            root.iconbitmap(default="icon.ico")
        except:
            pass  # Icon file not found, use default
        
        # Create and run the application
        app = EnhancedOCRApp(root)
        
        # Handle window closing
        def on_closing():
            if messagebox.askokcancel("Quit", "Do you want to quit the Enhanced OCR Processor?"):
                root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Center window on screen
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")
        
        # Start the GUI event loop
        root.mainloop()
        
    except Exception as e:
        print(f"Failed to start GUI application: {str(e)}")
        print("Falling back to command line interface...")
        test_enhanced_ocr()

if __name__ == "__main__":
    main()

