# api/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# User Schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    telegram_id: Optional[str] = Field(None, max_length=255)

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

# Question Schemas
class QuestionBase(BaseModel):
    question_type: str = Field(..., max_length=50)
    question_text: str
    correct_answer: str
    possible_answers: Optional[str] = None

class QuestionCreate(QuestionBase):
    quiz_id: int

class Question(QuestionBase):
    id: int
    quiz_id: int

    class Config:
        orm_mode = True

# Quiz Schemas
class QuizBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    author: str = Field(..., min_length=1, max_length=255)
    is_random: bool = False
    show_results_after_quiz: bool = True
    show_results_after_question: bool = True

class QuizCreate(QuizBase):
    pass

class QuizCreateWithQuestions(QuizBase):
    questions: List[QuestionCreate]

class Quiz(QuizBase):
    id: int
    created_at: datetime
    questions: List[Question] = []

    class Config:
        orm_mode = True

# Answer Schemas
class AnswerBase(BaseModel):
    question_id: int
    answer_text: str = Field(..., max_length=500)

class AnswerCreate(AnswerBase):
    pass

class Answer(AnswerBase):
    id: int
    attempt_id: int
    is_correct: bool
    answered_at: datetime

    class Config:
        orm_mode = True

# Quiz Attempt Schemas
class QuizAttemptBase(BaseModel):
    quiz_id: int
    user_id: int

class QuizAttemptCreate(QuizAttemptBase):
    pass

class QuizAttempt(QuizAttemptBase):
    id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    score: Optional[int] = None
    answers: List[Answer] = []

    class Config:
        orm_mode = True

# Response Schemas
class Message(BaseModel):
    detail: str

# Statistics Schemas
class UserStats(BaseModel):
    total_quizzes_created: int
    total_attempts: int
    completed_attempts: int
    average_score: float

class LeaderboardEntry(BaseModel):
    username: str
    score: int
    completed_at: datetime