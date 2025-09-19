from datetime import datetime, timedelta
from typing import Optional, Literal, Dict, Any

import os
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext

# Cargar variables de entorno desde .env si existe
load_dotenv()

# Configuración de seguridad por variables de entorno (con valores por defecto seguros para desarrollo)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_SUPER_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_token(
    subject: str,
    *,
    token_type: Literal["access", "refresh"],
    role: Literal["admin", "cobrador"],
    cuenta_id: Optional[int] = None,
    empleado_identificacion: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    now = datetime.utcnow()
    if expires_delta is None:
        expires_delta = (
            timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            if token_type == "access"
            else timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        )
    to_encode: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if cuenta_id is not None:
        to_encode["cuenta_id"] = cuenta_id
    if empleado_identificacion is not None:
        to_encode["empleado_identificacion"] = empleado_identificacion
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


def get_current_principal(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    if payload.get("role") not in ("admin", "cobrador"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol no permitido")
    return payload


def require_admin(principal: dict = Depends(get_current_principal)) -> dict:
    if principal.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol admin")
    return principal


def require_cobrador_for_empleado(
    empleado_id: str,
    principal: dict = Depends(get_current_principal),
) -> dict:
    """Permite admin o cobrador restringido a su propio empleado."""
    role = principal.get("role")
    if role == "admin":
        return principal
    if role == "cobrador":
        if principal.get("empleado_identificacion") != str(empleado_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado a este empleado")
        return principal
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol no permitido")


