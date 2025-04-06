        # --- START OF FILE routes/chatbot_routes.py ---

import os
import io
import base64
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image

# Import necessary models and db from your main models file
# Adjust the import path if your structure is different
try:
    from models import db, Item, Category, Supplier, Warehouse, Inventory, PurchaseOrder, BOM, BOMDetail, WorkerProductivity, ProductionRun, ProductionRunDetail, ProductionProcess
except ImportError:
    # Handle potential import errors if structure differs or running standalone
    print("Warning: Could not import models. Ensure models.py is accessible.")
    db = None
    Item = Category = Supplier = Warehouse = Inventory = PurchaseOrder = BOM = BOMDetail = WorkerProductivity = ProductionRun = ProductionRunDetail = ProductionProcess = None


# Load environment variables (for API key)
load_dotenv()

chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/api/chatbot')

# --- Gemini Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY not found in environment variables.")
    # You might want to raise an error or handle this more gracefully
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")

# Choose the appropriate model - gemini-1.5-flash supports vision and is efficient
# Use gemini-pro if you only need text or encounter issues with flash
MODEL_NAME = "gemini-2.0-flash" # Recommended for multimodal

try:
    # Check if models are available before initializing
    if Item and Supplier and Category and Warehouse and Inventory and PurchaseOrder and BOM and ProductionRun:
         # Initialize the Generative Model - outside the request if possible
         model = genai.GenerativeModel(MODEL_NAME)
    else:
        model = None
        print("Warning: Models not available, chatbot model not initialized.")

except Exception as e:
    print(f"Error initializing Gemini model '{MODEL_NAME}': {e}")
    model = None # Ensure model is None if initialization fails
# --- Helper Functions ---

