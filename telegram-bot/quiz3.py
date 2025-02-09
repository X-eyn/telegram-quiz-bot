from telegram import Bot, Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    PollAnswerHandler,
    MessageHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
import json
import datetime
import logging
import asyncio

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
TOKEN = '8035023863:AAH_7vWIy_bsxd9IOAxPNDm5P-pr52IME68'
POLL_DATA_FILE = 'poll_data.json'
WEBAPP_URL = "https://scintillating-puppy-397098.netlify.app/"

# --- Global Variables ---
active_polls = {}
poll_data = {}
user_poll_creation_state = {}

# --- Load existing poll data from JSON file on startup ---
try:
    with open(POLL_DATA_FILE, 'r') as f:
        poll_data = json.load(f)
    logger.info("Poll data loaded from JSON file.")
except FileNotFoundError:
    poll_data = {}
    logger.info("No existing poll data file found. Starting fresh.")

# --- Helper Functions ---
def save_poll_data_to_json():
    """Saves the poll_data dictionary to the JSON file."""
    try:
        with open(POLL_DATA_FILE, 'w') as f:
            json.dump(poll_data, f, indent=4)
        logger.info("Poll data saved to JSON file.")
    except Exception as e:
        logger.error(f"Error saving poll data: {e}")

def generate_poll_id():
    """Generates a unique poll ID."""
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S")

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the /start command is issued."""
    await update.message.reply_text(
        'Hello! I am a poll bot. Use /poll to create a new poll, or /newquiz to create a quiz.'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a help message when the /help command is issued."""
    help_text = (
        "Available commands:\n"
        "/poll - Create a new poll interactively\n"
        "/newquiz - Create a quiz using WebApp\n"
        "/stoppoll - Stop the active poll in the chat\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(help_text)

async def new_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a button that opens the WebApp for quiz creation."""
    webapp_info = WebAppInfo(url=WEBAPP_URL)
    keyboard = [[InlineKeyboardButton("Create Quiz", web_app=webapp_info)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Click the button below to create a new quiz using the WebApp:",
        reply_markup=reply_markup
    )

async def create_poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the interactive poll creation process."""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Initialize poll creation state
    user_poll_creation_state[user_id] = {
        'question': None,
        'options': [],
        'chat_id': chat_id,
        'message_id_to_edit': None
    }

    keyboard = [
        [InlineKeyboardButton("Set Question", callback_data='set_question')],
        [InlineKeyboardButton("Add Option", callback_data='add_option')],
        [InlineKeyboardButton("Create Poll", callback_data='create_poll_final')],
        [InlineKeyboardButton("Cancel", callback_data='cancel_poll_creation')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = await update.message.reply_text(
        "Let's create a poll! Use the buttons below to set up your poll.\n\n"
        "Current Poll Setup:\n"
        "Question: Not set\n"
        "Options: (None)",
        reply_markup=reply_markup
    )
    user_poll_creation_state[user_id]['message_id_to_edit'] = message.message_id

async def update_interactive_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, message_id_to_edit: int):
    """Updates the interactive poll setup message with current question and options."""
    if user_id not in user_poll_creation_state:
        return

    poll_state = user_poll_creation_state[user_id]
    question_display = poll_state['question'] if poll_state['question'] else "Not set"
    options_display = "\n".join([f"- {opt}" for opt in poll_state['options']]) if poll_state['options'] else "(None)"

    keyboard = [
        [InlineKeyboardButton("Set Question", callback_data='set_question')],
        [InlineKeyboardButton("Add Option", callback_data='add_option')],
        [InlineKeyboardButton("Create Poll", callback_data='create_poll_final')],
        [InlineKeyboardButton("Cancel", callback_data='cancel_poll_creation')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.edit_message_text(
            chat_id=poll_state['chat_id'],
            message_id=message_id_to_edit,
            text=(
                "Let's create a poll! Use the buttons below to set up your poll.\n\n"
                "Current Poll Setup:\n"
                f"Question: {question_display}\n"
                f"Options:\n{options_display}"
            ),
            reply_markup=reply_markup
        )
    except BadRequest as e:
        logger.error(f"Error updating interactive message: {e}")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button presses for poll creation."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data
    chat_id = query.message.chat_id
    message_id_to_edit = user_poll_creation_state.get(user_id, {}).get('message_id_to_edit')

    if user_id not in user_poll_creation_state:
        await query.edit_message_text("Poll creation process timed out or was cancelled.")
        return

    if data == 'set_question':
        await context.bot.send_message(
            chat_id,
            "Please reply to *this message* with your poll question\\.",
            reply_to_message_id=message_id_to_edit,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        user_poll_creation_state[user_id]['awaiting_question'] = True

    elif data == 'add_option':
        await context.bot.send_message(
            chat_id,
            "Please reply to *this message* with a poll option\\.",
            reply_to_message_id=message_id_to_edit,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        user_poll_creation_state[user_id]['awaiting_option'] = True

    elif data == 'create_poll_final':
        await create_final_poll(update, context)

    elif data == 'cancel_poll_creation':
        await cancel_poll_setup(update, context)

    await update_interactive_message(update, context, user_id, message_id_to_edit)

async def handle_message_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles replies to messages during poll creation."""
    user_id = update.message.from_user.id
    message_text = update.message.text
    chat_id = update.message.chat_id
    
    if user_id not in user_poll_creation_state:
        return

    message_id_to_edit = user_poll_creation_state[user_id].get('message_id_to_edit')

    if user_poll_creation_state[user_id].get('awaiting_question'):
        user_poll_creation_state[user_id]['question'] = message_text
        user_poll_creation_state[user_id].pop('awaiting_question', None)
        await update.message.reply_text("✅ Question set!")

    elif user_poll_creation_state[user_id].get('awaiting_option'):
        if len(user_poll_creation_state[user_id]['options']) < 10:
            user_poll_creation_state[user_id]['options'].append(message_text)
            await update.message.reply_text(f"✅ Option '{message_text}' added!")
        else:
            await update.message.reply_text("❌ Maximum 10 options allowed for a poll.")
        user_poll_creation_state[user_id].pop('awaiting_option', None)

    await update_interactive_message(update, context, user_id, message_id_to_edit)

async def create_final_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Creates the final poll with collected data."""
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    if user_id not in user_poll_creation_state:
        await query.answer("Poll creation timed out or cancelled.")
        return

    poll_state = user_poll_creation_state[user_id]
    question = poll_state['question']
    options = poll_state['options']

    if not question:
        await query.answer("Please set a question first.")
        return
    if len(options) < 2:
        await query.answer("Please add at least two options.")
        return

    try:
        message = await context.bot.send_poll(
            chat_id,
            question,
            options,
            is_anonymous=False
        )

        poll_id_telegram = message.poll.id
        unique_poll_id = generate_poll_id()

        active_polls[poll_id_telegram] = {
            'poll_id_telegram': poll_id_telegram,
            'unique_poll_id': unique_poll_id,
            'question': question,
            'options': options,
            'created_by': user_id,
            'chat_id': chat_id,
            'start_time': datetime.datetime.now().isoformat(),
            'votes': {i: [] for i in range(len(options))},
            'message_id': message.message_id
        }

        await query.edit_message_text(
            f"Poll created!\n"
            f"Question: '{question}'\n"
            f"Options: {', '.join(options)}\n"
            f"Poll ID: {unique_poll_id}"
        )
        
        del user_poll_creation_state[user_id]

    except BadRequest as e:
        await query.answer(f"Error creating poll: {e}")
        logger.error(f"Poll creation error: {e}")

async def cancel_poll_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the poll creation process."""
    query = update.callback_query
    user_id = query.from_user.id

    if user_id in user_poll_creation_state:
        del user_poll_creation_state[user_id]
        await query.edit_message_text("Poll creation cancelled.")
    else:
        await query.answer("No poll creation in progress to cancel.")

async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles poll answers."""
    answer = update.poll_answer
    poll_id_telegram = answer.poll_id
    user = answer.user
    user_id = user.id
    username = user.username
    selected_options = answer.option_ids

    if poll_id_telegram in active_polls:
        poll_data_entry = active_polls[poll_id_telegram]
        
        # Reset previous votes for this user
        for option_votes in poll_data_entry['votes'].values():
            option_votes[:] = [vote for vote in option_votes if vote['user_id'] != user_id]
        
        # Add new votes
        for option_index in selected_options:
            if option_index in poll_data_entry['votes']:
                user_info = {'user_id': user_id, 'username': username}
                poll_data_entry['votes'][option_index].append(user_info)

async def stop_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stops the active poll and saves results."""
    chat_id = update.message.chat_id
    
    # Find the most recent active poll in this chat
    active_poll_in_chat = None
    latest_poll_start_time = None
    poll_id_to_stop = None
    
    for poll_telegram_id, poll_info in active_polls.items():
        if poll_info['chat_id'] == chat_id:
            poll_start_time = datetime.datetime.fromisoformat(poll_info['start_time'])
            if latest_poll_start_time is None or poll_start_time > latest_poll_start_time:
                latest_poll_start_time = poll_start_time
                active_poll_in_chat = poll_info
                poll_id_to_stop = poll_telegram_id

    if active_poll_in_chat:
        try:
            stopped_poll = await context.bot.stop_poll(
                chat_id,
                message_id=active_poll_in_chat['message_id']
            )

            poll_data_entry = active_polls.pop(poll_id_to_stop)
            poll_data_entry['end_time'] = datetime.datetime.now().isoformat()
            
            # Convert Poll object to dict for JSON serialization
            poll_data_entry['final_results'] = {
                'total_voter_count': stopped_poll.total_voter_count,
                'options': [{'text': opt.text, 'voter_count': opt.voter_count} 
                          for opt in stopped_poll.options]
            }

            unique_poll_id = poll_data_entry['unique_poll_id']
            poll_data[unique_poll_id] = poll_data_entry
            save_poll_data_to_json()

            # Prepare results message
            results_message = f"📊 Poll '{poll_data_entry['question']}' stopped. Results:\n\n"
            for i, option in enumerate(stopped_poll.options):
                voters = poll_data_entry['votes'].get(i, [])
                voters_text = ", ".join(f"@{v['username']}" if v['username'] 
                                      else f"User{v['user_id']}" for v in voters)
                results_message += (f"📌 {option.text}: {option.voter_count} votes\n"
                                  f"   Voters: {voters_text if voters else 'None'}\n")

            await update.message.reply_text(results_message)

        except BadRequest as e:
            await update.message.reply_text(f"Error stopping poll: {e}")
            logger.error(f"Poll stopping error: {e}")
    else:
        await update.message.reply_text("No active poll found in this chat to stop.")

async def webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles data sent from the WebApp."""
    query = update.inline_query
    data_string = query.query

    try:
        quiz_data = json.loads(data_string)
        logger.info("Received quiz data from WebApp: %s", json.dumps(quiz_data, indent=2))
        
        # Store the quiz data
        quiz_id = generate_poll_id()
        poll_data[quiz_id] = {
            'type': 'quiz',
            'data': quiz_data,
            'created_at': datetime.datetime.now().isoformat(),
            'created_by': query.from_user.id
        }
        save_poll_data_to_json()

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding WebApp data: {e}\nRaw data: {data_string}")

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles regular text messages."""
    # This can be expanded based on needs
    pass

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles unknown commands."""
    await update.message.reply_text(
        "Sorry, I don't understand that command. Use /help to see available commands."
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles errors."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Send message to the user
    error_message = "An error occurred while processing your request. Please try again."
    
    if update and update.effective_message:
        await update.effective_message.reply_text(error_message)

async def main():
    """Starts the bot."""
    # Create the Application with explicit scheduler settings
    application = (
        Application.builder()
        .token(TOKEN)
        .job_queue(None)  # Disable job queue since we don't use it
        .build()
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("poll", create_poll_command))
    application.add_handler(CommandHandler("newquiz", new_quiz_command))
    application.add_handler(CommandHandler("stoppoll", stop_poll))
    application.add_handler(CommandHandler("stop", stop_poll))

    # Callback Query Handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # Message Handler for replies
    application.add_handler(MessageHandler(
        filters.REPLY & filters.TEXT & ~filters.COMMAND,
        handle_message_reply
    ))

    # Inline Query Handler
    application.add_handler(InlineQueryHandler(webapp_data))

    # Poll answer handler
    application.add_handler(PollAnswerHandler(poll_answer))

    # Message handlers
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.REPLY,
        text_message_handler
    ))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # Error handler
    application.add_error_handler(error_handler)

    # Start the Bot
    logger.info("Starting bot...")
    await application.initialize()
    await application.start()
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user. Goodbye!")