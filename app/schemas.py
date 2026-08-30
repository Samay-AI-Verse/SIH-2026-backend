from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr, Field, field_validator
import re

class MemberBase(BaseModel):
    full_name: str = Field(..., min_length=2)
    email: Optional[str] = ""
    phone: Optional[str] = ""
    gender: str # Male / Female / Other
    college: Optional[str] = ""
    course: Optional[str] = ""
    branch: Optional[str] = ""
    year: Optional[str] = ""
    student_id: Optional[str] = ""

class MemberCreate(MemberBase):
    pass

class MemberOut(MemberBase):
    id: str
    team_id: str
    is_leader: bool
    created_at: str

    class Config:
        from_attributes = True

class TeamRegisterRequest(BaseModel):
    team_name: str = Field(..., min_length=3, max_length=100)
    college: Optional[str] = ""
    university: Optional[str] = ""
    city: Optional[str] = ""
    state: Optional[str] = ""
    
    leader_name: str = Field(..., min_length=2)
    leader_email: EmailStr
    leader_phone: str = Field(..., min_length=10)
    leader_gender: str
    leader_course: Optional[str] = ""
    leader_branch: Optional[str] = ""
    leader_year: Optional[str] = ""
    leader_student_id: Optional[str] = ""
    
    # Selected Problem Statement / Open Innovation
    selected_problem_id: Optional[str] = None
    is_open_innovation: Optional[bool] = False
    open_innovation_title: Optional[str] = None
    open_innovation_description: Optional[str] = None
    
    # 6 members (Leader + 5 Members)
    members: List[MemberCreate]

    @field_validator("team_name")
    def clean_team_name(cls, v):
        cleaned = v.strip()
        if len(cleaned) < 3:
            raise ValueError("Team name must be at least 3 characters long")
        return cleaned

    @field_validator("leader_phone")
    def validate_phone(cls, v):
        cleaned = re.sub(r"\s+", "", v)
        if not re.match(r"^[6-9]\d{9}$", cleaned):
            raise ValueError("Leader phone number must be a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9")
        return cleaned

    @field_validator("members")
    def validate_roster(cls, members):
        if len(members) != 6:
            raise ValueError("Exactly 6 team members (Leader + 5 members) are required")
        
        # Check female requirement
        has_female = any(m.gender.lower() == "female" for m in members)
        if not has_female:
            raise ValueError("SIH guidelines require at least 1 female team member")
        return members

class TeamLookupRequest(BaseModel):
    email: EmailStr
    team_name: Optional[str] = None
    registration_id: Optional[str] = None

class TeamOut(BaseModel):
    id: str
    registration_id: str
    team_name: str
    college: Optional[str] = ""
    university: Optional[str] = ""
    city: Optional[str] = ""
    state: Optional[str] = ""
    leader_name: str
    leader_email: str
    leader_phone: str
    leader_gender: str
    leader_course: str
    leader_branch: str
    leader_year: str
    leader_student_id: str
    registration_status: str
    payment_status: str
    selected_problem_id: Optional[str] = None
    selected_problem_title: Optional[str] = None
    is_open_innovation: bool
    open_innovation_title: Optional[str] = None
    open_innovation_description: Optional[str] = None
    registered_at: str
    members: List[MemberOut] = []
    payment_utr: Optional[str] = None
    payment_proof_url: Optional[str] = None

    class Config:
        from_attributes = True

class ProblemOut(BaseModel):
    id: str
    code: str
    title: str
    organization: str
    category: str
    theme: str
    difficulty: str
    description: str
    background: str
    expected_solution: str
    technical_requirements: Any
    technologies: Any
    constraint_items: Any
    evaluation_criteria: Any
    selected_count: int
    max_selections: int
    is_open_innovation: bool
    status: str
    sort_order: int

    class Config:
        from_attributes = True

class ProblemSelectRequest(BaseModel):
    team_id: str
    problem_id: str
    problem_title: Optional[str] = None
    # If selecting Open Innovation
    is_open_innovation: Optional[bool] = False
    open_innovation_title: Optional[str] = None
    open_innovation_description: Optional[str] = None

class PaymentUtrSubmitRequest(BaseModel):
    team_id: str
    utr: Optional[str] = ""
    proof_key: Optional[str] = None
    proof_url: Optional[str] = None
    payment_mode: Optional[str] = "ONLINE"
    collector_name: Optional[str] = None
    receipt_no: Optional[str] = None

    @field_validator("utr")
    def clean_utr(cls, v):
        if not v:
            return ""
        cleaned = re.sub(r"\s+", "", v.upper())
        if cleaned and len(cleaned) < 3:
            raise ValueError("Valid UTR / Transaction ID / Receipt Number is required")
        return cleaned

class PaymentVerifyRequest(BaseModel):
    team_id: str
    status: str # SUCCESS / FAILED / PENDING
    admin_notes: Optional[str] = ""

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str
    google_email: Optional[str] = None
    google_name: Optional[str] = None

class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: dict

class ContactCreate(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str

class SettingsOut(BaseModel):
    fee: float
    currency: str
    is_active: bool
    min_members: int
    max_members: int
    female_required: bool

class ExpenseCreateRequest(BaseModel):
    title: str
    category: Optional[str] = "General"
    amount: float
    paid_to: Optional[str] = ""
    notes: Optional[str] = ""

class TeamCancelRequest(BaseModel):
    refund: Optional[bool] = False
    admin_notes: Optional[str] = ""

class TeamNameUpdateRequest(BaseModel):
    team_name: str = Field(..., min_length=3, max_length=100)

class AdminCreateRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2)
    password: str = Field(..., min_length=6)
    role: Optional[str] = "ADMIN" # SUPER_ADMIN or ADMIN
    google_email: Optional[str] = None

class AdminRoleUpdateRequest(BaseModel):
    role: str # SUPER_ADMIN or ADMIN

class AdminLoginLogResponse(BaseModel):
    id: str
    admin_id: Optional[str] = None
    email: str
    name: Optional[str] = None
    role: Optional[str] = None
    google_email: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str
    timestamp: str

    class Config:
        from_attributes = True

class AdminProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

class AdminPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)

class ForceLogoutResponse(BaseModel):
    success: bool
    message: str
    logged_out_at: str

class TeamCheckinRequest(BaseModel):
    entry_status: Optional[str] = "CHECKED_IN" # CHECKED_IN / PENDING
    checked_in_by: Optional[str] = None
    desk_number: Optional[str] = None
    goodies_status: Optional[str] = None # COLLECTED / PENDING / None
    goodies_count: Optional[int] = None
    goodies_distributed_by: Optional[str] = None
    checkin_notes: Optional[str] = None
    present_member_ids: Optional[List[str]] = None

class TeamBatchCheckinRequest(BaseModel):
    team_ids: List[str]
    action: str # "CHECKIN" / "GOODIES" / "CHECKIN_AND_GOODIES" / "RESET"
    coordinator_name: Optional[str] = "Admin Desk"
    desk_prefix: Optional[str] = None
    goodies_count: Optional[int] = 6



