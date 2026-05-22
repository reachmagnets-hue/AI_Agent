"""Authentication and authorization utilities with JWT support."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel

from ..core.config import get_settings_lazy
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenData(BaseModel):
    """Token payload data"""
    sub: str  # Subject (user ID)
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp
    scopes: list = []  # Permission scopes


class User(BaseModel):
    """User model"""
    id: str
    email: str
    name: str
    is_active: bool = True
    scopes: list = []


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.warning(f"Password verification error: {str(e)}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token"""
    settings = get_settings_lazy()
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "iss": "reach-magnets-api"
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )

    return encoded_jwt


def verify_token(token: str) -> Optional[TokenData]:
    """Verify a JWT token"""
    settings = get_settings_lazy()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )

        token_data = TokenData(**payload)

        # Check expiration
        if token_data.exp < int(datetime.utcnow().timestamp()):
            return None

        return token_data

    except JWTError as e:
        logger.debug(f"JWT verification error: {str(e)}")
        return None
    except Exception as e:
        logger.warning(f"Token verification error: {str(e)}")
        return None


def generate_reset_token() -> str:
    """Generate a secure token for password reset"""
    import secrets
    return secrets.token_urlsafe(32)


class AuthManager:
    """Centralized authentication manager"""

    def __init__(self):
        self._token_cache = {}

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user"""
        # This is a placeholder - integrate with your user management system
        # Example with Supabase Auth:

        # from app.core.database import get_supabase
        # supabase = get_supabase()
        # try:
        #     auth_response = supabase.auth.sign_in_with_password(email=email, password=password)
        #     if auth_response.user:
        #         return User(
        #             id=auth_response.user.id,
        #             email=auth_response.user.email,
        #             name=auth_response.user.user_metadata.get("name", "")
        #         )
        # except Exception as e:
        #     logger.error(f"Authentication error: {str(e)}")

        return None

    async def get_user_from_token(self, token: str) -> Optional[User]:
        """Get user from JWT token"""
        token_data = verify_token(token)
        if not token_data:
            return None

        # Fetch user from database
        # from app.core.database import get_supabase
        # supabase = get_supabase()
        # user_response = supabase.table("users").select("*").eq("id", token_data.sub).execute()

        # if user_response.data:
        #     user_data = user_response.data[0]
        #     return User(**user_data)

        return None

    def check_permission(self, user: User, required_scopes: list) -> bool:
        """Check if user has required permissions"""
        user_scopes = set(user.scopes)
        required_scopes = set(required_scopes)

        return required_scopes.issubset(user_scopes)

    async def invalidate_token(self, token: str):
        """Invalidate a token (logout)"""
        # Add to blacklist or remove from cache
        pass


# Global auth manager instance
auth_manager = AuthManager()