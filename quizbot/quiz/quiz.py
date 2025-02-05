"""
With this module, you can create quizzes with questions of different kinds.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from quizbot.quiz.question_factory import (
    Question, QuestionString, QuestionNumber, 
    QuestionBool, QuestionChoice, QuestionChoiceSingle
)
from typing import List
import json
from dotenv import load_dotenv

load_dotenv()

# MySQL Connection
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+mysqlconnector://root@localhost/quizbot")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Quiz:
    """
    An Instance of the class Quiz has a list of questions, which defines the Quiz.
    You can choose whether
        - the order of the questions is random
        - the result of the entered answer is shown after the question
        - the result of the entered answer of every question is shown after the quiz
    """

    def __init__(self, author="", name="") -> None:
        """
        Initializes an instance of the class Quiz.
        :param author: Author of the quiz
        :param name: Name of the quiz
        """
        self.questions: List[Question] = []
        self.is_random = False
        self.author = author
        self.name = name
        self.show_results_after_quiz = True
        self.show_results_after_question = True

    def add_question(self, new_question: Question):
        """
        Add an instance of the class Question to the list of questions.
        :param new_question: New question of the quiz.
        """
        self.questions.append(new_question)

    def get_questions(self):
        """
        Returns a copy of the list of questions.
        :returns: List of questions.
        """
        return self.questions.copy()

    def save_to_db(self):
        """Save quiz to MySQL database"""
        db = SessionLocal()
        try:
            # First insert/update the quiz
            quiz_data = {
                "name": self.name,
                "author": self.author,
                "is_random": self.is_random,
                "show_results_after_quiz": self.show_results_after_quiz,
                "show_results_after_question": self.show_results_after_question
            }
            
            # Insert quiz and get its ID
            result = db.execute(
                """INSERT INTO quizzes 
                   (name, author, is_random, show_results_after_quiz, show_results_after_question)
                   VALUES (:name, :author, :is_random, :show_results_after_quiz, 
                          :show_results_after_question)
                   ON DUPLICATE KEY UPDATE
                   author=:author, is_random=:is_random,
                   show_results_after_quiz=:show_results_after_quiz,
                   show_results_after_question=:show_results_after_question""",
                quiz_data
            )
            db.commit()
            
            # Get quiz ID
            quiz_id = db.execute(
                "SELECT id FROM quizzes WHERE name = :name",
                {"name": self.name}
            ).scalar()
            
            # Delete old questions
            db.execute("DELETE FROM questions WHERE quiz_id = :quiz_id", {"quiz_id": quiz_id})
            
            # Insert new questions
            for q in self.questions:
                question_data = {
                    "quiz_id": quiz_id,
                    "question_type": q.__class__.__name__,
                    "question_text": q.question,
                    "correct_answer": q.correct_answer,
                    "possible_answers": json.dumps(q.possible_answers) if hasattr(q, 'possible_answers') else None
                }
                db.execute(
                    """INSERT INTO questions 
                       (quiz_id, question_type, question_text, correct_answer, possible_answers)
                       VALUES (:quiz_id, :question_type, :question_text, :correct_answer, 
                              :possible_answers)""",
                    question_data
                )
            
            db.commit()
        finally:
            db.close()

    @staticmethod
    def load_from_db(name: str, author: str = None):
        """
        Load quiz from MySQL database
        :param name: Name of the quiz to load
        :param author: Optional author of the quiz
        :returns: Quiz object or None if not found
        """
        db = SessionLocal()
        try:
            # First get the quiz
            query = """
                SELECT q.*, qq.question_type, qq.question_text, 
                       qq.correct_answer, qq.possible_answers 
                FROM quizzes q
                LEFT JOIN questions qq ON q.id = qq.quiz_id
                WHERE q.name = :name
            """
            params = {"name": name}
            if author:
                query += " AND q.author = :author"
                params["author"] = author

            result = db.execute(query, params).fetchall()
            
            if not result:
                return None

            # Create quiz instance from first row
            quiz = Quiz(author=result[0].author, name=result[0].name)
            quiz.is_random = result[0].is_random
            quiz.show_results_after_quiz = result[0].show_results_after_quiz
            quiz.show_results_after_question = result[0].show_results_after_question

            # Add each question
            for row in result:
                if row.question_text:  # Skip if no question (in case of LEFT JOIN)
                    if row.question_type == "QuestionString":
                        question = QuestionString(row.question_text, row.correct_answer)
                    elif row.question_type == "QuestionNumber":
                        question = QuestionNumber(row.question_text, row.correct_answer)
                    elif row.question_type == "QuestionBool":
                        question = QuestionBool(row.question_text, row.correct_answer)
                    elif row.question_type == "QuestionChoice":
                        question = QuestionChoice(row.question_text, row.correct_answer)
                        if row.possible_answers:
                            question.possible_answers = json.loads(row.possible_answers)
                    elif row.question_type == "QuestionChoiceSingle":
                        question = QuestionChoiceSingle(row.question_text, row.correct_answer)
                        if row.possible_answers:
                            question.possible_answers = json.loads(row.possible_answers)
                    quiz.add_question(question)

            return quiz
        finally:
            db.close()

    @staticmethod
    def list_quizzes(author: str = None):
        """
        List all available quizzes
        :param author: Optional author to filter quizzes
        :returns: List of quiz names and authors
        """
        db = SessionLocal()
        try:
            query = "SELECT name, author FROM quizzes"
            if author:
                query += " WHERE author = :author"
                result = db.execute(query, {"author": author}).fetchall()
            else:
                result = db.execute(query).fetchall()
            return result
        finally:
            db.close()