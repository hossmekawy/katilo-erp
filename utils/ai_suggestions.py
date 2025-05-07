import threading
import time
import google.generativeai as genai
from models import db, Item, Category, Inventory, AISuggestion
from sqlalchemy import func
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ai_suggestions')

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not found in environment variables.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Gemini API configured successfully")
    except Exception as e:
        logger.error(f"Error configuring Gemini API: {e}")

# Choose the appropriate model
MODEL_NAME = "gemini-2.0-flash"  # Using the latest model for efficiency

# Global variable to track if the suggestion thread is running
suggestion_thread_running = False

def get_gemini_model():
    """Get the Gemini model instance"""
    try:
        return genai.GenerativeModel(MODEL_NAME)
    except Exception as e:
        logger.error(f"Error creating Gemini model: {e}")
        return None

def analyze_item_data(item_id=None, category_id=None, app=None):
    """
    Analyze item data using Gemini AI and generate suggestions

    Args:
        item_id: Optional specific item ID to analyze
        category_id: Optional specific category ID to analyze
        app: Flask application instance (optional)
    """
    try:
        # Import Flask here to avoid circular imports
        from flask import current_app

        # Get the Flask app context
        if app is None:
            app = current_app._get_current_object()

        # Ensure we're running within an application context
        with app.app_context():
            model = get_gemini_model()
            if not model:
                logger.error("Failed to initialize Gemini model")
                return

            # Build query based on parameters
            if item_id:
                items = Item.query.filter_by(id=item_id).all()
            elif category_id:
                items = Item.query.filter_by(category_id=category_id).all()
            else:
                # Limit to 100 items to avoid overwhelming the API
                items = Item.query.limit(100).all()

            if not items:
                logger.info("No items found to analyze")
                return

            # Process items in batches to avoid overwhelming the API
            batch_size = 10
            for i in range(0, len(items), batch_size):
                batch_items = items[i:i+batch_size]
                process_item_batch(model, batch_items)
                time.sleep(2)  # Avoid rate limiting

    except Exception as e:
        logger.error(f"Error in analyze_item_data: {e}")

def process_item_batch(model, items):
    """Process a batch of items with Gemini AI"""
    try:
        # Prepare item data for analysis
        items_data = []
        for item in items:
            # Get inventory data
            inventory_data = db.session.query(
                func.sum(Inventory.quantity).label('total_quantity')
            ).filter(Inventory.item_id == item.id).first()

            total_quantity = inventory_data.total_quantity if inventory_data and inventory_data.total_quantity else 0

            # Get category information
            category = Category.query.get(item.category_id)
            category_name = category.name if category else "Unknown"
            category_type = category.category_type if category else "Unknown"

            items_data.append({
                'id': item.id,
                'name': item.name,
                'sku': item.sku,
                'category_name': category_name,
                'category_type': category_type,
                'reorder_level': item.reorder_level,
                'current_quantity': total_quantity,
                'unit_of_measure': item.unit_of_measure,
                'cost': item.cost,
                'price': item.price
            })

        # Create prompt for Gemini
        prompt = create_analysis_prompt(items_data)

        # Get suggestions from Gemini
        response = model.generate_content(prompt)

        if not response or not response.text:
            logger.warning("Empty response from Gemini")
            return

        # Process and store suggestions
        process_gemini_response(response.text, items_data)

    except Exception as e:
        logger.error(f"Error in process_item_batch: {e}")

