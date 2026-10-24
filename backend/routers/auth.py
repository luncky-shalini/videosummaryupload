import logging
import re
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional
from dependencies import get_current_user
from database import get_supabase_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class CheckEmailRequest(BaseModel):
    email: str

class ConfirmAccountRequest(BaseModel):
    email: str


@router.get("/me")
async def get_current_user_profile(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Returns current authenticated user details and ensures profile record exists in public.profiles.
    Never trusts client-supplied identity; extracts verified claims from Supabase auth.
    """
    metadata = user.get("user_metadata", {})
    full_name = metadata.get("full_name") or metadata.get("name") or (user["email"].split("@")[0] if user.get("email") else "User")
    avatar_url = metadata.get("avatar_url") or metadata.get("picture")

    profile_data = {
        "id": user["id"],
        "email": user["email"],
        "full_name": full_name,
        "avatar_url": avatar_url,
    }

    try:
        admin_supabase = get_supabase_admin()
        admin_supabase.table("profiles").upsert(profile_data, on_conflict="id").execute()
    except Exception as e:
        logger.debug(f"Profiles table upsert non-critical: {e}")

    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": full_name,
        "avatar_url": avatar_url,
        "metadata": metadata
    }

@router.post("/register")
async def register_user(req: RegisterRequest):
    """
    Registers a new user with verified email in Supabase.
    Bypasses Supabase free-tier SMTP rate-limit (429 email rate limit exceeded)
    by confirming the email upon registration so the user can immediately log in with signInWithPassword.
    """
    email = req.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid email address (e.g. name@example.com)."
        )
    if len(req.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long."
        )

    admin_supabase = get_supabase_admin()

    # If user already exists, update/link their password so they are never blocked
    try:
        users = admin_supabase.auth.admin.list_users(page=1, per_page=1000)
        for u in users:
            if u.email and u.email.lower() == email:
                full_name = (req.full_name or u.user_metadata.get("full_name") or email.split("@")[0]).strip()
                admin_supabase.auth.admin.update_user_by_id(u.id, {
                    "password": req.password,
                    "email_confirm": True,
                    "user_metadata": {
                        "full_name": full_name,
                        "name": full_name
                    }
                })
                # Ensure profile record exists
                try:
                    admin_supabase.table("profiles").upsert({
                        "id": u.id,
                        "email": email,
                        "full_name": full_name,
                        "updated_at": "now()"
                    }, on_conflict="id").execute()
                except Exception:
                    pass

                return {
                    "success": True,
                    "message": "Account credentials updated successfully.",
                    "user_id": u.id
                }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"User pre-check note: {e}")

    try:
        full_name = (req.full_name or email.split("@")[0]).strip()
        user_res = admin_supabase.auth.admin.create_user({
            "email": email,
            "password": req.password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": full_name,
                "name": full_name
            }
        })

        if not user_res.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user account. Please try again."
            )

        # Ensure profile record exists
        try:
            admin_supabase.table("profiles").upsert({
                "id": user_res.user.id,
                "email": email,
                "full_name": full_name,
                "updated_at": "now()"
            }, on_conflict="id").execute()
        except Exception as pe:
            logger.debug(f"Profile creation note: {pe}")

        return {
            "success": True,
            "message": "Account created successfully. You can now sign in.",
            "user_id": user_res.user.id
        }
    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e)
        if "already registered" in err_msg.lower() or "unique" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists. Please sign in or reset your password."
            )
        logger.error(f"Registration failure: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {err_msg}"
        )

@router.post("/check-method")
async def check_auth_method(req: CheckEmailRequest):
    """
    Checks the authentication method associated with an email.
    Helps display clear guidance if a user attempts password login on a Google OAuth account.
    """
    email = req.email.strip().lower()
    admin_supabase = get_supabase_admin()

    try:
        users = admin_supabase.auth.admin.list_users(page=1, per_page=1000)
        for u in users:
            if u.email and u.email.lower() == email:
                providers = u.app_metadata.get("providers", [])
                has_google = "google" in providers or u.app_metadata.get("provider") == "google"
                has_email = "email" in providers
                is_confirmed = bool(u.email_confirmed_at)
                return {
                    "exists": True,
                    "has_google": has_google,
                    "has_email": has_email,
                    "is_confirmed": is_confirmed
                }
    except Exception as e:
        logger.warning(f"check_auth_method error: {e}")

    return {
        "exists": False,
        "has_google": False,
        "has_email": False,
        "is_confirmed": False
    }

@router.post("/confirm-account")
async def confirm_account(req: ConfirmAccountRequest):
    """
    Confirms an unconfirmed user account's email so they are not blocked by email delivery limits.
    """
    email = req.email.strip().lower()
    admin_supabase = get_supabase_admin()

    try:
        users = admin_supabase.auth.admin.list_users(page=1, per_page=1000)
        for u in users:
            if u.email and u.email.lower() == email:
                if not u.email_confirmed_at:
                    admin_supabase.auth.admin.update_user_by_id(u.id, {"email_confirm": True})
                    return {
                        "success": True,
                        "message": "Account email verified successfully. You can now sign in."
                    }
                return {
                    "success": True,
                    "message": "Account email is already verified. You can sign in directly."
                }
    except Exception as e:
        logger.error(f"confirm_account error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify account email."
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No account found with this email."
    )

