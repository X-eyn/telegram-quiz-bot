from pydantic import BaseModel
from typing import List, Optional

class QuestionBase(BaseModel):
    question_type: str
    question_text: str
    correct_answer: str
    possible_answers: Optional[str] = None

class QuizBase(BaseModel):
    author: str
    is_random: bool = False
    show_results_after_quiz: bool = True
    show_results_after_question: bool = True