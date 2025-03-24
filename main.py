

import logging, json, datetime, os, dotenv
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from sqlalchemy.orm import sessionmaker
from telegram.ext import ConversationHandler, ContextTypes
from db.models import User, Donation, engine
from utils.helper import get_message, get_user_language

# Setup
Session = sessionmaker(bind=engine)
session = Session()
logging.basicConfig(level=logging.INFO)

dotenv.load_dotenv()
WEBAPP_URL = "https://sualh1999.github.io/hanif_donation_bot/"
TOKEN = os.getenv("TOKEN")
# Add conversation state
SEND_RECEIPT = 1
ADMIN_MESSAGE = 2
USER_MESSAGE = 3
LANGUAGE_SELECTION = 4

async def start(update: Update, context: CallbackContext) -> None:
    print("Start")
    user_id = update.message.from_user.id
    user = session.query(User).filter_by(id=user_id).first()

    if user:
        # Show next payment info for registered users
        last_payment = user.last_payment_date
        next_payment = last_payment + datetime.timedelta(days=30 * user.duration)
        days_remaining = (next_payment - datetime.date.today()).days
        
        await update.message.reply_text(
            get_message('payment_info', user.language, 
                       amount=user.donation_amount,
                       next_date=next_payment.strftime('%d %B %Y'),
                       days=days_remaining)
        )
    else:
        #set command /start
        await context.bot.set_my_commands([
            ('start', 'Register for a donation'),
            ('profile', 'To update your profile'),
            ('dele', 'Delete your account'),
            ('pay', 'Send payment receipt')
        ])
        
        # Show language selection buttons
        keyboard = [
            [InlineKeyboardButton("English", callback_data="lang_en"),
             InlineKeyboardButton("አማርኛ", callback_data="lang_am")],
            [InlineKeyboardButton("Afaan Oromoo", callback_data="lang_or"),
             InlineKeyboardButton("العربية", callback_data="lang_ar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Please select your preferred language\nቋንቋ ይምረጡ\nAfaan kee filadhu\nاختر لغتك",
            reply_markup=reply_markup
        )
        return LANGUAGE_SELECTION

async def handle_language_selection(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    selected_lang = query.data.split('_')[1]
    context.user_data['language'] = selected_lang
    
    webapp_url = f"{WEBAPP_URL}?lang={selected_lang}"
    reply_markup = ReplyKeyboardMarkup.from_button(
        KeyboardButton(
            text="Register",
            web_app=WebAppInfo(url=webapp_url)),
            resize_keyboard=True,
            one_time_keyboard=True)
    
    await query.message.reply_text(
        get_message('welcome', selected_lang),
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def handle_payment_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "ignore_payment":
        user_id = query.from_user.id
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.last_payment_date = datetime.date.today()
            session.commit()
            await query.message.reply_text(
                get_message('payment_success', user.language,
                           next_due=(datetime.date.today() + datetime.timedelta(days=30 * user.duration)).strftime('%d %B %Y'))
            )
    elif query.data == "pay_now":
        await pay(update, context)

async def handle_webapp_data(update: Update, context: CallbackContext) -> None:
    data = json.loads(update.effective_message.web_app_data.data)
    user_id = update.effective_message.from_user.id

    langMap = {
        "Amharic": "am",
        "Affan Oromo": "or",
        "English": "en",
        "Arabic": "ar"
    }
    language = langMap[data['language']]
    
    if data.get('isUpdate'):
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.first_name = data['fullName']
            user.phone_number = data['phone']
            user.language = language
            user.donation_amount = int(data['amount'])
            user.duration = int(data['duration'])
            session.commit()
            
            next_due = user.last_payment_date + datetime.timedelta(days=30 * int(data['duration']))
            await update.message.reply_text(
                get_message('profile_updated', language,
                           amount=data['amount'],
                           duration=data['duration'],
                           next_due=next_due.strftime('%d %B %Y'))
            )
            return
    
    # Handle new registration
    user = User(
        id=user_id,
        first_name=data['fullName'],
        phone_number=data['phone'],
        language=language,
        donation_amount=int(data['amount']),
        duration=int(data['duration']),
        last_payment_date=datetime.date.today()
    )
    
    session.add(user)
    session.commit()

    next_due = datetime.date.today() + datetime.timedelta(days=30 * int(data['duration']))
    keyboard = [
        [InlineKeyboardButton("Pay Now", callback_data="pay_now"),
         InlineKeyboardButton("Ignore", callback_data="ignore_payment")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        get_message('registration_complete', language,
                    amount=data['amount'],
                    duration=data['duration'],
                    next_due=next_due.strftime('%d %B %Y')),
        reply_markup=reply_markup
    )

async def dele(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user = session.query(User).filter_by(id=user_id).first()
    if user:
        session.delete(user)
        session.commit()
        await context.bot.send_message(
            chat_id=user_id,
            text=get_message('account_deleted', user.language)
        )

async def pay(update: Update, context: CallbackContext) -> int:
    print(update)
    user_id = update.callback_query.from_user.id if update.callback_query else update.message.from_user.id
    update = update.callback_query if update.callback_query else update
    user = session.query(User).filter_by(id=user_id).first()
    
    if not user:
        await update.message.reply_text("Please register first using /start")
        return ConversationHandler.END

    today = datetime.date.today()
    last_payment = user.last_payment_date
    next_payment = last_payment + datetime.timedelta(days=30 * user.duration)
    days_remaining = (next_payment - today).days
    
    if last_payment and days_remaining > 0:
        await update.message.reply_text(
            get_message('payment_success', user.language,
                           next_due=next_payment.strftime('%d %B %Y'))
            )
        return ConversationHandler.END

    await update.message.reply_text(
        get_message('payment_reminder', user.language,
                   name=user.first_name,
                   amount=user.donation_amount,
                   due_date=next_payment.strftime('%d %B %Y'))
    )
    return SEND_RECEIPT
    

ADMIN_ID = 843171085

async def handle_receipt(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user = session.query(User).filter_by(id=user_id).first()
    
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    
    folder = "receipts\\"
    today = datetime.date.today()
    file_path = f"{folder}{user_id}-{today}_receipt.jpg"
    await photo_file.download_to_drive(file_path)
    
    donation = Donation(
        user_id=user_id,
        amount=user.donation_amount,
        date_paid=today,
        receipt=file_path
    )
    session.add(donation)
    
    keyboard = [
        [InlineKeyboardButton("✉️ Message User", callback_data=f"message_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_message = (
        f"📝 Payment Receipt Submission\n\n"
        f"User: {user.first_name}\n"
        f"Amount: {user.donation_amount}\n"
        f"Due Date: {(user.last_payment_date + datetime.timedelta(days=30 * user.duration)).strftime('%d %B %Y')}\n"
        f"Submission Date: {today.strftime('%d %B %Y')}"
    )
    
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Failed to forward receipt to admin: {str(e)}")
    
    user.last_payment_date = today
    session.commit()
    
    next_due = today + datetime.timedelta(days=30 * user.duration)
    
    user_keyboard = [
        [InlineKeyboardButton("💬 Talk to Admin", callback_data="talk_admin")]
    ]
    user_reply_markup = InlineKeyboardMarkup(user_keyboard)
    
    await update.message.reply_text(
        get_message('payment_success', user.language,
                   next_due=next_due.strftime('%d %B %Y')),
        reply_markup=user_reply_markup
    )
    return ConversationHandler.END

async def handle_admin_message_button(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split('_')[1])
    context.user_data['target_user_id'] = user_id
    
    await query.message.reply_text("Please type your message to the user:")
    return ADMIN_MESSAGE

async def send_admin_message(update: Update, context: CallbackContext) -> int:
    user_id = context.user_data.get('target_user_id')
    message_text = update.message.text
    user = session.query(User).filter_by(id=user_id).first()
    
    keyboard = [
        [InlineKeyboardButton("💬 Reply to Admin", callback_data="talk_admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text=get_message('admin_message', user.language, message=message_text),
        reply_markup=reply_markup
    )
    
    await update.message.reply_text("Message sent successfully!")
    return ConversationHandler.END

async def handle_user_talk_button(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text("Please type your message to the admin:")
    return USER_MESSAGE

async def send_user_message(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user = session.query(User).filter_by(id=user_id).first()
    message_text = update.message.text
    
    keyboard = [
        [InlineKeyboardButton("✉️ Reply", callback_data=f"message_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=get_message('user_message', 'en',
                        name=user.first_name,
                        id=user_id,
                        message=message_text),
        reply_markup=reply_markup
    )
    
    await update.message.reply_text("Your message has been sent to the admin!")
    return ConversationHandler.END

async def handle_cancel(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Cancelled")
    return ConversationHandler.END

async def profile(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user = session.query(User).filter_by(id=user_id).first()
    
    if not user:
        return
    
    webapp_url = f"{WEBAPP_URL}?lang={user.language}&user_id={user_id}&fullName={user.first_name.replace(' ', '%20')}&phone={user.phone_number}&amount={user.donation_amount}&duration={user.duration}"
    reply_markup = ReplyKeyboardMarkup.from_button(
        KeyboardButton(
            text="Update Profile",
            web_app=WebAppInfo(url=webapp_url)),
            resize_keyboard=True,
            one_time_keyboard=True)
    
    await update.message.reply_text(
        get_message('profile_update', user.language),
        reply_markup=reply_markup
    )

def main():
    app = Application.builder().token(TOKEN).build()

    
    pay_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("pay", pay)],
        states={
            SEND_RECEIPT: [MessageHandler(filters.PHOTO, handle_receipt)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    
    message_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_admin_message_button, pattern=r'^message_\d+$'),
            CallbackQueryHandler(handle_user_talk_button, pattern=r'^talk_admin$')
        ],
        states={
            ADMIN_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_admin_message)],
            USER_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_user_message)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
        

    start_h = CommandHandler("start", start)
    app.add_handler(CallbackQueryHandler(handle_language_selection, pattern=r'^lang_'))
    # Add callback handler for payment buttons
    app.add_handler(CallbackQueryHandler(handle_payment_button, pattern=r'^(pay_now|ignore_payment)$'))
    app.add_handler(start_h)
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("dele", dele))
    app.add_handler(pay_conv_handler)
    app.add_handler(message_conv_handler)
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()