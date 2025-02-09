#!/usr/bin/env python3
import telebot
from telebot import types
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import time

# Initialize bot
BOT_TOKEN = "8035023863:AAH_7vWIy_bsxd9IOAxPNDm5P-pr52IME68"  # Replace with your actual token
bot = telebot.TeleBot(BOT_TOKEN)

# Data structures
@dataclass
class Question:
    text: str
    options: List[str]
    correct_option: int
    explanation: Optional[str] = None
    media: Optional[Dict] = None

@dataclass
class Quiz:
    name: str
    description: Optional[str]
    questions: List[Question]
    timer: int
    shuffle_questions: bool
    shuffle_options: bool
    creator_id: int
    quiz_id: str

# Global storages
user_states = {}         # For quiz creation state
quizzes = {}             # quiz_id -> Quiz object
temp_quiz_data = {}      # Temporary quiz creation data
quiz_sessions = {}       # Active quiz playing sessions
quiz_attempts = {}       # quiz_id -> list of attempt dictionaries

# State machine for quiz creation
CREATE_STATES = {
    'IDLE': 0,
    'AWAITING_NAME': 1,
    'AWAITING_DESCRIPTION': 2,
    'AWAITING_QUESTION': 3,
    'AWAITING_OPTIONS': 4,
    'AWAITING_CORRECT_OPTION': 5,
    'AWAITING_EXPLANATION': 6,
    'AWAITING_TIMER': 7,
    'AWAITING_SHUFFLE_PREFERENCE': 8
}

# ----------------- Bot Commands and Handlers -----------------

# /start command handler
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    create_btn = types.KeyboardButton('Create a quiz')
    my_quizzes_btn = types.KeyboardButton('My quizzes')
    markup.add(create_btn, my_quizzes_btn)

    bot.reply_to(
        message,
        "Welcome to QuizBot! 📚\n\n"
        "Here you can create and share educational quizzes.\n\n"
        "Choose an option to begin:",
        reply_markup=markup
    )

# 'Create a quiz' handler
@bot.message_handler(func=lambda message: message.text == 'Create a quiz')
def start_quiz_creation(message):
    user_id = message.from_user.id
    user_states[user_id] = CREATE_STATES['AWAITING_NAME']
    temp_quiz_data[user_id] = {'questions': []}

    markup = types.ReplyKeyboardRemove()
    bot.reply_to(
        message,
        "Let's create your quiz! 🎯\n\n"
        "First, send me the name of your quiz.",
        reply_markup=markup
    )

# Process quiz name
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == CREATE_STATES['AWAITING_NAME'])
def process_quiz_name(message):
    user_id = message.from_user.id
    temp_quiz_data[user_id]['name'] = message.text
    user_states[user_id] = CREATE_STATES['AWAITING_DESCRIPTION']

    bot.reply_to(
        message,
        "Great! Now send me a description for your quiz (or send /skip if you don't want one)."
    )

# Process quiz description (or skip)
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == CREATE_STATES['AWAITING_DESCRIPTION'])
def process_quiz_description(message):
    user_id = message.from_user.id
    if message.text != '/skip':
        temp_quiz_data[user_id]['description'] = message.text
    else:
        temp_quiz_data[user_id]['description'] = None

    send_question_creation_prompt(message.chat.id)
    user_states[user_id] = CREATE_STATES['AWAITING_QUESTION']