def create_analysis_prompt(items_data):
    """Create a prompt for Gemini to analyze item data"""
    prompt = """
    أنت مساعد ذكي متخصص في تحليل بيانات المخزون والمنتجات. قم بتحليل البيانات التالية وتقديم اقتراحات لتحسين إدارة المخزون.

    فيما يلي بيانات العناصر من نظام إدارة المخزون:

    """

    for item in items_data:
        prompt += f"""
        العنصر {item['id']}:
        - الاسم: {item['name']}
        - الرمز التعريفي (SKU): {item['sku']}
        - الفئة: {item['category_name']} (النوع: {item['category_type']})
        - مستوى إعادة الطلب: {item['reorder_level']}
        - الكمية الحالية: {item['current_quantity']}
        - وحدة القياس: {item['unit_of_measure']}
        - التكلفة: {item['cost']}
        - السعر: {item['price']}
        """

    prompt += """
    قم بتحليل البيانات وتقديم اقتراحات محددة في التنسيق التالي:

    SUGGESTION_START
    item_id: [رقم العنصر]
    suggestion_type: [نوع الاقتراح - NameImprovement, CategoryMismatch, ReorderLevelAdjustment, InventoryAnomaly]
    suggestion_text: [نص الاقتراح بالعربية]
    suggested_value: [القيمة المقترحة إن وجدت]
    SUGGESTION_END

    أنواع الاقتراحات:
    1. NameImprovement: اقتراحات لتحسين اسم العنصر
    2. CategoryMismatch: اقتراح بأن العنصر قد يكون في فئة غير مناسبة
    3. ReorderLevelAdjustment: اقتراح لتعديل مستوى إعادة الطلب بناءً على الكمية الحالية
    4. InventoryAnomaly: اكتشاف أي شذوذ في بيانات المخزون (مثل كمية سالبة أو صفرية غير منطقية)

    قدم اقتراحات فقط عندما تكون هناك مشكلة واضحة أو فرصة للتحسين. لا تقدم اقتراحات لكل عنصر إذا لم تكن هناك حاجة.
    """

    return prompt

def process_gemini_response(response_text, items_data):
    """Process Gemini's response and store suggestions in the database"""
    try:
        # Extract suggestions from the response
        suggestions = []
        current_suggestion = None

        for line in response_text.split('\n'):
            line = line.strip()

            if line == "SUGGESTION_START":
                current_suggestion = {}
            elif line == "SUGGESTION_END" and current_suggestion:
                suggestions.append(current_suggestion)
                current_suggestion = None
            elif current_suggestion is not None and ":" in line:
                key, value = line.split(":", 1)
                current_suggestion[key.strip()] = value.strip()

        # Store suggestions in the database
        for suggestion in suggestions:
            try:
                item_id = int(suggestion.get('item_id', 0))
                if not item_id:
                    continue

                # Check if a similar suggestion already exists
                existing_suggestion = AISuggestion.query.filter_by(
                    item_id=item_id,
                    suggestion_type=suggestion.get('suggestion_type'),
                    status='Pending'
                ).first()

                if existing_suggestion:
                    # Update existing suggestion
                    existing_suggestion.suggestion_text = suggestion.get('suggestion_text', '')
                    existing_suggestion.suggested_value = suggestion.get('suggested_value', '')
                    existing_suggestion.updated_at = datetime.now()
                else:
                    # Create new suggestion
                    new_suggestion = AISuggestion(
                        item_id=item_id,
                        suggestion_type=suggestion.get('suggestion_type', ''),
                        suggestion_text=suggestion.get('suggestion_text', ''),
                        suggested_value=suggestion.get('suggested_value', ''),
                        status='Pending'
                    )
                    db.session.add(new_suggestion)

                db.session.commit()
                logger.info(f"Stored suggestion for item {item_id}: {suggestion.get('suggestion_type')}")

            except Exception as e:
                db.session.rollback()
                logger.error(f"Error storing suggestion: {e}")

    except Exception as e:
        logger.error(f"Error processing Gemini response: {e}")

def start_suggestion_thread(app=None):
    """Start a background thread to periodically analyze inventory data"""
    global suggestion_thread_running

    if suggestion_thread_running:
        logger.info("Suggestion thread is already running")
        return

    # Import Flask here to avoid circular imports
    from flask import current_app

    # Get the Flask app context if not provided
    if app is None:
        try:
            app = current_app._get_current_object()
        except Exception as e:
            logger.error(f"Failed to get current app: {e}")
            return None

    def run_periodic_analysis():
        global suggestion_thread_running
        suggestion_thread_running = True
        logger.info("Starting periodic inventory analysis")

        try:
            while suggestion_thread_running:
                try:
                    analyze_item_data(app=app)
                    logger.info("Completed inventory analysis cycle")
                except Exception as e:
                    logger.error(f"Error in analysis cycle: {e}")

                # Sleep for 6 hours before next analysis
                for _ in range(6 * 60 * 60):
                    if not suggestion_thread_running:
                        break
                    time.sleep(1)
        finally:
            suggestion_thread_running = False
            logger.info("Stopped periodic inventory analysis")

    # Start the thread
    thread = threading.Thread(target=run_periodic_analysis, daemon=True)
    thread.start()
    logger.info("Started suggestion thread")
    return thread

def stop_suggestion_thread():
    """Stop the background suggestion thread"""
    global suggestion_thread_running
    suggestion_thread_running = False
    logger.info("Requested to stop suggestion thread")
