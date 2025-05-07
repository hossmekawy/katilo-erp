# routes/chatbot_routes.py

import os
import io
import base64
import inspect

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from dotenv import load_dotenv
from PIL import Image
import google.generativeai as genai

from utils.chat_history_manager import ChatHistoryManager
import models                # your package containing all SQLAlchemy model classes
from models import db        # the SQLAlchemy `db` instance

# -------------------------------------------------------------------
# 1. Dynamically gather all model classes that have a __table__
# -------------------------------------------------------------------
MODEL_CLASSES = {
    name: cls for name, cls in inspect.getmembers(models, inspect.isclass)
    if hasattr(cls, '__table__')
}

# -------------------------------------------------------------------
# 2. Blueprint setup
# -------------------------------------------------------------------
chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/api/chatbot')

# Load environment and configure Gemini
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not found in environment variables")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

chat_history_manager = ChatHistoryManager()

# -------------------------------------------------------------------
# 3. Helper: fetch_context_data
# -------------------------------------------------------------------
def fetch_context_data(query: str) -> str:
    """Fetch database context based on keyword→model mapping, with fallback."""
    if not db.session or not model:
        return "لا يمكن الوصول إلى بيانات النظام أو نموذج الذكاء الاصطناعي."

    q = query.lower()
    parts = []

    # Map Arabic keywords to (model_name, loader_fn)
    KEYWORD_MAP = {
        # Inventory overview
        "حالة المخزون": (
            "Inventory",
            lambda cls: cls.query
                          .join(models.Item)
                          .join(models.Warehouse)
                          .limit(10)
                          .all()
        ),
        # Low-stock (reorder-level)
        "حد إعادة الطلب": (
            "Inventory",
            lambda cls: cls.query
                          .join(models.Item)
                          .filter(cls.quantity <= models.Item.reorder_level)
                          .join(models.Warehouse)
                          .all()
        ),
        # Category list
        "تصنيف": (
            "Category",
            lambda cls: cls.query.limit(10).all()
        ),
        # Purchase orders
        "طلب شراء": (
            "PurchaseOrder",
            lambda cls: cls.query.order_by(cls.order_date.desc()).limit(5).all()
        ),
        # Sales orders
        "طلب بيع": (
            "SalesOrder",
            lambda cls: cls.query.order_by(cls.order_date.desc()).limit(5).all()
        ),
        # Shipments
        "شحنة": (
            "Shipment",
            lambda cls: cls.query.order_by(cls.shipment_date.desc()).limit(5).all()
        ),
        # Production runs
        "إنتاج": (
            "ProductionRun",
            lambda cls: cls.query.order_by(cls.planned_start_date.desc()).limit(5).all()
        ),
        # Quality checks
        "جودة": (
            "QualityCheckResult",
            lambda cls: cls.query.order_by(cls.checked_at.desc()).limit(5).all()
        ),
        # Support tickets
        "دعم": (
            "SupportTicket",
            lambda cls: cls.query.filter_by(status='open').limit(5).all()
        ),
        # AI suggestions
        "اقتراح": (
            "AISuggestion",
            lambda cls: cls.query.order_by(cls.created_at.desc()).limit(5).all()
        ),
        # …add more as needed…
    }

    for kw, (model_name, loader) in KEYWORD_MAP.items():
        if kw in q and model_name in MODEL_CLASSES:
            cls = MODEL_CLASSES[model_name]
            try:
                records = loader(cls)
                if records:
                    parts.append(f"**{model_name}**:")
                    for rec in records:
                        # custom formatting for Inventory
                        if model_name == "Inventory":
                            parts.append(
                                f"- {rec.item.name}: الكمية {rec.quantity} في المستودع {rec.warehouse.name}"
                            )
                        else:
                            parts.append(f"- {rec}")
            except Exception as e:
                parts.append(f"خطأ أثناء جلب بيانات {model_name}: {e}")

    # Fallback: dump up to 3 sample rows from every table
    if not parts:
        parts.append("**عرض بيانات عينة**:")
        for model_name, cls in MODEL_CLASSES.items():
            try:
                rows = cls.query.limit(3).all()
                if rows:
                    parts.append(f"**{model_name}**:")
                    for r in rows:
                        parts.append(f"- {r}")
            except:
                continue

    return "\n".join(parts)

# -------------------------------------------------------------------
# 4. Helper: image preparation for Gemini
# -------------------------------------------------------------------
def prepare_image_part(image_data_base64):
    if not image_data_base64:
        return None
    # split off any "data:image/...;base64," prefix
    if ',' in image_data_base64:
        header, encoded = image_data_base64.split(',', 1)
        mime = header.split(';')[0].split(':')[1]
    else:
        encoded = image_data_base64
        mime = 'image/jpeg'
    try:
        data = base64.b64decode(encoded)
        return {"mime_type": mime, "data": data}
    except Exception:
        return None

