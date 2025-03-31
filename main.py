

import logging, json, datetime, os, dotenv
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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
ADMIN_ID = 843171085

# Add conversation state
SEND_RECEIPT = 1
ADMIN_MESSAGE = 2
USER_MESSAGE = 3
LANGUAGE_SELECTION = 4

async def waiting(update: Update, context: CallbackContext) -> None:
    try:
        user_id = update.callback_query.from_user.id if update.callback_query else update.message.from_user.id
        a= await context.bot.send_message(chat_id=user_id, text="...", reply_markup=ReplyKeyboardRemove())
        await context.bot.delete_message(chat_id=user_id,message_id=a.message_id)
    except:
        print("error\n\n\n\n\n\n\n\nwaiting")

async def start(update: Update, context: CallbackContext) -> None:
    await waiting(update, context)
    #set commands
    await context.bot.set_my_commands([
        ('start', 'Register for a donation'),
        ('talk', 'Talk with the admin'),
        ('profile', 'To update your profile'),
        ('dele', 'Delete your account'),
        ('pay', 'Send payment receipt')
    ])

    print("Start")
    user_id = update.callback_query.from_user.id if update.callback_query else update.message.from_user.id
    user = session.query(User).filter_by(id=user_id).first()

    selected_lang = context.user_data.get('language')

    if user:
        # Show next payment info for registered users
        last_payment = user.last_payment_date
        next_payment = last_payment + datetime.timedelta(days=30 * user.duration)
        days_remaining = (next_payment - datetime.date.today()).days
        
        reply_markup = ReplyKeyboardMarkup(
            [[KeyboardButton(get_message('onetime_payment', user.language))]],
                resize_keyboard=True,
                one_time_keyboard=True)
        await context.bot.send_message(chat_id=user_id,
            text=get_message('payment_info', user.language, 
                       amount=user.donation_amount,
                       next_date=next_payment.strftime('%d %B %Y'),
                       days=days_remaining), reply_markup=reply_markup
        )
    elif selected_lang:
        webapp_url = f"{WEBAPP_URL}?lang={selected_lang}"
        reply_markup = ReplyKeyboardMarkup(
            [[KeyboardButton(
                text="Register",
                web_app=WebAppInfo(url=webapp_url)),],[KeyboardButton(get_message('onetime_payment', selected_lang))]],
                resize_keyboard=True,
                one_time_keyboard=True)
        
        await context.bot.send_message(chat_id=user_id,
            text=get_message('welcome'), reply_markup=reply_markup
        )

    else:
        
        # Show language selection buttons
        keyboard = [
            [InlineKeyboardButton("English", callback_data="lang_en"),
             InlineKeyboardButton("አማርኛ", callback_data="lang_am")],
            [InlineKeyboardButton("Afaan Oromoo", callback_data="lang_or"),
             InlineKeyboardButton("العربية", callback_data="lang_ar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(chat_id=user_id,
            text="Please select your preferred language\nቋንቋ ይምረጡ\nAfaan kee filadhu\nاختر لغتك",
            reply_markup=reply_markup
        )
        return LANGUAGE_SELECTION

async def handle_language_selection(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    selected_lang = query.data.split('_')[1]
    context.user_data['language'] = selected_lang
    await context.bot.delete_message(chat_id=query.from_user.id, message_id=query.message.message_id)
    
    await start(update, context)



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

async def handle_webapp_data(update: Update, context: CallbackContext) -> None:
    await waiting(update, context)

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
    today = datetime.date.today()
    last_payment_date = today - datetime.timedelta(days=30 * int(data['duration']))
    
    # Handle new registration
    user = User(
        id=user_id,
        first_name=data['fullName'],
        phone_number=data['phone'],
        language=language,
        donation_amount=int(data['amount']),
        duration=int(data['duration']),
        last_payment_date=last_payment_date
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

async def onetime_payment_handler(update: Update, context: CallbackContext) -> int:
    await waiting(update, context)
    user_id = update.callback_query.from_user.id if update.callback_query else update.message.from_user.id
    update = update.callback_query if update.callback_query else update
    selected_lang = context.user_data.get('language')

    
    if not selected_lang:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return await start(update, context)
        selected_lang = user.language

    await context.bot.send_message(chat_id=user_id,
            text=get_message("onetime_payment_message", selected_lang)
    )
    return SEND_RECEIPT



async def handle_onetime_payment_receipt(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    name= update.message.from_user.first_name
    username= update.message.from_user.username

    selected_lang = context.user_data.get('language')

    
    if not selected_lang:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return await start(update, context)
        selected_lang = user.language
    
    photo = update.message.photo[-1]
    today = datetime.date.today()

    keyboard = [
        [InlineKeyboardButton("✉️ Message User", callback_data=f"message_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_message = (
        f"📝 Payment Receipt Submission\n\n"
        f"User: {name} - @{username}\n"
        f"Submission Date: {today.strftime('%d %B %Y')}"
    )
    
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo.file_id,
        reply_markup=reply_markup,
        caption=admin_message
    )
    
    
    user_keyboard = [
        [InlineKeyboardButton("💬 Talk to Admin", callback_data="talk_admin")]
    ]
    user_reply_markup = InlineKeyboardMarkup(user_keyboard)
    
    await context.bot.send_message(chat_id=user_id,
            text=get_message("onetime_payment_success", selected_lang),
        reply_markup=user_reply_markup
    )
    return ConversationHandler.END
    


async def handle_receipt(update: Update, context: CallbackContext) -> int:
    await waiting(update, context)
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
    
    await context.bot.send_message(chat_id=user_id,
            text=get_message('payment_success', user.language,
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
    user_id = update.callback_query.from_user.id if update.callback_query else update.message.from_user.id
    
    await context.bot.send_message(chat_id=user_id,
            text="Please type your message to the admin:")
    return USER_MESSAGE

async def send_user_message(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    name = update.message.from_user.first_name
    message_text = update.message.text
    
    keyboard = [
        [InlineKeyboardButton("✉️ Reply", callback_data=f"message_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=get_message('user_message', 'en',
                        name=name,
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

async def handle_messages(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    text = update.message.text
    selected_lang = context.user_data.get('language')
    
    if not selected_lang:
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            selected_lang = user.language
        else:
            return await start(update, context)
    
    await update.message.reply_text(
        get_message('unknown_input', selected_lang))
    
    print(text)




def main():
    app = Application.builder().token(TOKEN).build()

    
    pay_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("pay", pay),
                      CallbackQueryHandler(pay, pattern=r'^(pay_now)$')],
        states={
            SEND_RECEIPT: [MessageHandler(filters.PHOTO, handle_receipt)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    onetime_payment_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'^(One-Time Payment|Gatii Yeroo Tokkoo|አንድ ጊዜ ክፍያ|دفع مرة واحدة)$'), onetime_payment_handler)],
        states={
            SEND_RECEIPT: [MessageHandler(filters.PHOTO, handle_onetime_payment_receipt)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    
    message_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_admin_message_button, pattern=r'^message_\d+$'),
            CallbackQueryHandler(handle_user_talk_button, pattern=r'^talk_admin$'),
            CommandHandler("talk", handle_user_talk_button)
        ],
        states={
            ADMIN_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_admin_message)],
            USER_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_user_message)]
        },
        fallbacks=[CommandHandler("cancel", handle_cancel)]
    )
        

    
    app.add_handler(CallbackQueryHandler(handle_language_selection, pattern=r'^lang_'))
    # Add callback handler for payment buttons
    app.add_handler(CallbackQueryHandler(handle_payment_button, pattern=r'^(ignore_payment)$'))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("dele", dele))
    app.add_handler(pay_conv_handler)
    app.add_handler(onetime_payment_conv)
    app.add_handler(message_conv_handler)
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))

    app.add_handler(MessageHandler(filters.TEXT, handle_messages))
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()