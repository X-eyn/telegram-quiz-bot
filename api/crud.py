# api/crud.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models, schemas
from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException

# User operations
def get_user(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    db_user = models.User(**user.dict())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Quiz operations
def get_quiz(db: Session, quiz_id: int) -> Optional[models.Quiz]:
    return db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()

def get_quiz_by_name_and_author(db: Session, name: str, author: str) -> Optional[models.Quiz]:
    return db.query(models.Quiz).filter(
        models.Quiz.name == name,
        models.Quiz.author == author
    ).first()

def create_quiz(db: Session, quiz: schemas.QuizCreateWithQuestions) -> models.Quiz:
    # Create quiz
    db_quiz = models.Quiz(**quiz.dict(exclude={'questions'}))
    db.add(db_quiz)
    db.commit()
    db.refresh(db_quiz)
    
    # Add questions
    if quiz.questions:
        for q in quiz.questions:
            db_question = models.Question(
                quiz_id=db_quiz.id,
                **q.dict(exclude={'quiz_id'})
            )
            db.add(db_question)
    
    db.commit()
    db.refresh(db_quiz)
    return db_quiz

def get_user_quizzes(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[models.Quiz]:
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return db.query(models.Quiz).filter(
        models.Quiz.author == user.username
    ).offset(skip).limit(limit).all()

# Question operations
def create_question(db: Session, question: schemas.QuestionCreate) -> models.Question:
    db_question = models.Question(**question.dict())
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question

# Quiz attempt operations
def create_attempt(db: Session, attempt: schemas.QuizAttemptCreate) -> models.QuizAttempt:
    db_attempt = models.QuizAttempt(**attempt.dict())
    db.add(db_attempt)
    db.commit()
    db.refresh(db_attempt)
    return db_attempt

def submit_answer(
    db: Session, 
    attempt_id: int, 
    answer: schemas.AnswerCreate
) -> models.Answer:
    # Get question
    question = db.query(models.Question).filter(
        models.Question.id == answer.question_id
    ).first()
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Check answer
    is_correct = False
    if question.question_type in ["QuestionChoice", "QuestionChoiceSingle"]:
        correct_answers = set(a.strip() for a in question.correct_answer.split(','))
        user_answers = set(a.strip() for a in answer.answer_text.split(','))
        is_correct = correct_answers == user_answers
    else:
        is_correct = answer.answer_text.strip() == question.correct_answer.strip()
    
    # Create answer record
    db_answer = models.Answer(
        attempt_id=attempt_id,
        question_id=answer.question_id,
        answer_text=answer.answer_text,
        is_correct=is_correct
    )
    
    db.add(db_answer)
    db.commit()
    db.refresh(db_answer)
    return db_answer

def complete_attempt(db: Session, attempt_id: int) -> models.QuizAttempt:
    attempt = db.query(models.QuizAttempt).filter(
        models.QuizAttempt.id == attempt_id
    ).first()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    
    if attempt.completed_at:
        raise HTTPException(status_code=400, detail="Attempt already completed")
    
    # Calculate score
    total_questions = db.query(models.Question).filter(
        models.Question.quiz_id == attempt.quiz_id
    ).count()
    
    correct_answers = db.query(models.Answer).filter(
        models.Answer.attempt_id == attempt_id,
        models.Answer.is_correct == True
    ).count()
    
    attempt.score = int((correct_answers / total_questions) * 100) if total_questions > 0 else 0
    attempt.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(attempt)
    return attempt

# Statistics operations
def get_user_stats(db: Session, user_id: int) -> schemas.UserStats:
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    total_quizzes = db.query(models.Quiz).filter(
        models.Quiz.author == user.username
    ).count()
    
    attempts_query = db.query(models.QuizAttempt).filter(
        models.QuizAttempt.user_id == user_id
    )
    
    total_attempts = attempts_query.count()
    completed_attempts = attempts_query.filter(
        models.QuizAttempt.completed_at.isnot(None)
    ).count()
    
    avg_score = db.query(func.avg(models.QuizAttempt.score)).filter(
        models.QuizAttempt.user_id == user_id,
        models.QuizAttempt.completed_at.isnot(None)
    ).scalar() or 0.0
    
    return schemas.UserStats(
        total_quizzes_created=total_quizzes,
        total_attempts=total_attempts,
        completed_attempts=completed_attempts,
        average_score=round(float(avg_score), 2)
        
)

def get_quiz_leaderboard(db: Session, quiz_id: int, limit: int = 10) -> List[schemas.LeaderboardEntry]:
    quiz = get_quiz(db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    leaderboard = db.query(
        models.User.username,
        models.QuizAttempt.score,
        models.QuizAttempt.completed_at
    ).join(
        models.QuizAttempt,
        models.User.id == models.QuizAttempt.user_id
    ).filter(
        models.QuizAttempt.quiz_id == quiz_id,
        models.QuizAttempt.completed_at.isnot(None),
        models.QuizAttempt.score.isnot(None)
    ).order_by(
        models.QuizAttempt.score.desc()
    ).limit(limit).all()
    
    return [
        schemas.LeaderboardEntry(
            username=username,
            score=score,
            completed_at=completed_at
        )
        for username, score, completed_at in leaderboard
    ]

def delete_quiz(db: Session, quiz_id: int, user_id: int) -> bool:
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    quiz = get_quiz(db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    if quiz.author != user.username:
        raise HTTPException(status_code=403, detail="Not authorized to delete this quiz")
    
    db.delete(quiz)
    db.commit()
    return True

def update_quiz(db: Session, quiz_id: int, user_id: int, quiz_update: schemas.QuizCreate) -> models.Quiz:
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    quiz = get_quiz(db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    if quiz.author != user.username:
        raise HTTPException(status_code=403, detail="Not authorized to update this quiz")
    
    for key, value in quiz_update.dict(exclude_unset=True).items():
        setattr(quiz, key, value)
    
    db.commit()
    db.refresh(quiz)
    return quiz