from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from api.database import Base  # Update this import

class QuizModel(Base):
    __tablename__ = "quizzes"
    
    id = Column(Integer, primary_key=True, index=True)
    author = Column(String(255))
    is_random = Column(Boolean, default=False)
    show_results_after_quiz = Column(Boolean, default=True)
    show_results_after_question = Column(Boolean, default=True)

class QuestionModel(Base):
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    question_type = Column(String(50))
    question_text = Column(String(500))
    correct_answer = Column(String(500))
    possible_answers = Column(String(1000))