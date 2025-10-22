import logging
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from google.auth import default
from google.auth.transport.requests import Request
import requests
import uvicorn
import json

# Configure logging
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# Initialize FastAPI app
app = FastAPI(title="Gemini Web Server")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request model
class PromptRequest(BaseModel):
    prompt: str

# Configuration
# Available Vertex AI Gemini models (October 2024)
# Based on Google Cloud documentation
GEMINI_MODELS = {
    # Latest models (2.5 series) - These work without version suffix
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
    
    # 2.0 series - These need the -001 suffix
    "gemini-2.0-flash": "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite": "gemini-2.0-flash-lite-001",
    
    # Legacy models (still available)
    "gemini-1.5-flash": "gemini-1.5-flash-002",
    "gemini-1.5-pro": "gemini-1.5-pro-002",
    "gemini-pro": "gemini-pro",
}

# Select model (can be configured via environment variable)
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
MODEL_ID = GEMINI_MODELS.get(MODEL_NAME, "gemini-2.0-flash-001")

# Initialize credentials and project info
logger.info("Initializing Gemini API credentials...")
creds = None
project_id = None

# Location can be 'us-central1' or 'global' (global provides better availability)
location = os.environ.get("VERTEX_AI_LOCATION", "us-central1")

try:
    # Get credentials with correct scopes for Vertex AI
    creds, project = default(scopes=[
        "https://www.googleapis.com/auth/cloud-platform"
    ])
    
    # Get project ID from various sources
    project_id = project or os.environ.get('GCP_PROJECT') or os.environ.get('GOOGLE_CLOUD_PROJECT')
    
    # For Cloud Run, we can also get it from metadata server
    if not project_id:
        try:
            import urllib.request
            req = urllib.request.Request(
                'http://metadata.google.internal/computeMetadata/v1/project/project-id',
                headers={'Metadata-Flavor': 'Google'}
            )
            project_id = urllib.request.urlopen(req).read().decode('utf-8')
        except:
            pass
    
    logger.info(f"Credentials obtained successfully")
    logger.info(f"Project ID: {project_id}")
    logger.info(f"Location: {location}")
    logger.info(f"Model: {MODEL_NAME} -> {MODEL_ID}")
    
except Exception as e:
    logger.error(f"Failed to obtain credentials: {e}")
    logger.error("Please ensure Google Cloud credentials are properly configured")

