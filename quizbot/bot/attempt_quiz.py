"""
Module with methods to attempt to a quiz with a telegram bot
"""
# quizbot/bot/attempt_quiz.py
import logging
import random
from telegram.ext import ConversationHandler
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, ChatAction
from quizbot.quiz.question_factory import (
    QuestionBool, QuestionChoice, QuestionChoiceSingle,
    QuestionNumber, QuestionString
)
from quizbot.quiz.attempt import Attempt
from quizbot.quiz.quiz import Quiz

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Dict to store user data like an attempt instance
userDict = dict()


def start(update, _):
    """Start the attempt conversation"""
    user = update.message.from_user
    username = user.username or f"user_{user.id}"
    logger.info('[%s] Attempt initialized', username)

    if user.id in userDict:
        logger.info('[%s] Attempt canceled because user is in middle of quiz.', username)
        update.message.reply_text(
            "You're in the middle of a quiz. You can't attempt a second one 😁\n"
            'If you want to cancel your attempt, enter /cancelAttempt.'
        )
        return ConversationHandler.END

    update.message.reply_text(
        'Hi 😃 Which quiz would you like to attempt?\n'
        'Please enter the quiz name. '
        'If the quiz wasn\'t created by you, add the creator\'s username after the quiz name.'
    )
    return 'ENTER_QUIZ'

def cancel(update, _):
    """
    Cancels an attempt to a quiz by deleting the users' entries.
    """
    logger.info('[%s] Attempt canceled by user',
                update.message.from_user.username)

    # Remove all user data
    userDict.pop(update.message.from_user.id)
    update.message.reply_text(
        "I canceled you attempt. See you next time. 🙋‍♂️")
    return ConversationHandler.END


def enter_quiz(update, context):
    """Handle quiz name entry"""
    user = update.message.from_user
    username = user.username or f"user_{user.id}"
    quiz_input = update.message.text.split()
    
    # Get quiz name and optional creator
    quiz_name = quiz_input[0]
    quiz_creator = quiz_input[1] if len(quiz_input) > 1 else None
    
    logger.info('[%s] Quiz "%s" entered', username, quiz_name)

    # Bot is typing during database query
    context.bot.send_chat_action(
        chat_id=update.effective_message.chat_id,
        action=ChatAction.TYPING
    )

    try:
        # Try to load quiz from database
        quiz = Quiz.load_from_db(quiz_name, quiz_creator)
        
        if not quiz:
            update.message.reply_text(
                f"Sorry, I couldn't find the quiz '{quiz_name}' 😕 Please try again."
            )
            logger.info('[%s] Couldn\'t find Quiz %s', username, quiz_name)
            return 'ENTER_QUIZ'

        logger.info('[%s] Found Quiz %s', username, quiz_name)
        userDict[user.id] = Attempt(quiz)
        
        update.message.reply_text(
            f"Let's go! 🙌 Have fun with the quiz '{quiz_name}'!\n"
            "You can cancel your participation with /cancelAttempt."
        )

        # Ask first question
        ask_question(update)
        return 'ENTER_ANSWER'

    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        update.message.reply_text(
            "Sorry, there was an error accessing the quiz. Please try again."
        )
        return 'ENTER_QUIZ'

def enter_answer(update, _):
    """
    It processes the answer to a question and asks a new question, if possible.
    Otherwise, it prints results.
    """

    user_id = update.message.from_user.id
    user_message = update.message.text
    act_question = userDict[user_id].act_question()

    # If the current question is a multiple-choice question,
    # the bot has to wait for "Enter" to enter the answer.
    if type(act_question) is QuestionChoice and user_message != 'Enter':
        # the current question is a multiple-choice question and not ready to enter

        logger.info('[%s]Insert Answer "%s", Looking for additional answers',
                    update.message.from_user.username, user_message)

        # add answer to list of users' answers
        # TODO What if user answer isnt in possible messages
        userDict[user_id].input_answer(user_message)
        # wait for next answer
        return 'ENTER_ANSWER'
    elif not type(act_question) is QuestionChoice:

        logger.info('[%s] Insert Answer "%s"',
                    update.message.from_user.username, user_message)

        # add answer to list of users' answers
        userDict[user_id].input_answer(user_message)

    # enter the answer of user
    try:
        is_correct, correct_answer = userDict[user_id].enter_answer()
    except AssertionError:
        userDict[user_id].user_answers.clear()
        logger.info("[%s] Something went wrong by entering the answer.",
                    update.message.from_user.username)
        update.message.reply_text(
            "Sorry 😕 Something went wrong by entering your answer. Please try again.")
        return 'ENTER_ANSWER'

    logger.info('[%s] Entered Answer', update.message.from_user.username)

    if userDict[user_id].quiz.show_results_after_question:
        # If creator of the quiz wants the user to see him/her results after the question
        if is_correct:
            update.message.reply_text("Thats correct 😁")
        else:
            update.message.reply_text(
                "Sorry, thats not correct. 😕\nThe correct answer is: {}".format(correct_answer))

    if userDict[user_id].has_next_question():
        # check for next question
        ask_question(update)
        return 'ENTER_ANSWER'

    # no question left
    update.message.reply_text(
        "Thanks for your participation! ☺️", reply_markup=ReplyKeyboardRemove())
    if userDict[user_id].quiz.show_results_after_quiz:
        # If creator of the quiz wants the user to see him/her results after the quiz
        count = 1
        for is_correct, question in userDict[user_id].user_points:
            update.message.reply_text(
                "Question {}:\n".format(count)
                + question.question + "\n"
                "Your answer was " +
                ("correct 😁" if is_correct else "wrong. 😕\nThe correct answer is: {}".format(
                    question.correct_answer)),
                reply_markup=ReplyKeyboardRemove())
            count = count + 1

    # Deletes the users entries to closes the attempt
    del userDict[update.message.from_user.id]
    logger.info('[%s] Quitting Quiz', update.message.from_user.username)
    return ConversationHandler.END


def ask_question(update):
    """
    Formats the keyboard and prints the current question.
    """
    user_id = update.message.from_user.id
    act_question = userDict[user_id].act_question()

    if isinstance(act_question, (QuestionString, QuestionNumber)):
        # String or number question: Use normal Keyboard
        reply_markup = ReplyKeyboardRemove()
    elif isinstance(act_question, QuestionBool):
        # Bool question: Choose between true and false button
        reply_markup = ReplyKeyboardMarkup(
            [['True', 'False']], one_time_keyboard=True)
    elif isinstance(act_question, QuestionChoiceSingle):
        # Single choice question: Choose between possible answers buttons
        list_of_answers = [[el] for el in act_question.possible_answers]
        if act_question.is_random:
            # Shuffle if necessary
            random.shuffle(list_of_answers)
        reply_markup = ReplyKeyboardMarkup(
            list_of_answers, one_time_keyboard=True)
    else:
        # Single choice question: Choose between possible answers buttons
        list_of_answers = [[el] for el in act_question.possible_answers]
        if act_question.is_random:
            # Shuffle if necessary
            random.shuffle(list_of_answers)
        # add termination button
        list_of_answers.append(['Enter'])
        reply_markup = ReplyKeyboardMarkup(
            list_of_answers, one_time_keyboard=False)

    # print question
    update.message.reply_text(
        act_question.question,
        reply_markup=reply_markup
    )

    logger.info('[%s] Printed new question', update.message.from_user.username)
