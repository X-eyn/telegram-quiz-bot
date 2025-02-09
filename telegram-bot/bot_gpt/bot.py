import logging
import json
import os
import csv
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Poll,
    KeyboardButton,
    KeyboardButtonPollType,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    PollAnswerHandler,
    filters,
    ContextTypes,
)

# -------------------------------
# Conversation States
# -------------------------------
# Quiz Creation states
CR_QUIZ_NAME = 1
CR_QUIZ_DESCRIPTION = 2
CR_PRE_QUESTION = 3
CR_ADD_QUESTION = 4
CR_NEXT_QUESTION = 5
CR_TIMER = 6
CR_SHUFFLE = 7
CR_SUBMIT = 8

# Quiz Taking states
TK_SELECT_QUIZ = 19
TK_TAKING_QUESTION = 20  # Not used in conversation handler; replaced by TK_WAIT_NEXT
TK_WAIT_NEXT = 21

# Import Conversation state
IMPORT_WAITING_FILE = 30

# -------------------------------
# File names for persistent storage
# -------------------------------
QUIZZES_FILE = "quizzes.json"
PARTICIPANTS_FILE = "quiz_participants.json"

# -------------------------------
# Default Quiz (used if no quiz has been created)
# -------------------------------
DEFAULT_QUIZ = {
    "quiz_name": "Default Sample Quiz",
    "quiz_description": "This is a default quiz. Create your own quiz using the bot!",
    "pre_question": "",
    "questions": [
        {
            "question": "What is the capital of France?",
            "options": ["Paris", "Rome", "Madrid", "Berlin"],
            "correct_option_id": 0,
            "explanation": "Paris is the capital of France.",
        },
        {
            "question": "What is 2 + 2?",
            "options": ["3", "4", "5"],
            "correct_option_id": 1,
            "explanation": "2 + 2 equals 4.",
        },
    ],
    "timer": 15,
    "shuffle": False,
    "submit": False,
}

