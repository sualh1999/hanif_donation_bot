from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters, 
    CallbackQueryHandler
)
import json
from pathlib import Path

# Load messages from JSON file
def load_messages():
    messages_path = Path(__file__).parent / 'messages.json'
    with open(messages_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# Get message in user's language
def get_message(message_key: str, language: str = 'en', **kwargs) -> str:
    """Get a message in the specified language with optional format parameters"""
    messages = load_messages()
    if message_key not in messages:
        return f"Message key '{message_key}' not found"
    
    message_translations = messages[message_key]
    if language not in message_translations:
        # Fallback to English if translation not available
        language = 'en'
    
    message = message_translations[language]
    if kwargs:
        try:
            return message.format(**kwargs)
        except KeyError as e:
            return f"Missing format parameter: {str(e)}"
    return message

# Get user's language preference
def get_user_language(user) -> str:
    """Get user's preferred language code"""
    return getattr(user, 'language', 'en')
