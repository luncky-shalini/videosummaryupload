from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Optional
from config import settings
from database import get_supabase

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Query(None, description="Optional bearer token passed via query string for media/downloads")
) -> Dict[str, Any]:
    """
    Validates Supabase Bearer token (from Authorization header or query param) and returns user dictionary.
    Supports media streaming, direct file downloads, and standard REST requests.
    """
    raw_token = credentials.credentials if credentials else token
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Header with Bearer Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_str = raw_token.strip()
    try:
        supabase = get_supabase()
        user_res = supabase.auth.get_user(token_str)

        if not user_res or not user_res.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {
            "id": user_res.user.id,
            "email": user_res.user.email,
            "user_metadata": user_res.user.user_metadata or {}
        }
    except Exception as e:
        # If Supabase Auth fails or is not yet configured
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Query(None)
) -> Optional[Dict[str, Any]]:
    if not credentials and not token:
        return None
    try:
        return await get_current_user(credentials, token)
    except HTTPException:
        return None
