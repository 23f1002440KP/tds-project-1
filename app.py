from fastapi import FastAPI, HTTPException, Request,status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
import re
import os
import httpx
from dotenv import load_dotenv
from generator import GenerateCodeLLM
from github_manager import GitHubManager
import asyncio
from contextlib import asynccontextmanager


load_dotenv()  # Load environment variables from .env file




class Attachment(BaseModel):
    name: str
    url: str


class TaskRequest(BaseModel):
    email: EmailStr
    secret: str
    task: str
    round: int = Field(..., ge=0)
    nonce: str
    brief: Optional[str] = None
    checks: Optional[List[str]] = []
    evaluation_url: Optional[str] = None
    attachments: Optional[List[Attachment]] = []



llm_generator: Optional[GenerateCodeLLM] = None
github_manager: Optional[GitHubManager] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes external resources (LLM and GitHub clients) on startup."""
    global llm_generator, github_manager
    
    # Initialize the LLM (will load the GEMINI_API_KEY)
    try:
        llm_generator = GenerateCodeLLM()
    except ValueError as e:
        print(f"FATAL: LLM initialization failed - {e}")
        # We allow the app to start, but the endpoint will fail

    # Initialize the GitHub Manager (will load the GITHUB_TOKEN)
    try:
        github_manager = GitHubManager()
    except ValueError as e:
        print(f"FATAL: GitHub initialization failed - {e}")
        # We allow the app to start, but the endpoint will fail

    print("FastAPI application startup complete. Modules initialized.")
    yield
    print("FastAPI application shutdown.")



app = FastAPI(title="TDS Project API", version="0.1.0",lifespan=lifespan)

# NOTE: for development we allow all origins and headers so OPTIONS preflight requests
# succeed. In production, restrict `allow_origins` to trusted domains or configure
# via environment variables.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("TDS_ALLOW_ORIGINS", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/", summary="Health check")
async def root():
    return {
        "status": "ok", 
        "service": "tds-project-1",
        "version": "0.1.0"
        }


@app.post("/tasks", summary="Receive a task submission")
async def receive_task(payload: TaskRequest, request: Request):
    """Receive the task submission JSON described in the project brief.

    Validates structure and returns an enriched acknowledgement including the nonce.
    """
    # Secret verification: read allowed secrets from environment.



    allowed = os.environ.get("TDS_ACCEPTED_SECRETS") or os.environ.get("TDS_SECRET")
    allowed_secrets = []
    if allowed:
        # allow comma-separated list
        allowed_secrets = [s.strip() for s in allowed.split(",") if s.strip()]

    if not allowed_secrets:
        # If no secret configured, reject to avoid accidental acceptance in production.
        raise HTTPException(status_code=401, detail="No server-side secret configured")

    if payload.secret not in allowed_secrets:
        raise HTTPException(status_code=401, detail="Invalid secret")
    
    
    # Acknowledge receipt with enriched data.
    
    global llm_generator, github_manager
    
    if llm_generator is None:
        raise HTTPException(status_code=503, detail="LLM not initialized on server")

    if github_manager is None:
        raise HTTPException(status_code=503, detail="GitHub Manager not initialized on server")


    try:
        print(f"Processing request for task: {payload.task}, round: {payload.round}")
        import time

        
        start = time.time()
        
        task_data_dict = payload.model_dump()
        generated_files = llm_generator.generate_app_files(task_data_dict)
        
        
        if not generated_files:
            raise ValueError("LLM failed to generate any files.")
        
        task_slug = payload.task.lower().replace(" ", "-")
        task_id = f"{task_slug}-round-{payload.round}"

        print(f"Generated files for task ID: {task_id}: {list(generated_files.keys())}")
        
        
        repo_url, commit_sha, pages_url = github_manager.create_and_deploy(
            task_id=task_id,
            files=generated_files
        )
        # We use the repo_url or pages_url as the final output URL for the user
        final_url = pages_url if pages_url else repo_url
        
        # 4.4. Post to Evaluation URL (Callback)
        try:
            callback_json = {
                "email": payload.email,
                "task": payload.task,
                "round": payload.round,
                "nonce": payload.nonce,
                "repo_url": repo_url,
                "commit_sha": commit_sha,
                "pages_url": pages_url,
            }
            
            async with httpx.AsyncClient(timeout=600.0) as client: # Timeout is 10 min (600s)
                response = await client.post(
                    payload.evaluation_url,
                    json=callback_json,
                    headers={"Content-Type": "application/json"}
                )
                max_attempts = 6  # retries: 1,2,4,8,16,32 seconds
                delay = 1
                last_exc = None

                for attempt in range(1, max_attempts + 1):
                    print(response.status_code)
                    try:
                        response = await client.post(
                            payload.evaluation_url,
                            json=callback_json,
                            headers={"Content-Type": "application/json"}
                        )
                        
                        if response.status_code == 200:
                            response.raise_for_status()
                            break
                        # non-200 status -> prepare an HTTPStatusError and retry
                        last_exc = httpx.HTTPStatusError(
                            f"Unexpected status {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                    except httpx.RequestError as e:
                        last_exc = e

                    if attempt == max_attempts:
                        # Exhausted retries, re-raise last exception to be handled by outer except
                        raise last_exc

                    await asyncio.sleep(delay)
                    delay *= 2
            
            print(f"Successfully posted results to evaluation URL: {payload.evaluation_url}")
            
           

            
        except httpx.RequestError as e:
            print(f"WARNING: Failed to post to evaluation URL. Request error: {e}")
        except httpx.HTTPStatusError as e:
            print(f"WARNING: Failed to post to evaluation URL. Server returned status: {e.response.status_code}")
        
        # 4.5. Success Response
        end = time.time()
        duration = end - start
        
        return {
            "status": "success",
            "message": f"Code generated and deployed successfully to new repository: {repo_url}",
            "commit_url": final_url, # Return the deployment URL
            "evaluation_url": payload.evaluation_url,
            "time_taken":f"{duration:.2f} seconds"
        }
        
    except Exception as e:
        print(f"Error during processing: {e}")
        # 4.6. Error Response
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process request: {e}"
        )
    