def fetch_context_data(query):
    """
    Fetches relevant data from the database based on keywords in the query.
    This is a simplified example; you might need more sophisticated keyword matching
    or even use embeddings for better relevance.
    """
    context_parts = []
    query_lower = query.lower()

    if not db or not model: # Check if db or model failed to initialize
        return "لا يمكن الوصول إلى بيانات النظام أو نموذج الذكاء الاصطناعي حاليًا."

    try:
        # --- Simple Keyword Matching ---
        if "منتج" in query_lower or "عنصر" in query_lower or "sku" in query_lower or "صنف" in query_lower:
            items = Item.query.limit(5).all()
            if items:
                context_parts.append("أحدث المنتجات:")
                for item in items:
                    cat_name = item.category.name if item.category else "غير محدد"
                    context_parts.append(f"- {item.name} (SKU: {item.sku}, التصنيف: {cat_name}, السعر: {item.price})")

        if "مورد" in query_lower:
            suppliers = Supplier.query.limit(3).all()
            if suppliers:
                context_parts.append("بعض الموردين:")
                for sup in suppliers:
                    context_parts.append(f"- {sup.supplier_name} (جهة الاتصال: {sup.contact_person or 'غير محدد'})")

        if "مخزون" in query_lower or "كمية" in query_lower or "مستودع" in query_lower:
            inventory = Inventory.query.join(Item).join(Warehouse).limit(5).all()
            if inventory:
                context_parts.append("أحدث بيانات المخزون:")
                for inv in inventory:
                    context_parts.append(f"- {inv.item.name} في {inv.warehouse.name}: الكمية {inv.quantity}")

        if "تصنيف" in query_lower:
            categories = Category.query.limit(5).all()
            if categories:
                context_parts.append("بعض التصنيفات:")
                for cat in categories:
                    context_parts.append(f"- {cat.name}")

        if "طلب شراء" in query_lower or "شراء" in query_lower:
            pos = PurchaseOrder.query.order_by(PurchaseOrder.order_date.desc()).limit(3).all()
            if pos:
                context_parts.append("أحدث طلبات الشراء:")
                for po in pos:
                    sup_name = po.supplier.supplier_name if po.supplier else "غير محدد"
                    context_parts.append(f"- طلب رقم {po.id} للمورد {sup_name} (الحالة: {po.status}, التاريخ: {po.order_date.strftime('%Y-%m-%d')})")

        # --- BOM and BOMDetail Information ---
        if "قائمة مواد" in query_lower or "bom" in query_lower or "مكونات" in query_lower:
            boms = BOM.query.join(Item, BOM.final_product_id == Item.id).limit(3).all()
            if boms:
                context_parts.append("بعض قوائم المواد:")
                for bom in boms:
                    context_parts.append(f"- قائمة مواد للمنتج: {bom.final_product.name} (ID: {bom.id})")
                    # Get details for this BOM
                    details = BOMDetail.query.filter_by(bom_id=bom.id).join(Item, BOMDetail.component_item_id == Item.id).limit(5).all()
                    if details:
                        context_parts.append("  المكونات:")
                        for detail in details:
                            context_parts.append(f"  -- {detail.component_item.name}: الكمية {detail.quantity_required} {detail.unit_of_measure or ''}")

        # --- Production Run Information ---
        if "إنتاج" in query_lower or "تصنيع" in query_lower or "خط الإنتاج" in query_lower:
            runs = ProductionRun.query.order_by(ProductionRun.planned_start_date.desc()).limit(3).all()
            if runs:
                context_parts.append("أحدث عمليات الإنتاج:")
                for run in runs:
                    responsible = run.responsible_user.username if run.responsible_user else "غير محدد"
                    start_date = run.planned_start_date.strftime('%Y-%m-%d') if run.planned_start_date else "غير محدد"
                    context_parts.append(f"- عملية إنتاج رقم {run.id} (الحالة: {run.status}, المسؤول: {responsible}, تاريخ البدء: {start_date})")
                    
                    # Get details for this production run
                    run_details = ProductionRunDetail.query.filter_by(production_run_id=run.id).join(Item).limit(3).all()
                    if run_details:
                        context_parts.append("  المنتجات المخطط إنتاجها:")
                        for detail in run_details:
                            context_parts.append(f"  -- {detail.item.name}: الكمية المخططة {detail.quantity_planned}")

        # --- Production Process Information ---
        if "عملية إنتاج" in query_lower or "مراحل الإنتاج" in query_lower:
            processes = ProductionProcess.query.order_by(ProductionProcess.start_time.desc()).limit(5).all()
            if processes:
                context_parts.append("أحدث عمليات الإنتاج المفصلة:")
                for process in processes:
                    batch_info = f"دفعة رقم {process.batch_id}" if process.batch else "غير محدد"
                    operator = process.operator.username if process.operator else "غير محدد"
                    context_parts.append(f"- عملية {process.process_type} لـ {batch_info} (المشغل: {operator})")
                    if process.temperature:
                        context_parts.append(f"  -- درجة الحرارة: {process.temperature}°C")
                    if process.humidity:
                        context_parts.append(f"  -- الرطوبة: {process.humidity}%")
                    if process.ph_level:
                        context_parts.append(f"  -- مستوى الحموضة: {process.ph_level}")

        # --- Worker Productivity Information ---
        if "إنتاجية" in query_lower or "عمال" in query_lower or "أداء العمال" in query_lower:
            productivity = WorkerProductivity.query.join(ProductionRun).order_by(WorkerProductivity.timestamp.desc()).limit(5).all()
            if productivity:
                context_parts.append("أحدث بيانات إنتاجية العمال:")
                for prod in productivity:
                    worker_name = prod.user.username if prod.user else "غير محدد"
                    run_id = prod.production_run_id
                    context_parts.append(f"- العامل {worker_name} في عملية الإنتاج رقم {run_id}:")
                    context_parts.append(f"  -- العناصر المنتجة: {prod.items_produced}")
                    context_parts.append(f"  -- الأخطاء: {prod.errors_made}")
                    context_parts.append(f"  -- ساعات العمل: {prod.hours_worked}")
                    if prod.efficiency_score:
                        context_parts.append(f"  -- معدل الكفاءة: {prod.efficiency_score}")

        # --- Fallback if no specific keywords match ---
        if not context_parts:
             context_parts.append("معلومات عامة: نظام كاتيلو يدير المخزون والمنتجات والموردين وعمليات الإنتاج.")

    except Exception as e:
        print(f"Error fetching context data: {e}")
        context_parts.append("حدث خطأ أثناء جلب البيانات من قاعدة البيانات.")


    return "\n".join(context_parts)