# Helper: Prompt user to add questions
def send_question_creation_prompt(chat_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    create_btn = types.KeyboardButton('Create a question')
    done_btn = types.KeyboardButton('/done')
    markup.add(create_btn, done_btn)

    bot.send_message(
        chat_id,
        "Now let's add questions to your quiz!\n\n"
        "Press 'Create a question' to add a new question, or /done when finished.",
        reply_markup=markup
    )

# /done command handler (finish adding questions)
@bot.message_handler(commands=['done'])
def finish_questions(message):
    user_id = message.from_user.id

    # If we're not in quiz creation mode, ignore
    if user_id not in temp_quiz_data:
        return

    # If in the middle of adding options for a question, complete that question first
    if user_states.get(user_id) == CREATE_STATES['AWAITING_OPTIONS']:
        process_options_done(message)
        return

    # Ensure at least one question has been added
    if not temp_quiz_data[user_id].get('questions'):
        bot.reply_to(message, "Please add at least one question first!")
        return

    # Proceed to timer selection
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    times = ['10 seconds', '30 seconds', '1 minute', '2 minutes', '5 minutes']
    for t in times:
        markup.add(types.KeyboardButton(t))

    user_states[user_id] = CREATE_STATES['AWAITING_TIMER']
    bot.reply_to(
        message,
        "How long should users have to answer each question?",
        reply_markup=markup
    )

# Helper: Process options completion for a question
def process_options_done(message):
    user_id = message.from_user.id
    current_q = temp_quiz_data[user_id].get('current_question', {})
    options = current_q.get('options', [])

    if len(options) < 2:
        bot.reply_to(message, "Please add at least 2 options!")
        return

    # Show options for selecting the correct answer
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    for i, option in enumerate(options, 1):
        markup.add(types.KeyboardButton(f"{i}. {option}"))

    user_states[user_id] = CREATE_STATES['AWAITING_CORRECT_OPTION']
    bot.reply_to(
        message,
        "Select the correct answer by tapping on it:",
        reply_markup=markup
    )

# 'Create a question' handler
@bot.message_handler(func=lambda message: message.text == 'Create a question')
def start_question_creation(message):
    user_id = message.from_user.id
    if user_id not in temp_quiz_data:
        bot.reply_to(message, "Please start quiz creation first using the 'Create a quiz' button.")
        return

    user_states[user_id] = CREATE_STATES['AWAITING_QUESTION']
    markup = types.ReplyKeyboardRemove()
    bot.reply_to(
        message,
        "Send me the question text.\n\n"
        "You can also send a photo or video before the question if needed.",
        reply_markup=markup
    )

# Handler: Add media (photo or video) for a question
@bot.message_handler(content_types=['photo', 'video'],
                     func=lambda message: user_states.get(message.from_user.id) == CREATE_STATES['AWAITING_QUESTION'])
def handle_question_media(message):
    user_id = message.from_user.id
    media_type = 'photo' if message.photo else 'video'
    file_id = message.photo[-1].file_id if message.photo else message.video.file_id

    if 'current_question' not in temp_quiz_data[user_id]:
        temp_quiz_data[user_id]['current_question'] = {}

    temp_quiz_data[user_id]['current_question']['media'] = {
        'type': media_type,
        'file_id': file_id
    }

    bot.reply_to(message, "Media added! Now send me the question text.")

# Process question text
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == CREATE_STATES['AWAITING_QUESTION']
                     and message.content_type == 'text')
def process_question_text(message):
    user_id = message.from_user.id
    if 'current_question' not in temp_quiz_data[user_id]:
        temp_quiz_data[user_id]['current_question'] = {}

    temp_quiz_data[user_id]['current_question']['text'] = message.text
    user_states[user_id] = CREATE_STATES['AWAITING_OPTIONS']
    temp_quiz_data[user_id]['current_question']['options'] = []
    bot.reply_to(
        message,
        "Great! Now send me the answer options one by one.\n"
        "Send /done when you've added all options."
    )

# Process each answer option
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == CREATE_STATES['AWAITING_OPTIONS']
                     and not message.text.startswith('/'))
def process_option(message):
    user_id = message.from_user.id
    if 'current_question' not in temp_quiz_data[user_id]:
        return

    temp_quiz_data[user_id]['current_question']['options'].append(message.text)
    bot.reply_to(
        message,
        f"Option {len(temp_quiz_data[user_id]['current_question']['options'])} added.\n"
        "Send another option or /done if finished."
    )

# Process correct option selection
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == CREATE_STATES['AWAITING_CORRECT_OPTION'])
def process_correct_option(message):
    user_id = message.from_user.id
    try:
        selected = int(message.text.split('.')[0]) - 1
        options = temp_quiz_data[user_id]['current_question']['options']
        if 0 <= selected < len(options):
            temp_quiz_data[user_id]['current_question']['correct_option'] = selected
            user_states[user_id] = CREATE_STATES['AWAITING_EXPLANATION']

            markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            markup.add(types.KeyboardButton('/skip'))
            bot.reply_to(
                message,
                "Great! Now send an explanation for this question (or /skip if you don't want one).",
                reply_markup=markup
            )
        else:
            bot.reply_to(message, "Please select a valid option number.")
    except Exception:
        bot.reply_to(message, "Please select a valid option.")

# Process explanation (or skip) and finish the question
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == CREATE_STATES['AWAITING_EXPLANATION'])
def process_explanation(message):
    user_id = message.from_user.id
    current_q = temp_quiz_data[user_id]['current_question']

    question = Question(
        text=current_q['text'],
        options=current_q['options'],
        correct_option=current_q['correct_option'],
        explanation=None if message.text == '/skip' else message.text,
        media=current_q.get('media')
    )

    temp_quiz_data[user_id]['questions'].append(question)
    del temp_quiz_data[user_id]['current_question']
    send_question_creation_prompt(message.chat.id)
    user_states[user_id] = CREATE_STATES['AWAITING_QUESTION']

