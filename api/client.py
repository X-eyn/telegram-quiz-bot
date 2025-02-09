# api/client.py
import httpx
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime

class QuizBotClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient()
    
    async def close(self):
        await self.client.aclose()
    
    async def create_user(self, username: str, telegram_id: Optional[str] = None) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/users/",
            json={"username": username, "telegram_id": telegram_id}
        )
        response.raise_for_status()
        return response.json()
    
    async def create_quiz(self, creator_id: int, quiz_data: Dict[str, Any]) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/quizzes/",
            params={"creator_id": creator_id},
            json=quiz_data
        )
        response.raise_for_status()
        return response.json()
    
    async def get_quiz(self, quiz_id: int) -> Dict:
        response = await self.client.get(f"{self.base_url}/quizzes/{quiz_id}")
        response.raise_for_status()
        return response.json()
    
    async def create_attempt(self, user_id: int, quiz_id: int) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/attempts/",
            params={"user_id": user_id},
            json={"quiz_id": quiz_id}
        )
        response.raise_for_status()
        return response.json()
    
    async def submit_answer(self, attempt_id: int, question_id: int, answer: str) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/attempts/{attempt_id}/answers/",
            json={
                "question_id": question_id,
                "answer_text": answer
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def complete_attempt(self, attempt_id: int) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/attempts/{attempt_id}/complete"
        )
        response.raise_for_status()
        return response.json()
    
    async def get_user_stats(self, user_id: int) -> Dict:
        response = await self.client.get(f"{self.base_url}/users/{user_id}/stats")
        response.raise_for_status()
        return response.json()
    
    async def get_quiz_leaderboard(self, quiz_id: int) -> List[Dict]:
        response = await self.client.get(f"{self.base_url}/leaderboard/quiz/{quiz_id}")
        response.raise_for_status()
        return response.json()

# Example usage
async def main():
    client = QuizBotClient()
    try:
        # Create a user
        user = await client.create_user("testuser", "123456")
        
        # Create a quiz
        quiz_data = {
            "name": "Test Quiz",
            "is_random": False,
            "questions": [
                {
                    "question_type": "QuestionString",
                    "question_text": "What is the capital of France?",
                    "correct_answer": "Paris"
                }
            ]
        }
        quiz = await client.create_quiz(user["id"], quiz_data)
        
        # Start an attempt
        attempt = await client.create_attempt(user["id"], quiz["id"])
        
        # Submit answer
        answer = await client.submit_answer(
            attempt["id"],
            quiz["questions"][0]["id"],
            "Paris"
        )
        
        # Complete attempt
        completed = await client.complete_attempt(attempt["id"])
        
        print(f"Quiz completed with score: {completed['score']}")
        
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())