def prepare_image_part(image_data_base64):
    """Decodes base64 image data and prepares it for the Gemini API."""
    if not image_data_base64:
        return None
    try:
        # Remove potential data URL prefix (e.g., "data:image/jpeg;base64,")
        if ',' in image_data_base64:
            header, encoded = image_data_base64.split(',', 1)
            mime_type = header.split(':')[1].split(';')[0] # Extract mime type
        else:
            encoded = image_data_base64
            # Attempt to infer mime type, default to jpeg
            try:
                img_bytes_for_check = base64.b64decode(encoded)
                img = Image.open(io.BytesIO(img_bytes_for_check))
                mime_type = Image.MIME.get(img.format) or 'image/jpeg'
            except Exception:
                 mime_type = 'image/jpeg' # Default if inference fails


        image_bytes = base64.b64decode(encoded)
        return {"mime_type": mime_type, "data": image_bytes}
    except Exception as e:
        print(f"Error processing image data: {e}")
        return None

# --- API Route ---

@chatbot_bp.route('/ask', methods=['POST'])
@login_required
def ask_chatbot():
    if not model:
         return jsonify({"error": "Chatbot model not initialized or database connection failed."}), 500

    data = request.get_json()
    user_query = data.get('query')
    image_data_base64 = data.get('image_data') # Expecting base64 encoded image string

    if not user_query:
        return jsonify({"error": "Query is required."}), 400

    # 1. Fetch relevant context from DB based on query
    db_context = fetch_context_data(user_query)

    # 2. Prepare image part if provided
    image_part = prepare_image_part(image_data_base64)

    # 3. Construct the prompt for Gemini
    prompt_parts = [
        "أنت 'Hamla Guys' مساعد ذكي لنظام إدارة المخزون والإنتاج 'كاتيلو'. مهمتك هي الإجابة على أسئلة المستخدم باللغة العربية بناءً على المعلومات المتوفرة.",
        "استخدم فقط المعلومات المقدمة في قسم 'بيانات من النظام' للإجابة. إذا لم تكن المعلومات كافية أو غير موجودة، قل بوضوح أنك لا تملك هذه المعلومة المحددة.",
        "لا تخترع معلومات غير موجودة في السياق.",
        "إذا تم تقديم صورة، حاول ربط إجابتك بها إذا كانت ذات صلة، خاصة إذا كانت تبدو كمنتج أو عنصر مخزون أو عملية إنتاج.",
        "\n--- بيانات من النظام ---\n",
        db_context,
        "\n--- سؤال المستخدم ---\n",
        user_query
    ]

    # Add image to prompt parts if it exists
    if image_part:
        # Gemini API expects content parts in a list: [text, image, text, ...] or [text, image]
        # Let's place the image before the final user query part for context
        prompt_parts.insert(-1, image_part) # Insert image before the user query text

    try:
        # 4. Generate content using Gemini API
        print(f"Sending to Gemini: {prompt_parts}") # Debug: See what's sent
        response = model.generate_content(prompt_parts)

        # 5. Extract and return the response text
        # Handle potential safety blocks or empty responses
        if response.parts:
            answer = response.text
        else:
             # Check safety ratings if needed response.prompt_feedback
             print(f"Gemini Response Blocked or Empty. Feedback: {response.prompt_feedback}")
             answer = "لم أتمكن من إنشاء رد. قد يكون السبب يتعلق بسياسات السلامة أو مشكلة فنية."


        return jsonify({"response": answer})

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        # Check for specific Gemini API errors if possible
        error_message = f"حدث خطأ أثناء التواصل مع مساعد الذكاء الاصطناعي: {e}"
        # You could add more specific error handling here based on common Gemini exceptions
        return jsonify({"error": error_message}), 500

# --- END OF FILE routes/chatbot_routes.py ---