# Process timer selection
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == CREATE_STATES['AWAITING_TIMER'])
def process_timer(message):
    user_id = message.from_user.id
    time_map = {
        '10 seconds': 10,
        '30 seconds': 30,
        '1 minute': 60,
        '2 minutes': 120,
        '5 minutes': 300
    }

    if message.text not in time_map:
        bot.reply_to(message, "Please select a valid time option.")
        return

    temp_quiz_data[user_id]['timer'] = time_map[message.text]
    user_states[user_id] = CREATE_STATES['AWAITING_SHUFFLE_PREFERENCE']

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('Yes'), types.KeyboardButton('No'))
    bot.reply_to(
        message,
        "Would you like to shuffle questions and answer options?",
        reply_markup=markup
    )

# Process shuffle preference and finalize the quiz
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == CREATE_STATES['AWAITING_SHUFFLE_PREFERENCE'])
def process_shuffle_preference(message):
    user_id = message.from_user.id
    if message.text not in ['Yes', 'No']:
        bot.reply_to(message, "Please select Yes or No.")
        return

    shuffle = message.text == 'Yes'
    quiz_id = f"quiz_{user_id}_{int(time.time())}"

    # Create final Quiz object
    quiz = Quiz(
        name=temp_quiz_data[user_id]['name'],
        description=temp_quiz_data[user_id]['description'],
        questions=temp_quiz_data[user_id]['questions'],
        timer=temp_quiz_data[user_id]['timer'],
        shuffle_questions=shuffle,
        shuffle_options=shuffle,
        creator_id=user_id,
        quiz_id=quiz_id
    )

    quizzes[quiz_id] = quiz

    # Cleanup
    del temp_quiz_data[user_id]
    user_states[user_id] = CREATE_STATES['IDLE']

    # Create share and play buttons
    markup = types.InlineKeyboardMarkup(row_width=2)
    share_button = types.InlineKeyboardButton(
        "Share Quiz",
        url=f"https://t.me/share/url?url=https://t.me/your_bot_username?start={quiz_id}"
    )
    play_button = types.InlineKeyboardButton(
        "Play Quiz",
        callback_data=f"play_quiz:{quiz_id}"
    )
    markup.add(play_button, share_button)

    bot.reply_to(
        message,
        f"🎉 Your quiz '{quiz.name}' is ready!\n\n"
        f"Total questions: {len(quiz.questions)}\n"
        f"Time per question: {quiz.timer} seconds\n"
        f"Shuffling: {'enabled' if shuffle else 'disabled'}\n\n"
        "Share your quiz using the button below:",
        reply_markup=markup
    )

# ----------------- Playing Quizzes -----------------

# Callback handler: Start playing a quiz
@bot.callback_query_handler(func=lambda call: call.data.startswith('play_quiz:'))
def handle_play_quiz(call):
    quiz_id = call.data.split(':')[1]
    user_id = call.from_user.id

    if quiz_id not in quizzes:
        bot.answer_callback_query(call.id, "Quiz not found!")
        return

    quiz = quizzes[quiz_id]
    quiz_sessions[user_id] = {
        'quiz_id': quiz_id,
        'current_question': 0,
        'score': 0,
        'start_time': time.time()
    }

    send_quiz_question(user_id, call.message.chat.id)
    bot.answer_callback_query(call.id)

