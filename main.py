"""
DỰ ÁN: HỆ THỐNG GIAO DỊCH TÀI CHÍNH NỘI BỘ (INTERNAL TREASURY PORTAL)
Mô tả: Hệ thống yêu cầu xác thực 2 bước (MFA) đối với các tài khoản Quản trị viên
để thực hiện các lệnh chuyển ngân ngân sách công ty.
"""

from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
import secrets

app = FastAPI(title="Treasury Financial Portal API", version="1.0.0")

# ==========================================
# CƠ SỞ DỮ LIỆU GIẢ LẬP & LƯU TRỮ PHIÊN (SESSION STORE)
# ==========================================
class User:
    def __init__(self, id: int, username: str, password_hash: str, role: str, mfa_enabled: bool, mfa_secret_otp: str):
        self.id = id
        self.username = username
        self.password_hash = password_hash  # Trong thực tế đã băm
        self.role = role
        self.mfa_enabled = mfa_enabled
        self.mfa_secret_otp = mfa_secret_otp  # Mã OTP cố định để minh họa demo

# Tài khoản Giám đốc tài chính (Bắt buộc bật 2FA)
USERS_DB = {
    "cfo_admin": User(
        id=101,
        username="cfo_admin",
        password_hash="P@ssw0rd2026!",
        role="TREASURY_ADMIN",
        mfa_enabled=True,
        mfa_secret_otp="889900"
    )
}

# Bảng lưu trữ token hợp lệ của hệ thống
# Token -> {"user_id": int, "role": str, "username": str}
ACTIVE_SESSIONS = {}

# ==========================================
# PYDANTIC SCHEMAS
# ==========================================
class LoginRequest(BaseModel):
    username: str
    password: str

class VerifyOTPRequest(BaseModel):
    otp: str

class TransferRequest(BaseModel):
    recipient_account: str
    amount: float
    note: str

# ==========================================
# DEPENDENCY KIỂM TRA PHIÊN ĐĂNG NHẬP
# ==========================================
def get_current_user(authorization: Optional[str] = Header(None)):
    """Kiểm tra Bearer Token gửi lên từ client."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Yêu cầu cung cấp Bearer Token")
    
    token = authorization.split(" ")[1]
    session_data = ACTIVE_SESSIONS.get(token)
    if not session_data:
        raise HTTPException(status_code=401, detail="Phiên làm việc không tồn tại hoặc đã hết hạn")
    
    return session_data

# ==========================================
# CÁC API ENDPOINTS
# ==========================================

@app.post("/api/v1/auth/login")
def login(creds: LoginRequest):
    """
    Bước 1: Xác thực Tên đăng nhập và Mật khẩu.
    """
    user = USERS_DB.get(creds.username)
    if not user or user.password_hash != creds.password:
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")
    
    # Sinh access token cấp phiên làm việc
    access_token = secrets.token_hex(24)
    ACTIVE_SESSIONS[access_token] = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role
    }

    # KIỂM TRA ĐIỀU KIỆN 2FA
    if user.mfa_enabled:
        return {
            "mfa_required": True,
            "session_token": access_token,
            "message": "Mật khẩu chính xác. Vui lòng chuyển hướng sang màn hình nhập OTP để hoàn tất."
        }

    return {
        "mfa_required": False,
        "session_token": access_token,
        "message": "Đăng nhập thành công"
    }


@app.post("/api/v1/auth/verify-otp")
def verify_otp(payload: VerifyOTPRequest, current_user = Depends(get_current_user)):
    """
    Bước 2: Xác thực mã OTP 6 số thứ hai.
    """
    user = USERS_DB.get(current_user["username"])
    if not user:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
    
    if payload.otp != user.mfa_secret_otp:
        raise HTTPException(status_code=400, detail="Mã OTP không chính xác")

    return {
        "status": "success",
        "message": "Xác thực OTP thành công. Bạn đã hoàn tất xác thực 2 yếu tố."
    }


@app.post("/api/v1/treasury/transfer")
def transfer_money(payload: TransferRequest, current_user = Depends(get_current_user)):
    """
    API Nghiệp vụ đặc quyền: Thực hiện chuyển ngân quỹ.
    Yêu cầu quyền hạn: TREASURY_ADMIN
    """
    if current_user["role"] != "TREASURY_ADMIN":
        raise HTTPException(status_code=403, detail="Chỉ Quản trị viên Tài chính mới có quyền chuyển tiền")

    # Thực hiện lệnh chuyển quỹ thành công
    return {
        "status": "success",
        "transaction_id": f"TXN_{secrets.token_hex(8)}",
        "sender": current_user["username"],
        "transferred_to": payload.recipient_account,
        "amount": payload.amount,
        "note": payload.note
    }
