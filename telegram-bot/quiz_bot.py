import telebot
from telebot import types
import json
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class QuizState:
    def __init__(self):
        self.title = None
        self.description = None
        self.questions = []
        self.current_poll = None
        self.stats = {
            'total_attempts': 0,
            'participants': {},
            'rankings': []
        }

user_states = {}

bot = telebot.TeleBot("8035023863:AAH_7vWIy_bsxd9IOAxPNDm5P-pr52IME68")

def safe_reply(message, text, **kwargs):
    """Safely send a reply message with error handling and additional parameters"""
    try:
        return bot.reply_to(message, text, **kwargs)
    except Exception as e:
        logger.error(f"Error sending reply message: {e}")
        try:
            return bot.send_message(message.chat.id, text, **kwargs)
        except Exception as e:
            logger.error(f"Failed to send fallback message: {e}")
            try:
                # Last resort - try sending without any additional parameters
                return bot.send_message(message.chat.id, "An error occurred. Please try again.")
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")

def safe_send_message(chat_id, text, **kwargs):
    """Safely send a message with error handling and additional parameters"""
    try:
        return bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        try:
            # Try sending without any additional parameters
            return bot.send_message(chat_id, "An error occurred. Please try again.")
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

@bot.message_handler(commands=['start'])
def start(message):
    try:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("Create Quiz"))
        safe_send_message(message.chat.id, "Welcome to QuizBot! 📚", reply_markup=markup)
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        safe_send_message(message.chat.id, "An error occurred. Please try again.")

@bot.message_handler(func=lambda message: message.text == "Create Quiz")
def create_quiz(message):
    try:
        user_id = message.from_user.id
        user_states[user_id] = QuizState()
        safe_send_message(
            message.chat.id,
            "Let's create a new quiz. First, send me the title of your quiz\n"
            "(e.g., 'Aptitude Test' or '10 questions about bears')."
        )
    except Exception as e:
        logger.error(f"Error in create_quiz handler: {e}")
        safe_send_message(message.chat.id, "Error creating quiz. Please try again with /start")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) 
                    and not user_states[message.from_user.id].title)
def get_title(message):
    try:
        user_id = message.from_user.id
        user_states[user_id].title = message.text
        safe_send_message(
            message.chat.id,
            "Good. Now send me a description of your quiz.\n"
            "This is optional, you can /skip this step."
        )
    except Exception as e:
        logger.error(f"Error in get_title handler: {e}")
        safe_send_message(message.chat.id, "Error saving title. Please try again.")

@bot.message_handler(func=lambda message: message.text == '/skip' 
                    or (user_states.get(message.from_user.id) 
                    and user_states[message.from_user.id].title 
                    and user_states[message.from_user.id].description is None))
def get_description(message):
    try:
        user_id = message.from_user.id
        if message.text != '/skip':
            user_states[user_id].description = message.text

        safe_send_message(
            message.chat.id,
            "Good. Now send me a poll with your first question.\n"
            "Warning: this bot can't create anonymous polls. Users in groups "
            "will see votes from other members."
        )
        
        options = {
            'is_anonymous': False,
            'type': 'quiz',
            'allows_multiple_answers': False,
            'correct_option_id': 0
        }
        
        current_poll = bot.send_poll(
            message.chat.id,
            "Enter your question here",
            ["Option 1", "Option 2"],
            **options
        )
        
        user_states[user_id].current_poll = current_poll
    except Exception as e:
        logger.error(f"Error in get_description handler: {e}")
        safe_send_message(message.chat.id, "Error creating poll. Please try again.")

@bot.poll_answer_handler(func=lambda poll_answer: True)
def handle_poll_answer(poll_answer):
    try:
        user_id = poll_answer.user.id
        if user_id in user_states:
            state = user_states[user_id]
            
            if poll_answer.user.id not in state.stats['participants']:
                state.stats['participants'][poll_answer.user.id] = {
                    'correct_answers': 0,
                    'total_attempts': 0,
                    'average_time': 0
                }
            
            participant = state.stats['participants'][poll_answer.user.id]
            participant['total_attempts'] += 1
            
            if hasattr(state.current_poll, 'correct_option_id') and \
               poll_answer.option_ids[0] == state.current_poll.correct_option_id:
                participant['correct_answers'] += 1
    except Exception as e:
        logger.error(f"Error in poll answer handler: {e}")

@bot.message_handler(commands=['done'])
def finish_quiz(message):
    try:
        user_id = message.from_user.id
        if user_id not in user_states:
            safe_send_message(message.chat.id, "No active quiz creation found. Start with /start")
            return
        
        state = user_states[user_id]
        
        stats_text = (
            f"Quiz '{state.title}' created!\n\n"
            f"📊 Statistics:\n"
            f"• Total questions: {len(state.questions)}\n"
            f"• Participants: {len(state.stats['participants'])}\n\n"
            "Quiz is ready to share!"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("Start this quiz", callback_data="start_quiz"),
            types.InlineKeyboardButton("Start quiz in group", callback_data="start_group"),
            types.InlineKeyboardButton("Share quiz", callback_data="share_quiz"),
            types.InlineKeyboardButton("Edit quiz", callback_data="edit_quiz"),
            types.InlineKeyboardButton("Quiz stats", callback_data="quiz_stats")
        )
        
        safe_send_message(message.chat.id, stats_text, reply_markup=markup)
    except Exception as e:
        logger.error(f"Error in finish_quiz handler: {e}")
        safe_send_message(message.chat.id, "Error finishing quiz. Please try again.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        if call.data == "quiz_stats":
            show_quiz_stats(call.message.chat.id, call.from_user.id)
    except Exception as e:
        logger.error(f"Error in callback handler: {e}")
        try:
            bot.answer_callback_query(
                call.id,
                text="An error occurred. Please try again."
            )
        except Exception as e:
            logger.error(f"Failed to send callback answer: {e}")

def show_quiz_stats(chat_id, user_id):
    try:
        if user_id not in user_states:
            safe_send_message(chat_id, "No quiz stats available.")
            return
        
        state = user_states[user_id]
        
        if not state.stats['participants']:
            safe_send_message(chat_id, "No participants in this quiz yet.")
            return
        
        sorted_participants = sorted(
            state.stats['participants'].items(),
            key=lambda x: (x[1]['correct_answers'], -x[1]['average_time']),
            reverse=True
        )
        
        rankings_text = "🏆 Quiz Rankings:\n\n"
        for i, (participant_id, stats) in enumerate(sorted_participants[:10], 1):
            percentage = 0
            if stats['total_attempts'] > 0:
                percentage = (stats['correct_answers'] / stats['total_attempts']) * 100
            
            rankings_text += (
                f"{i}. User {participant_id}\n"
                f"   ✓ {stats['correct_answers']}/{stats['total_attempts']} "
                f"({percentage:.1f}%)\n"
            )
        
        safe_send_message(chat_id, rankings_text)
    except Exception as e:
        logger.error(f"Error in show_quiz_stats: {e}")
        safe_send_message(chat_id, "Error showing quiz stats.")

if __name__ == "__main__":
    logger.info("Bot is starting...")
    while True:
        try:
            bot.infinity_polling()
        except Exception as e:
            logger.error(f"Error in main polling loop: {e}")
            continue