# Callback handler: Process an answer
@bot.callback_query_handler(func=lambda call: call.data.startswith('answer:'))
def handle_answer(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if user_id not in quiz_sessions:
        bot.answer_callback_query(call.id, "No active quiz session!")
        return

    session = quiz_sessions[user_id]
    quiz = quizzes[session['quiz_id']]
    current_q = quiz.questions[session['current_question']]

    try:
        selected_option = int(call.data.split(':')[1])
    except ValueError:
        bot.answer_callback_query(call.id, "Invalid answer format!")
        return

    is_correct = selected_option == current_q.correct_option
    if is_correct:
        session['score'] += 1
        response = "✅ Correct!"
    else:
        response = f"❌ Wrong! The correct answer was: {current_q.options[current_q.correct_option]}"

    if current_q.explanation:
        response += f"\n\n📝 Explanation: {current_q.explanation}"

    bot.answer_callback_query(call.id, "Answer recorded!")
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    bot.send_message(chat_id, response)

    session['current_question'] += 1
    if session['current_question'] < len(quiz.questions):
        send_quiz_question(user_id, chat_id)
    else:
        finish_quiz(user_id, chat_id)

# Send a quiz question to the user
def send_quiz_question(user_id, chat_id):
    session = quiz_sessions[user_id]
    quiz = quizzes[session['quiz_id']]
    question = quiz.questions[session['current_question']]

    message_text = f"Question {session['current_question'] + 1}/{len(quiz.questions)}\n\n"
    message_text += f"{question.text}\n\n"

    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, option in enumerate(question.options):
        button = types.InlineKeyboardButton(
            option,
            callback_data=f"answer:{i}"
        )
        markup.add(button)

    if question.media:
        if question.media['type'] == 'photo':
            bot.send_photo(chat_id, question.media['file_id'],
                           caption=message_text, reply_markup=markup)
        elif question.media['type'] == 'video':
            bot.send_video(chat_id, question.media['file_id'],
                           caption=message_text, reply_markup=markup)
    else:
        bot.send_message(chat_id, message_text, reply_markup=markup)

# Finish the quiz, show results, and store the attempt
def finish_quiz(user_id, chat_id):
    session = quiz_sessions[user_id]
    quiz = quizzes[session['quiz_id']]
    score_percent = (session['score'] / len(quiz.questions)) * 100
    time_taken = int(time.time() - session['start_time'])

    message = (
        f"🎯 Quiz Complete!\n\n"
        f"Quiz: {quiz.name}\n"
        f"Score: {session['score']}/{len(quiz.questions)} ({score_percent:.1f}%)\n"
        f"Time taken: {time_taken // 60}m {time_taken % 60}s\n\n"
    )

    if score_percent == 100:
        message += "🏆 Perfect score! Excellent work!"
    elif score_percent >= 80:
        message += "🌟 Great job!"
    elif score_percent >= 60:
        message += "👍 Good effort!"
    else:
        message += "📚 Keep practicing!"

    # Store this attempt in quiz_attempts
    attempt = {
        'user_id': user_id,
        'score': session['score'],
        'total': len(quiz.questions),
        'percentage': score_percent,
        'time_taken': time_taken,
        'timestamp': time.time()
    }
    if quiz.quiz_id not in quiz_attempts:
        quiz_attempts[quiz.quiz_id] = []
    quiz_attempts[quiz.quiz_id].append(attempt)

    # Add a retry button
    markup = types.InlineKeyboardMarkup()
    retry_button = types.InlineKeyboardButton(
        "Try Again",
        callback_data=f"play_quiz:{session['quiz_id']}"
    )
    markup.add(retry_button)

    bot.send_message(chat_id, message, reply_markup=markup)
    del quiz_sessions[user_id]

# ----------------- Viewing Quiz Results -----------------

# Handler for the "My quizzes" button.
@bot.message_handler(func=lambda message: message.text == 'My quizzes')
def show_my_quizzes(message):
    user_id = message.from_user.id
    # Filter quizzes created by this user.
    my_quizzes = [quiz for quiz in quizzes.values() if quiz.creator_id == user_id]
    if not my_quizzes:
        bot.reply_to(message, "You haven't created any quizzes yet!")
        return

    markup = types.InlineKeyboardMarkup()
    for quiz in my_quizzes:
        btn = types.InlineKeyboardButton(
            f"View Results for '{quiz.name}'",
            callback_data=f"view_results:{quiz.quiz_id}"
        )
        markup.add(btn)
    bot.reply_to(message, "Here are your quizzes:", reply_markup=markup)

# Callback handler for viewing quiz results.
@bot.callback_query_handler(func=lambda call: call.data.startswith('view_results:'))
def handle_view_results(call):
    print("DEBUG: handle_view_results called")  # Debug print
    quiz_id = call.data.split(':')[1]
    if quiz_id not in quizzes:
        bot.answer_callback_query(call.id, "Quiz not found!")
        return

    attempts = quiz_attempts.get(quiz_id, [])
    if not attempts:
        bot.answer_callback_query(call.id, "No attempts for this quiz yet!")
        bot.send_message(call.message.chat.id, "No one has attempted this quiz yet.")
        return

    message_text = f"Results for quiz '{quizzes[quiz_id].name}':\n\n"
    for attempt in attempts:
        timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(attempt['timestamp']))
        message_text += (f"User: {attempt['user_id']}\n"
                         f"Score: {attempt['score']}/{attempt['total']} ({attempt['percentage']:.1f}%)\n"
                         f"Time: {attempt['time_taken'] // 60}m {attempt['time_taken'] % 60}s\n"
                         f"At: {timestamp_str}\n\n")
    bot.send_message(call.message.chat.id, message_text)
    bot.answer_callback_query(call.id)

# ----------------- Start the Bot -----------------
if __name__ == '__main__':
    bot.infinity_polling()
