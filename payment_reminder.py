import asyncio, os, dotenv
import datetime
from sqlalchemy.orm import sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application
from db.models import User, engine

dotenv.load_dotenv()

TOKEN = os.getenv("TOKEN")

# Setup database session
Session = sessionmaker(bind=engine)
session = Session()

async def check_overdue_payments():
    while True:
        today = datetime.date.today()
        
        # Query for users with overdue payments
        users = session.query(User).all()
        
        for user in users:
            # If last_payment_date is None, use created_at date or today
            last_payment = user.last_payment_date
            next_payment = last_payment + datetime.timedelta(days=30 * user.duration)
            days_overdue = (today - next_payment).days
            
            print(f"User: {user.first_name}")
            print(f"Last payment: {last_payment}")
            print(f"Next payment: {next_payment}")
            print(f"Days overdue: {days_overdue}")
            
            if days_overdue >= 0:
                print(f"Sending reminder to {user.first_name}")
                # Create payment button
                keyboard = [[InlineKeyboardButton("Send Payment Receipt", callback_data="pay_now")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Send reminder message
                message = (
                    f"Dear {user.first_name},\n\n"
                    f"Your payment of {user.donation_amount} was due on {next_payment.strftime('%d %B %Y')}. "
                    f"Please send your payment receipt using the button below or by using the /pay command."
                )
                
                try:
                    app = Application.builder().token(TOKEN).build()
                    async with app:
                        await app.bot.send_message(
                            chat_id=user.id,
                            text=message,
                            reply_markup=reply_markup
                        )
                except Exception as e:
                    print(f"Failed to send reminder to user {user.id}: {str(e)}")
        
        # Wait for 24 hours before next check
        await asyncio.sleep(24 * 60 * 60)

if __name__ == "__main__":
    asyncio.run(check_overdue_payments())