# -------------------------------
# Helper functions for JSON storage
# -------------------------------
def load_quizzes():
    if os.path.exists(QUIZZES_FILE):
        with open(QUIZZES_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                else:
                    return []
            except json.JSONDecodeError:
                return []
    else:
        return []

def save_quiz_data(quiz):
    quizzes = load_quizzes()
    quizzes.append(quiz)
    with open(QUIZZES_FILE, "w", encoding="utf-8") as f:
        json.dump(quizzes, f, indent=2)

def save_poll_answer_data(data):
    if os.path.exists(PARTICIPANTS_FILE):
        with open(PARTICIPANTS_FILE, "r", encoding="utf-8") as f:
            try:
                all_data = json.load(f)
            except json.JSONDecodeError:
                all_data = []
    else:
        all_data = []
    all_data.append(data)
    with open(PARTICIPANTS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2)

# -------------------------------
# /start Command – Main Menu
# -------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Create Quiz", callback_data="create_quiz")],
        [InlineKeyboardButton("Take Quiz", callback_data="take_quiz")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(
            "Welcome to the Interactive Quiz Bot!\nPlease choose an option:",
            reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            "Welcome to the Interactive Quiz Bot!\nPlease choose an option:",
            reply_markup=reply_markup
        )

# -------------------------------
# QUIZ CREATION FLOW – Using Native Polls for Questions
# -------------------------------
async def cr_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data['questions'] = []
    await query.edit_message_text("Let's create your quiz!\n\nPlease enter the quiz name:")
    return CR_QUIZ_NAME

async def cr_quiz_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['quiz_name'] = update.message.text
    await update.message.reply_text("Enter a description for your quiz (or type /skip to skip):")
    return CR_QUIZ_DESCRIPTION

async def cr_quiz_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['quiz_description'] = update.message.text
    await update.message.reply_text("Send pre-question text or image (optional, or type /skip to skip):")
    return CR_PRE_QUESTION

async def cr_skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['quiz_description'] = ""
    await update.message.reply_text("No description added.\nSend pre-question text or image (optional, or type /skip to skip):")
    return CR_PRE_QUESTION

async def cr_pre_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Check if the message contains a photo; if so, store its file_id.
    if update.message.photo:
        context.user_data['pre_question'] = {"type": "photo", "file_id": update.message.photo[-1].file_id}
    else:
        context.user_data['pre_question'] = {"type": "text", "content": update.message.text}
    # Use KeyboardButtonPollType to let the user create a quiz-type poll.
    button = KeyboardButton("Create Quiz Question", request_poll=KeyboardButtonPollType(type="quiz"))
    markup = ReplyKeyboardMarkup([[button]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Now, create your first quiz question by pressing the button below:",
        reply_markup=markup,
    )
    return CR_ADD_QUESTION

async def cr_skip_pre_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['pre_question'] = None
    button = KeyboardButton("Create Quiz Question", request_poll=KeyboardButtonPollType(type="quiz"))
    markup = ReplyKeyboardMarkup([[button]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "No pre-question media/text added.\nNow, create your first quiz question by pressing the button below:",
        reply_markup=markup,
    )
    return CR_ADD_QUESTION

async def handle_created_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    poll = update.message.poll
    if poll is None:
        return CR_ADD_QUESTION
    if poll.type != "quiz":
        await update.message.reply_text("Please create a quiz-type poll.")
        return CR_ADD_QUESTION
    question_data = {
        "question": poll.question,
        "options": [option.text for option in poll.options],
        "correct_option_id": poll.correct_option_id,
        "explanation": poll.explanation or "",
    }
    context.user_data.setdefault('questions', []).append(question_data)
    keyboard = [
        [InlineKeyboardButton("Add another question", callback_data="add_another")],
        [InlineKeyboardButton("Finish questions", callback_data="finish_questions")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Question added! What would you like to do next?", reply_markup=reply_markup)
    return CR_NEXT_QUESTION

async def cr_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "add_another":
        button = KeyboardButton("Create Quiz Question", request_poll=KeyboardButtonPollType(type="quiz"))
        markup = ReplyKeyboardMarkup([[button]], one_time_keyboard=True, resize_keyboard=True)
        await query.edit_message_text("Send your next quiz question by pressing the button below:")
        await query.message.reply_text("Press the button below to create a new quiz question:", reply_markup=markup)
        return CR_ADD_QUESTION
    elif query.data == "finish_questions":
        await query.edit_message_text("Enter the timer duration (in seconds) for each question:")
        return CR_TIMER

async def cr_finish_questions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('questions'):
        await update.message.reply_text("You haven't added any questions yet. Please add at least one question using the poll button.")
        return CR_ADD_QUESTION
    await update.message.reply_text("Enter the timer duration (in seconds) for each question:")
    return CR_TIMER

async def cr_set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data['timer'] = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Please enter a valid number for the timer (in seconds):")
        return CR_TIMER
    keyboard = [
        [InlineKeyboardButton("Yes", callback_data="shuffle_yes"),
         InlineKeyboardButton("No", callback_data="shuffle_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Do you want to shuffle questions and answer options?", reply_markup=reply_markup)
    return CR_SHUFFLE

async def cr_set_shuffle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['shuffle'] = (query.data == "shuffle_yes")
    keyboard = [
        [InlineKeyboardButton("Yes", callback_data="submit_yes"),
         InlineKeyboardButton("No", callback_data="submit_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Would you like to submit your quiz to the contest?", reply_markup=reply_markup)
    return CR_SUBMIT

async def cr_set_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['submit'] = (query.data == "submit_yes")
    quiz = {
        "quiz_name": context.user_data.get('quiz_name', 'Untitled Quiz'),
        "quiz_description": context.user_data.get('quiz_description', ''),
        "pre_question": context.user_data.get('pre_question', None),
        "questions": context.user_data.get('questions', []),
        "timer": context.user_data.get('timer', 15),
        "shuffle": context.user_data.get('shuffle', False),
        "submit": context.user_data.get('submit', False)
    }
    summary = (
        f"Quiz Created!\n\n"
        f"Title: {quiz['quiz_name']}\n"
        f"Description: {quiz['quiz_description']}\n"
        f"Pre-question: {quiz['pre_question']}\n"
        f"Number of questions: {len(quiz['questions'])}\n"
        f"Timer: {quiz['timer']} seconds\n"
        f"Shuffle: {'Yes' if quiz['shuffle'] else 'No'}\n"
        f"Submitted to contest: {'Yes' if quiz['submit'] else 'No'}"
    )
    await query.edit_message_text(summary)
    save_quiz_data(quiz)
    await query.message.reply_text("Your quiz has been created! You can take it by selecting 'Take Quiz' from the main menu.")
    return ConversationHandler.END

async def cr_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Quiz creation cancelled.")
    return ConversationHandler.END

# -------------------------------
# IMPORT QUIZZES – Import from JSON/CSV/XLSX
# -------------------------------
async def import_quizzes_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Please send a document file (JSON, CSV, or XLSX) containing quiz data to import.")
    return IMPORT_WAITING_FILE

async def import_quizzes_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    document = update.message.document
    if not document:
        await update.message.reply_text("No document received. Please send a valid document file.")
        return IMPORT_WAITING_FILE
    file_name = document.file_name.lower() if document.file_name else ""
    file = await document.get_file()
    temp_path = f"temp_{file_name}"
    await file.download_to_drive(temp_path)
    imported_quizzes = []
    try:
        if file_name.endswith(".json"):
            with open(temp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    imported_quizzes = data
                else:
                    imported_quizzes = [data]
        elif file_name.endswith(".csv"):
            with open(temp_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                quizzes_dict = {}
                for row in reader:
                    quiz_name = row.get("quiz_name", "Untitled Quiz")
                    if quiz_name not in quizzes_dict:
                        quizzes_dict[quiz_name] = {
                            "quiz_name": quiz_name,
                            "quiz_description": row.get("quiz_description", ""),
                            "pre_question": row.get("pre_question", ""),
                            "questions": [],
                            "timer": int(row.get("timer", 15)),
                            "shuffle": row.get("shuffle", "False") == "True",
                            "submit": row.get("submit", "False") == "True"
                        }
                    question = {
                        "question": row.get("question", ""),
                        "options": row.get("options", "").split(";"),
                        "correct_option_id": int(row.get("correct_option_id", 0)),
                        "explanation": row.get("explanation", "")
                    }
                    quizzes_dict[quiz_name]["questions"].append(question)
                imported_quizzes = list(quizzes_dict.values())
        elif file_name.endswith(".xlsx"):
            from openpyxl import load_workbook
            wb = load_workbook(filename=temp_path)
            ws = wb.active
            headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
            quizzes_dict = {}
            for row in ws.iter_rows(min_row=2, values_only=True):
                row_dict = dict(zip(headers, row))
                quiz_name = row_dict.get("quiz_name", "Untitled Quiz")
                if quiz_name not in quizzes_dict:
                    quizzes_dict[quiz_name] = {
                        "quiz_name": quiz_name,
                        "quiz_description": row_dict.get("quiz_description", ""),
                        "pre_question": row_dict.get("pre_question", ""),
                        "questions": [],
                        "timer": int(row_dict.get("timer", 15)) if row_dict.get("timer") else 15,
                        "shuffle": str(row_dict.get("shuffle", "False")) == "True",
                        "submit": str(row_dict.get("submit", "False")) == "True"
                    }
                question = {
                    "question": row_dict.get("question", ""),
                    "options": row_dict.get("options", "").split(";") if row_dict.get("options") else [],
                    "correct_option_id": int(row_dict.get("correct_option_id", 0)),
                    "explanation": row_dict.get("explanation", "")
                }
                quizzes_dict[quiz_name]["questions"].append(question)
            imported_quizzes = list(quizzes_dict.values())
        else:
            await update.message.reply_text("Unsupported file type. Please send a JSON, CSV, or XLSX file.")
            os.remove(temp_path)
            return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"Error processing file: {e}")
        os.remove(temp_path)
        return ConversationHandler.END
    os.remove(temp_path)
    existing_quizzes = load_quizzes()
    existing_quizzes.extend(imported_quizzes)
    with open(QUIZZES_FILE, "w", encoding="utf-8") as f:
        json.dump(existing_quizzes, f, indent=2)
    await update.message.reply_text(f"Successfully imported {len(imported_quizzes)} quizzes!")
    return ConversationHandler.END

async def import_quizzes_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Import cancelled.")
    return ConversationHandler.END

# -------------------------------
# EXPORT QUIZZES – Export quizzes to JSON, CSV, and XLSX
# -------------------------------
async def export_quizzes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    quizzes = load_quizzes()
    if not quizzes:
        await update.message.reply_text("No quizzes found to export.")
        return

    # The JSON file already exists (QUIZZES_FILE)
    json_file = QUIZZES_FILE

    # Export to CSV
    csv_file = "quizzes_export.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["quiz_name", "quiz_description", "pre_question", "question", "options", "correct_option_id", "explanation", "timer", "shuffle", "submit"])
        for quiz in quizzes:
            pre_question = ""
            if isinstance(quiz.get("pre_question"), dict):
                if quiz["pre_question"].get("type") == "text":
                    pre_question = quiz["pre_question"].get("content", "")
                elif quiz["pre_question"].get("type") == "photo":
                    pre_question = "[PHOTO]"
            else:
                pre_question = quiz.get("pre_question", "")
            for question in quiz.get("questions", []):
                writer.writerow([
                    quiz.get("quiz_name", ""),
                    quiz.get("quiz_description", ""),
                    pre_question,
                    question.get("question", ""),
                    ";".join(question.get("options", [])),
                    question.get("correct_option_id", 0),
                    question.get("explanation", ""),
                    quiz.get("timer", 15),
                    quiz.get("shuffle", False),
                    quiz.get("submit", False)
                ])
    # Export to XLSX
    xlsx_file = "quizzes_export.xlsx"
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["quiz_name", "quiz_description", "pre_question", "question", "options", "correct_option_id", "explanation", "timer", "shuffle", "submit"])
        for quiz in quizzes:
            pre_question = ""
            if isinstance(quiz.get("pre_question"), dict):
                if quiz["pre_question"].get("type") == "text":
                    pre_question = quiz["pre_question"].get("content", "")
                elif quiz["pre_question"].get("type") == "photo":
                    pre_question = "[PHOTO]"
            else:
                pre_question = quiz.get("pre_question", "")
            for question in quiz.get("questions", []):
                ws.append([
                    quiz.get("quiz_name", ""),
                    quiz.get("quiz_description", ""),
                    pre_question,
                    question.get("question", ""),
                    ";".join(question.get("options", [])),
                    question.get("correct_option_id", 0),
                    question.get("explanation", ""),
                    quiz.get("timer", 15),
                    quiz.get("shuffle", False),
                    quiz.get("submit", False)
                ])
        wb.save(xlsx_file)
    except ImportError:
        xlsx_file = None

    chat_id = update.effective_chat.id
    if os.path.exists(json_file):
        await context.bot.send_document(chat_id=chat_id, document=open(json_file, "rb"), filename=json_file)
    if os.path.exists(csv_file):
        await context.bot.send_document(chat_id=chat_id, document=open(csv_file, "rb"), filename=csv_file)
    if xlsx_file and os.path.exists(xlsx_file):
        await context.bot.send_document(chat_id=chat_id, document=open(xlsx_file, "rb"), filename=xlsx_file)

    if os.path.exists(csv_file):
        os.remove(csv_file)
    if xlsx_file and os.path.exists(xlsx_file):
        os.remove(xlsx_file)

# -------------------------------
# QUIZ TAKING FLOW – Using Native Quiz Polls with Timer and Pre-question Display
# -------------------------------
async def tk_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    quizzes = load_quizzes()
    if not quizzes:
        quiz = DEFAULT_QUIZ
        context.user_data['quiz'] = quiz
        context.user_data['question_index'] = 0
        context.user_data['score'] = 0
        await query.edit_message_text(f"Starting quiz: {quiz['quiz_name']}\n{quiz['quiz_description']}")
        return await tk_send_poll(update, context)
    else:
        keyboard = []
        for idx, quiz in enumerate(quizzes):
            if isinstance(quiz, dict):
                quiz_name = quiz.get("quiz_name", "Untitled Quiz")
            else:
                quiz_name = str(quiz)
            keyboard.append([InlineKeyboardButton(quiz_name, callback_data=f"select_quiz_{idx}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Select a quiz to take:", reply_markup=reply_markup)
        return TK_SELECT_QUIZ

async def tk_select_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    idx = int(data.split("_")[-1])
    quizzes = load_quizzes()
    if idx < len(quizzes):
        quiz = quizzes[idx]
    else:
        quiz = DEFAULT_QUIZ
    context.user_data['quiz'] = quiz
    context.user_data['question_index'] = 0
    context.user_data['score'] = 0
    pre_question = quiz.get("pre_question")
    chat_id = query.message.chat_id
    if pre_question:
        if isinstance(pre_question, dict) and pre_question.get("type") == "photo":
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=pre_question["file_id"],
                caption="Context for the quiz:"
            )
        elif isinstance(pre_question, dict) and pre_question.get("type") == "text":
            await context.bot.send_message(
                chat_id=chat_id,
                text=pre_question.get("content", "")
            )
        elif isinstance(pre_question, str):
            await context.bot.send_message(chat_id=chat_id, text=pre_question)
    await query.edit_message_text(f"Starting quiz: {quiz['quiz_name']}\n{quiz['quiz_description']}")
    return await tk_send_poll(update, context)

async def tk_send_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    quiz = context.user_data['quiz']
    index = context.user_data['question_index']
    if index < len(quiz['questions']):
        question = quiz['questions'][index]
        poll_message = await update.effective_chat.send_poll(
            question=question['question'],
            options=question['options'],
            type=Poll.QUIZ,
            correct_option_id=question['correct_option_id'],
            explanation=question.get('explanation', ''),
            is_anonymous=False,
            open_period=quiz.get('timer', 15)
        )
        context.user_data['current_poll_id'] = poll_message.poll.id
        # Return TK_WAIT_NEXT so that the "Next" button callback is correctly caught.
        return TK_WAIT_NEXT
    else:
        score = context.user_data['score']
        total = len(quiz['questions'])
        await update.effective_chat.send_message(
            text=f"Quiz finished!\nYour score: {score}/{total}\nType /start to return to the main menu."
        )
        return ConversationHandler.END

async def tk_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['question_index'] += 1
    return await tk_send_poll(update, context)

async def tk_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Quiz cancelled. Use /start to return to the main menu.")
    return ConversationHandler.END

# -------------------------------
# Global PollAnswer Handler – Save Participant Data and Provide Feedback
# -------------------------------
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    poll_answer = update.poll_answer
    user_id = poll_answer.user.id
    if 'quiz' not in context.user_data:
        return
    if context.user_data.get('current_poll_id') != poll_answer.poll_id:
        return
    if not poll_answer.option_ids:
        return
    selected = poll_answer.option_ids[0]
    quiz = context.user_data['quiz']
    index = context.user_data['question_index']
    question = quiz['questions'][index]
    if selected == question['correct_option_id']:
        context.user_data['score'] += 1
        feedback = "Correct!"
    else:
        correct_option = question['options'][question['correct_option_id']]
        feedback = f"Incorrect. The correct answer was: {correct_option}"
    if question.get('explanation'):
        feedback += f"\nExplanation: {question['explanation']}"
    answer_data = {
        "user_id": poll_answer.user.id,
        "username": poll_answer.user.username,
        "poll_id": poll_answer.poll_id,
        "selected_option": selected,
        "question": question['question'],
        "correct_option": question['options'][question['correct_option_id']],
        "timestamp": datetime.utcnow().isoformat()
    }
    save_poll_answer_data(answer_data)
    keyboard = [[InlineKeyboardButton("Next", callback_data="next_question")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=feedback, reply_markup=reply_markup)
    context.user_data['current_poll_id'] = None

# -------------------------------
# MAIN: Set Up Handlers and Run the Bot
# -------------------------------
def main():
    TOKEN = "7699629853:AAHwJfx-IOBtndlnrTyzJ9G3YKKp-367BhU"  # Replace with your actual bot token
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("export_quizzes", export_quizzes_handler))
    app.add_handler(CommandHandler("import_quizzes", import_quizzes_start))

    import_conversation = ConversationHandler(
        entry_points=[CommandHandler("import_quizzes", import_quizzes_start)],
        states={
            IMPORT_WAITING_FILE: [MessageHandler(filters.Document.ALL, import_quizzes_file)]
        },
        fallbacks=[CommandHandler("cancel", import_quizzes_cancel)],
        allow_reentry=True,
    )
    app.add_handler(import_conversation)

    quiz_creation_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cr_entry, pattern="^create_quiz$")],
        states={
            CR_QUIZ_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, cr_quiz_name)],
            CR_QUIZ_DESCRIPTION: [
                CommandHandler("skip", cr_skip_description),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cr_quiz_description),
            ],
            CR_PRE_QUESTION: [
                CommandHandler("skip", cr_skip_pre_question),
                MessageHandler(filters.TEXT | filters.PHOTO, cr_pre_question),
            ],
            CR_ADD_QUESTION: [
                MessageHandler(filters.POLL, handle_created_poll),
                CommandHandler("done", cr_finish_questions),
            ],
            CR_NEXT_QUESTION: [CallbackQueryHandler(cr_next_question, pattern="^(add_another|finish_questions)$")],
            CR_TIMER: [MessageHandler(filters.TEXT & ~filters.COMMAND, cr_set_timer)],
            CR_SHUFFLE: [CallbackQueryHandler(cr_set_shuffle, pattern="^shuffle_")],
            CR_SUBMIT: [CallbackQueryHandler(cr_set_submit, pattern="^submit_")],
        },
        fallbacks=[CommandHandler("cancel", cr_cancel)],
        allow_reentry=True,
    )
    app.add_handler(quiz_creation_conv)

    quiz_taking_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(tk_entry, pattern="^take_quiz$")],
        states={
            TK_SELECT_QUIZ: [CallbackQueryHandler(tk_select_quiz, pattern="^select_quiz_\\d+$")],
            TK_WAIT_NEXT: [CallbackQueryHandler(tk_next_question, pattern="^next_question$")],
        },
        fallbacks=[CommandHandler("cancel", tk_cancel)],
        allow_reentry=True,
    )
    app.add_handler(quiz_taking_conv)

    app.add_handler(PollAnswerHandler(handle_poll_answer))

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )
    logger = logging.getLogger(__name__)
    logger.info("Interactive Quiz Bot is running...")

    app.run_polling()

if __name__ == "__main__":
    main()
