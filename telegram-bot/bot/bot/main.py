import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Load environment variables
load_dotenv()

# Get token from environment variable
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

class QuizBot:
    def __init__(self):
        self.active_quizzes = {}
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /start is issued."""
        keyboard = [
            [
                InlineKeyboardButton("Create Quiz", callback_data='create_quiz'),
                InlineKeyboardButton("My Quizzes", callback_data='my_quizzes')
            ],
            [
                InlineKeyboardButton("Results", callback_data='results'),
                InlineKeyboardButton("Help", callback_data='help')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            'Welcome to the Quiz Bot! 📚\n\n'
            'I can help you create and manage quizzes with:\n'
            '• Text and image questions\n'
            '• Multiple choice answers\n'
            '• Student score tracking\n\n'
            'What would you like to do?',
            reply_markup=reply_markup
        )
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /help is issued."""
        help_text = (
            "Here are the available commands:\n\n"
            "/start - Start the bot\n"
            "/newquiz - Create a new quiz\n"
            "/myquizzes - View your quizzes\n"
            "/results - View quiz results\n"
            "/help - Show this help message"
        )
        await update.message.reply_text(help_text)
    
    async def button_click(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks."""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'create_quiz':
            await query.message.reply_text("Let's create a new quiz! Please send /newquiz to start.")
        elif query.data == 'my_quizzes':
            await query.message.reply_text("You don't have any quizzes yet.")
        elif query.data == 'results':
            await query.message.reply_text("No quiz results available yet.")
        elif query.data == 'help':
            await self.help(update, context)

def main():
    """Start the bot."""
    # Create the Application and pass it your bot's token
    quiz_bot = QuizBot()
    application = Application.builder().token(TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", quiz_bot.start))
    application.add_handler(CommandHandler("help", quiz_bot.help))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(quiz_bot.button_click))

    # Start the Bot
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()