# -------------------------------------------------------------------
# 5. Session CRUD endpoints
# -------------------------------------------------------------------
@chatbot_bp.route('/', methods=['GET'])
@login_required
def chat_page():
    if not current_user.has_permission('use_chatbot') and current_user.role.name != 'admin':
        return render_template('unauthorized.html'), 403
    return render_template('chat.html')

@chatbot_bp.route('/sessions', methods=['GET'])
@login_required
def get_chat_sessions():
    if not current_user.has_permission('use_chatbot') and current_user.role.name != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify(chat_history_manager.get_chat_sessions(current_user.id))

@chatbot_bp.route('/sessions', methods=['POST'])
@login_required
def create_chat_session():
    if not current_user.has_permission('use_chatbot') and current_user.role.name != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    title = request.json.get('title') if request.is_json else None
    chat_id = chat_history_manager.create_chat_session(current_user.id, title)
    return jsonify(chat_history_manager.get_chat_session(current_user.id, chat_id))

@chatbot_bp.route('/sessions/<chat_id>', methods=['GET'])
@login_required
def get_chat_session(chat_id):
    if not current_user.has_permission('use_chatbot') and current_user.role.name != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    session = chat_history_manager.get_chat_session(current_user.id, chat_id)
    if not session:
        return jsonify({"error": "Not found"}), 404
    return jsonify(session)

@chatbot_bp.route('/sessions/<chat_id>', methods=['DELETE'])
@login_required
def delete_chat_session(chat_id):
    if not current_user.has_permission('use_chatbot') and current_user.role.name != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    success = chat_history_manager.delete_chat_session(current_user.id, chat_id)
    return jsonify({"success": success})

@chatbot_bp.route('/sessions/<chat_id>/title', methods=['PUT'])
@login_required
def update_chat_title(chat_id):
    if not current_user.has_permission('use_chatbot') and current_user.role.name != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json() or {}
    new_title = data.get('title')
    if not new_title:
        return jsonify({"error": "Title is required"}), 400
    success = chat_history_manager.update_chat_title(current_user.id, chat_id, new_title)
    return jsonify({"success": success})

# -------------------------------------------------------------------
# 6. Suggested questions endpoint
# -------------------------------------------------------------------
@chatbot_bp.route('/suggested', methods=['GET'])
@login_required
def suggested_questions():
    return jsonify({
        "المخزون والمنتجات": [
            "ما هي حالة المخزون الحالية؟",
            "ما هي المنتجات التي وصلت لحد إعادة الطلب؟",
            "ما هي التصنيفات الموجودة في النظام؟",
            "ما هي المنتجات الأكثر مبيعاً هذا الشهر؟"
        ],
        # …other categories…
    })

# -------------------------------------------------------------------
# 7. Main chat endpoint
# -------------------------------------------------------------------
@chatbot_bp.route('/ask', methods=['POST'])
@login_required
def ask_chatbot():
    if not current_user.has_permission('use_chatbot') and current_user.role.name != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json() or {}
    user_query    = (data.get('query') or "").strip()
    image_data    = data.get('image_data')
    chat_id       = data.get('chat_id')

    if not user_query:
        return jsonify({"error": "Query is required."}), 400

    # ensure session
    if not chat_id:
        chat_id = chat_history_manager.create_chat_session(current_user.id)
    chat_history_manager.add_message(current_user.id, chat_id, user_query, 'user')

    # build prompt
    db_context = fetch_context_data(user_query)
    image_part  = prepare_image_part(image_data)
    session     = chat_history_manager.get_chat_session(current_user.id, chat_id)
    history     = "\n".join(
        f"{'المستخدم' if m['sender']=='user' else 'المساعد'}: {m['text']}"
        for m in session['messages'][-5:]
    )

    prompt_parts = [
        "أنت 'Hamla Guys'، مساعد ذكي لنظام كاتيلو لإدارة المخزون، المشتريات، الإنتاج، المبيعات، المالية، والشحن.",
        "استخدم فقط البيانات المرفقة ولا تختلق أي معلومات.",
        "\n--- سجل المحادثة السابق ---\n", history,
        "\n--- بيانات من النظام ---\n", db_context,
        "\n--- سؤال المستخدم ---\n", user_query
    ]
    if image_part:
        prompt_parts.insert(-2, image_part)

    try:
        response = model.generate_content(prompt_parts)
        answer   = response.text or "لم أتمكن من إنشاء رد. حاول مرة أخرى لاحقاً."
        chat_history_manager.add_message(current_user.id, chat_id, answer, 'bot')
        return jsonify({"response": answer, "chat_id": chat_id})

    except Exception as e:
        return jsonify({"error": f"خطأ أثناء التواصل مع نموذج الذكاء الاصطناعي: {e}"}), 500
