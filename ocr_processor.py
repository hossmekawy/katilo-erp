import os
import easyocr
import cv2
import numpy as np
import fitz  # PyMuPDF
from PIL import Image
import tempfile
import time

class OCRProcessor:
    def __init__(self, languages=['en', 'ar']):
        """
        Initialize the OCR processor with specified languages.
        
        Args:
            languages (list): List of language codes. Default: English and Arabic
        """
        print(f"Initializing EasyOCR with languages: {languages}")
        self.reader = easyocr.Reader(languages, gpu=False)
        self.languages = languages
        
    def process_image(self, image_path):
        """
        Process a single image file with OCR.
        
        Args:
            image_path (str): Path to the image file
            
        Returns:
            dict: Dictionary containing OCR results and metadata
        """
        start_time = time.time()
        print(f"Processing image: {image_path}")
        
        # Read the image
        image = cv2.imread(image_path)
        if image is None:
            return {"error": f"Could not read image file: {image_path}"}
        
        # Perform OCR
        results = self.reader.readtext(image)
        
        # Format results
        extracted_text = self._format_results(results)
        
        processing_time = time.time() - start_time
        return {
            "text": extracted_text,
            "raw_results": results,
            "processing_time": processing_time,
            "source_type": "image",
            "source_path": image_path
        }
    
    def process_pdf(self, pdf_path):
        """
        Process a PDF file with OCR, extracting text from each page.
        
        Args:
            pdf_path (str): Path to the PDF file
            
        Returns:
            dict: Dictionary containing OCR results and metadata for each page
        """
        start_time = time.time()
        print(f"Processing PDF: {pdf_path}")
        
        try:
            # Open the PDF
            pdf_document = fitz.open(pdf_path)
            page_results = []
            
            # Process each page
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                
                # Convert page to image
                pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
                
                # Create a temporary file for the page image
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # Save the image
                pix.save(temp_path)
                
                # Process the image
                image = cv2.imread(temp_path)
                results = self.reader.readtext(image)
                
                # Format results
                extracted_text = self._format_results(results)
                
                page_results.append({
                    "page_num": page_num + 1,
                    "text": extracted_text,
                    "raw_results": results
                })
                
                # Clean up temporary file
                os.unlink(temp_path)
            
            processing_time = time.time() - start_time
            return {
                "pages": page_results,
                "total_pages": len(pdf_document),
                "processing_time": processing_time,
                "source_type": "pdf",
                "source_path": pdf_path
            }
            
        except Exception as e:
            return {"error": f"Error processing PDF: {str(e)}"}
    
    def _format_results(self, results):
        """
        Format the raw OCR results into readable text.
        
        Args:
            results (list): List of OCR result tuples from EasyOCR
            
        Returns:
            str: Formatted text
        """
        text_blocks = []
        for (bbox, text, prob) in results:
            text_blocks.append(text)
        
        return "\n".join(text_blocks)

# Test function
def test_ocr():
    # Initialize OCR processor
    ocr = OCRProcessor(languages=['en', 'ar'])
    
    # Test with an image file
    image_path = input("Enter path to an image file (or press Enter to skip): ")
    if image_path:
        image_results = ocr.process_image(image_path)
        print("\n--- Image OCR Results ---")
        print(f"Processing time: {image_results.get('processing_time', 0):.2f} seconds")
        print("\nExtracted Text:")
        print(image_results.get('text', 'No text extracted'))
    
    # Test with a PDF file
    pdf_path = input("\nEnter path to a PDF file (or press Enter to skip): ")
    if pdf_path:
        pdf_results = ocr.process_pdf(pdf_path)
        print("\n--- PDF OCR Results ---")
        print(f"Total pages: {pdf_results.get('total_pages', 0)}")
        print(f"Processing time: {pdf_results.get('processing_time', 0):.2f} seconds")
        
        if 'pages' in pdf_results:
            for page in pdf_results['pages']:
                print(f"\n--- Page {page['page_num']} ---")
                print(page['text'])

if __name__ == "__main__":
    test_ocr()