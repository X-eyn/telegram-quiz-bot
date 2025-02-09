# api/main.py
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from . import crud, models, schemas
from .database import SessionLocal, engine
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import logging
from fastapi.responses import JSONResponse


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="QuizBot API",
    description="API for managing quizzes and attempts",
    version="1.0.0"
)

# Add error handler
@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )

# Rest of your imports
from . import crud, models, schemas
from .database import SessionLocal, engine

# Create tables (if they don't exist)
models.Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)

@app.get("/users/{user_id}", response_model=schemas.User)
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@app.get("/users/{user_id}/quizzes/", response_model=List[schemas.Quiz])
def read_user_quizzes(user_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    quizzes = crud.get_user_quizzes(db, user_id=user_id, skip=skip, limit=limit)
    return quizzes

@app.post("/quizzes/", response_model=schemas.Quiz)
def create_quiz(quiz: schemas.QuizCreate, creator_id: int, db: Session = Depends(get_db)):
    return crud.create_quiz(db=db, quiz=quiz, creator_id=creator_id)

@app.get("/quizzes/{quiz_id}", response_model=schemas.Quiz)
def read_quiz(quiz_id: int, db: Session = Depends(get_db)):
    db_quiz = crud.get_quiz(db, quiz_id=quiz_id)
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return db_quiz

@app.post("/attempts/", response_model=schemas.Attempt)
def create_attempt(attempt: schemas.AttemptCreate, user_id: int, db: Session = Depends(get_db)):
    return crud.create_attempt(db=db, attempt=attempt, user_id=user_id)

@app.post("/attempts/{attempt_id}/answers/", response_model=schemas.Answer)
def submit_answer(attempt_id: int, answer: schemas.AnswerCreate, db: Session = Depends(get_db)):
    return crud.submit_answer(db=db, attempt_id=attempt_id, answer=answer)

@app.post("/attempts/{attempt_id}/complete", response_model=schemas.Attempt)
def complete_attempt(attempt_id: int, db: Session = Depends(get_db)):
    return crud.complete_attempt(db=db, attempt_id=attempt_id)

@app.get("/quizzes/{quiz_id}/attempts/", response_model=List[schemas.Attempt])
def read_quiz_attempts(quiz_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    db_quiz = crud.get_quiz(db, quiz_id=quiz_id)
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return db_quiz.attempts[skip:skip+limit]

# Additional utility endpoints
@app.get("/quizzes/search/", response_model=List[schemas.Quiz])
def search_quizzes(q: str, db: Session = Depends(get_db)):
    quizzes = db.query(models.Quiz).filter(
        models.Quiz.name.ilike(f"%{q}%")
    ).all()
    return quizzes

@app.get("/users/{user_id}/stats")
def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    user = crud.get_user(db, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    total_quizzes = len(user.quizzes)
    total_attempts = len(user.attempts)
    completed_attempts = sum(1 for attempt in user.attempts if attempt.completed_at)
    avg_score = sum(attempt.score or 0 for attempt in user.attempts if attempt.completed_at) / completed_attempts if completed_attempts > 0 else 0
    
    return {
        "total_quizzes_created": total_quizzes,
        "total_attempts": total_attempts,
        "completed_attempts": completed_attempts,
        "average_score": round(avg_score, 2)
    }

@app.put("/quizzes/{quiz_id}", response_model=schemas.Quiz)
def update_quiz(quiz_id: int, quiz_update: schemas.QuizCreate, db: Session = Depends(get_db)):
    db_quiz = crud.get_quiz(db, quiz_id=quiz_id)
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    # Update quiz properties
    for key, value in quiz_update.dict(exclude={'questions'}).items():
        setattr(db_quiz, key, value)
    
    # Delete existing questions
    db.query(models.Question).filter(models.Question.quiz_id == quiz_id).delete()
    
    # Add new questions
    for i, question in enumerate(quiz_update.questions):
        db_question = models.Question(
            **question.dict(),
            quiz_id=quiz_id,
            order=i
        )
        db.add(db_question)
    
    db.commit()
    db.refresh(db_quiz)
    return db_quiz

@app.delete("/quizzes/{quiz_id}")
def delete_quiz(quiz_id: int, db: Session = Depends(get_db)):
    db_quiz = crud.get_quiz(db, quiz_id=quiz_id)
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    db.delete(db_quiz)
    db.commit()
    return {"message": "Quiz deleted successfully"}

@app.get("/leaderboard/quiz/{quiz_id}")
def get_quiz_leaderboard(quiz_id: int, db: Session = Depends(get_db)):
    quiz = crud.get_quiz(db, quiz_id=quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    leaderboard = db.query(
        models.User.username,
        models.QuizAttempt.score,
        models.QuizAttempt.completed_at
    ).join(
        models.QuizAttempt
    ).filter(
        models.QuizAttempt.quiz_id == quiz_id,
        models.QuizAttempt.completed_at.isnot(None)
    ).order_by(
        models.QuizAttempt.score.desc()
    ).limit(10).all()
    
    return [
        {
            "username": username,
            "score": score,
            "completed_at": completed_at
        }
        for username, score, completed_at in leaderboard
    ]

@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)