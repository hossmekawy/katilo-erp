import os
import json
import time
from datetime import datetime
from flask_login import current_user
from pathlib import Path

class ChatHistoryManager:
    """
    Manages chat history for users by storing conversations in JSON files.
    Each user has their own directory with chat session files.
    """
    
    def __init__(self, base_directory='static/chat_history'):
        """
        Initialize the chat history manager.
        
        Args:
            base_directory: Base directory to store chat history files
        """
        self.base_directory = base_directory
        # Ensure the base directory exists
        os.makedirs(self.base_directory, exist_ok=True)
    
    def _get_user_directory(self, user_id):
        """Get the directory for a specific user's chat history."""
        user_dir = os.path.join(self.base_directory, f"user_{user_id}")
        os.makedirs(user_dir, exist_ok=True)
        return user_dir
    
    def create_chat_session(self, user_id, title=None):
        """
        Create a new chat session for a user.
        
        Args:
            user_id: The ID of the user
            title: Optional title for the chat session
            
        Returns:
            chat_id: The ID of the new chat session
        """
        chat_id = f"chat_{int(time.time())}"
        user_dir = self._get_user_directory(user_id)
        
        # Create a new chat session file
        chat_data = {
            "chat_id": chat_id,
            "user_id": user_id,
            "title": title or "New Chat",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "messages": [
                {
                    "text": "مرحباً! أنا Hamla Guys، مساعد كاتيلو الذكي. كيف يمكنني مساعدتك اليوم؟ يمكنك سؤالي عن المخزون، المنتجات، الموردين، أو أي شيء آخر متعلق بنظام كاتيلو.",
                    "sender": "bot",
                    "timestamp": datetime.now().isoformat()
                }
            ]
        }
        
        # Save the chat session to a file
        chat_file_path = os.path.join(user_dir, f"{chat_id}.json")
        with open(chat_file_path, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, ensure_ascii=False, indent=2)
        
        return chat_id
    
    def get_chat_sessions(self, user_id):
        """
        Get all chat sessions for a user.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            list: List of chat session metadata
        """
        user_dir = self._get_user_directory(user_id)
        chat_sessions = []
        
        # List all JSON files in the user directory
        for file_name in os.listdir(user_dir):
            if file_name.endswith('.json'):
                file_path = os.path.join(user_dir, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        chat_data = json.load(f)
                        # Extract just the metadata, not all messages
                        chat_sessions.append({
                            "chat_id": chat_data.get("chat_id"),
                            "title": chat_data.get("title", "Untitled Chat"),
                            "created_at": chat_data.get("created_at"),
                            "updated_at": chat_data.get("updated_at"),
                            "message_count": len(chat_data.get("messages", []))
                        })
                except Exception as e:
                    print(f"Error reading chat file {file_path}: {e}")
        
        # Sort by updated_at (newest first)
        chat_sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return chat_sessions
    
    def get_chat_session(self, user_id, chat_id):
        """
        Get a specific chat session with all messages.
        
        Args:
            user_id: The ID of the user
            chat_id: The ID of the chat session
            
        Returns:
            dict: Chat session data including messages
        """
        user_dir = self._get_user_directory(user_id)
        chat_file_path = os.path.join(user_dir, f"{chat_id}.json")
        
        if not os.path.exists(chat_file_path):
            return None
        
        try:
            with open(chat_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading chat file {chat_file_path}: {e}")
            return None
    
    def add_message(self, user_id, chat_id, message, sender):
        """
        Add a message to a chat session.
        
        Args:
            user_id: The ID of the user
            chat_id: The ID of the chat session
            message: The message text
            sender: 'user' or 'bot'
            
        Returns:
            bool: True if successful, False otherwise
        """
        user_dir = self._get_user_directory(user_id)
        chat_file_path = os.path.join(user_dir, f"{chat_id}.json")
        
        if not os.path.exists(chat_file_path):
            return False
        
        try:
            # Read the current chat data
            with open(chat_file_path, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)
            
            # Add the new message
            chat_data["messages"].append({
                "text": message,
                "sender": sender,
                "timestamp": datetime.now().isoformat()
            })
            
            # Update the updated_at timestamp
            chat_data["updated_at"] = datetime.now().isoformat()
            
            # Update the title if it's the first user message and current title is generic
            if sender == 'user' and len(chat_data["messages"]) == 2 and chat_data["title"] == "New Chat":
                # Use the first ~30 chars of the user's first message as the title
                chat_data["title"] = (message[:30] + '...') if len(message) > 30 else message
            
            # Save the updated chat data
            with open(chat_file_path, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"Error updating chat file {chat_file_path}: {e}")
            return False
    
    def delete_chat_session(self, user_id, chat_id):
        """
        Delete a chat session.
        
        Args:
            user_id: The ID of the user
            chat_id: The ID of the chat session
            
        Returns:
            bool: True if successful, False otherwise
        """
        user_dir = self._get_user_directory(user_id)
        chat_file_path = os.path.join(user_dir, f"{chat_id}.json")
        
        if not os.path.exists(chat_file_path):
            return False
        
        try:
            os.remove(chat_file_path)
            return True
        except Exception as e:
            print(f"Error deleting chat file {chat_file_path}: {e}")
            return False
    
    def update_chat_title(self, user_id, chat_id, new_title):
        """
        Update the title of a chat session.
        
        Args:
            user_id: The ID of the user
            chat_id: The ID of the chat session
            new_title: The new title for the chat session
            
        Returns:
            bool: True if successful, False otherwise
        """
        user_dir = self._get_user_directory(user_id)
        chat_file_path = os.path.join(user_dir, f"{chat_id}.json")
        
        if not os.path.exists(chat_file_path):
            return False
        
        try:
            # Read the current chat data
            with open(chat_file_path, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)
            
            # Update the title
            chat_data["title"] = new_title
            
            # Save the updated chat data
            with open(chat_file_path, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"Error updating chat title {chat_file_path}: {e}")
            return False