@app.post("/api/generate")
async def generate_content(request: PromptRequest):
    """
    Endpoint to generate content using Gemini API via Vertex AI
    """
    if not creds:
        raise HTTPException(
            status_code=500, 
            detail="Google Cloud credentials not available. Please check service account configuration."
        )
    
    if not project_id:
        raise HTTPException(
            status_code=500,
            detail="Project ID not found. Please set GCP_PROJECT or GOOGLE_CLOUD_PROJECT environment variable."
        )
    
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    
    logger.info(f"Received prompt: {request.prompt[:100]}...")
    
    try:
        # Refresh credentials to get fresh access token
        logger.debug("Refreshing credentials to obtain access token...")
        creds.refresh(Request())
        access_token = creds.token
        logger.info(f"Access token retrieved successfully (length={len(access_token)} characters)")
        
        # Build the Vertex AI endpoint URL
        # Note: Some models work better with 'global' location
        if location == "global" or MODEL_ID.startswith("gemini-2.5"):
            # Use global endpoint for 2.5 models or when specified
            API_ENDPOINT = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/global/publishers/google/models/{MODEL_ID}:generateContent"
        else:
            # Use regional endpoint
            API_ENDPOINT = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/{MODEL_ID}:generateContent"
        
        logger.info(f"Using Vertex AI endpoint: {API_ENDPOINT}")
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Vertex AI request format
        data = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": request.prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 8192,
                "candidateCount": 1
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        }
        
        logger.debug(f"Request headers prepared")
        logger.debug(f"Request payload: {json.dumps(data, indent=2)}")
        
        logger.info("Sending POST request to Vertex AI Gemini API...")
        resp = requests.post(API_ENDPOINT, headers=headers, json=data, timeout=60)
        logger.info(f"Response received with status code: {resp.status_code}")
        
        if resp.status_code != 200:
            error_details = resp.text
            logger.error(f"Vertex AI API error: {error_details}")
            
            # Parse error for better message
            try:
                error_json = resp.json()
                error_message = error_json.get('error', {}).get('message', error_details)
                
                # Provide helpful error messages based on status code
                if "404" in str(resp.status_code) or "NOT_FOUND" in error_details:
                    error_message += f"\n\nModel '{MODEL_ID}' not found."
                    error_message += "\n\nTry these solutions:"
                    error_message += "\n1. Use 'global' location: Set VERTEX_AI_LOCATION=global"
                    error_message += "\n2. Try a different model:"
                    error_message += "\n   - gemini-2.0-flash (recommended)"
                    error_message += "\n   - gemini-2.5-flash (if available in your project)"
                    error_message += "\n   - gemini-1.5-flash"
                    error_message += "\n3. Check if Vertex AI API is enabled"
                    error_message += "\n4. Verify your project has access to Gemini models"
                    
                elif "403" in str(resp.status_code):
                    error_message += "\n\nAuthentication/Permission Issue:"
                    error_message += "\n1. Enable Vertex AI API: gcloud services enable aiplatform.googleapis.com"
                    error_message += "\n2. Grant service account the correct role:"
                    error_message += f"\n   gcloud projects add-iam-policy-binding {project_id} \\"
                    error_message += f"\n     --member='serviceAccount:YOUR_SERVICE_ACCOUNT' \\"
                    error_message += "\n     --role='roles/aiplatform.user'"
                
                raise HTTPException(status_code=resp.status_code, detail=error_message)
            except json.JSONDecodeError:
                raise HTTPException(status_code=resp.status_code, detail=error_details)
        
        response_json = resp.json()
        logger.debug(f"Full JSON response received successfully")
        
        # Extract the generated text from Vertex AI response format
        try:
            candidates = response_json.get('candidates', [])
            if candidates and len(candidates) > 0:
                content = candidates[0].get('content', {})
                parts = content.get('parts', [])
                if parts and len(parts) > 0:
                    generated_text = parts[0].get('text', '')
                    return {"response": generated_text}
            
            # If we can't parse the response, return the whole thing
            logger.warning("Could not parse standard response format, returning raw response")
            return {"response": str(response_json)}
            
        except (KeyError, IndexError) as e:
            logger.error(f"Error parsing Gemini response: {e}")
            return {"response": str(response_json)}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    service_account = "default"
    try:
        if hasattr(creds, 'service_account_email'):
            service_account = creds.service_account_email
    except:
        pass
    
    return {
        "status": "healthy",
        "credentials_available": creds is not None,
        "project_id": project_id,
        "location": location,
        "model": f"{MODEL_NAME} ({MODEL_ID})",
        "service_account": service_account,
        "available_models": list(GEMINI_MODELS.keys()),
        "note": "If model not found, try setting VERTEX_AI_LOCATION=global"
    }

@app.get("/models")
async def list_models():
    """List available Gemini models"""
    return {
        "current_model": MODEL_ID,
        "current_location": location,
        "available_models": GEMINI_MODELS,
        "recommended_models": [
            "gemini-2.0-flash (best for most use cases)",
            "gemini-2.5-flash (latest, may require global location)",
            "gemini-1.5-flash (stable, widely available)"
        ],
        "configuration": {
            "GEMINI_MODEL": "Set to change model (e.g., gemini-2.0-flash)",
            "VERTEX_AI_LOCATION": "Set to 'global' or 'us-central1'"
        }
    }

@app.get("/")
async def serve_frontend():
    """Serve the HTML frontend"""
    return FileResponse("static/index.html")

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting FastAPI server on http://0.0.0.0:{port}")
    logger.info(f"Using model: {MODEL_NAME} -> {MODEL_ID}")
    logger.info(f"Location: {location}")
    uvicorn.run(app, host="0.0.0.0", port=port)
