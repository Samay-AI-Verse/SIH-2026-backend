import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from .database import Base

def generate_uuid():
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc).isoformat()

class Admin(Base):
    __tablename__ = "admins"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, default="SIH Organizer")
    role = Column(String, default="ADMIN")
    token_version = Column(Integer, default=1)
    created_by = Column(String, default="MASTER_ADMIN")
    google_email = Column(String, nullable=True)
    last_login_at = Column(String, nullable=True)
    created_at = Column(String, default=utc_now)

class Setting(Base):
    __tablename__ = "settings"
    
    id = Column(String, primary_key=True, default="global_settings")
    fee = Column(Float, default=300.0)
    currency = Column(String, default="INR")
    is_active = Column(Boolean, default=True)
    min_members = Column(Integer, default=6)
    max_members = Column(Integer, default=6)
    female_required = Column(Boolean, default=True)
    updated_at = Column(String, default=utc_now, onupdate=utc_now)

class Problem(Base):
    __tablename__ = "problems"
    
    id = Column(String, primary_key=True) # PS Code or 'OPEN_INNOVATION'
    code = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    organization = Column(String, default="")
    category = Column(String, default="Software") # Software / Hardware / Open Innovation
    theme = Column(String, default="")
    difficulty = Column(String, default="Medium")
    description = Column(Text, default="")
    background = Column(Text, default="")
    expected_solution = Column(Text, default="")
    technical_requirements = Column(JSON, default=list)
    technologies = Column(JSON, default=list)
    constraint_items = Column(JSON, default=list)
    evaluation_criteria = Column(JSON, default=list)
    selected_count = Column(Integer, default=0)
    max_selections = Column(Integer, default=2)
    status = Column(String, default="AVAILABLE") # AVAILABLE / LOCKED / HIDDEN
    sort_order = Column(Integer, default=0)

class Team(Base):
    __tablename__ = "teams"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    registration_id = Column(String, unique=True, index=True, nullable=False) # e.g. SIH26-0001
    team_name = Column(String, unique=True, index=True, nullable=False)
    college = Column(String, nullable=False)
    university = Column(String, default="")
    city = Column(String, default="")
    state = Column(String, default="")
    leader_name = Column(String, nullable=False)
    leader_email = Column(String, index=True, nullable=False)
    leader_phone = Column(String, nullable=False)
    leader_gender = Column(String, nullable=False)
    leader_course = Column(String, default="B.Tech")
    leader_branch = Column(String, default="")
    leader_year = Column(String, default="")
    leader_student_id = Column(String, default="")
    
    registration_status = Column(String, default="CONFIRMED") # PENDING_PAYMENT / CONFIRMED / CANCELLED
    payment_status = Column(String, default="PENDING") # PENDING / PROCESSING / SUCCESS / FAILED
    
    selected_problem_id = Column(String, ForeignKey("problems.id", ondelete="SET NULL"), nullable=True)
    selected_problem_title = Column(String, nullable=True)
    is_open_innovation = Column(Boolean, default=False)
    open_innovation_title = Column(String, nullable=True)
    open_innovation_description = Column(Text, nullable=True)
    
    # Hackathon Day Entry & Goodies Distribution Tracking
    entry_status = Column(String, default="PENDING") # PENDING / CHECKED_IN
    checked_in_at = Column(String, nullable=True)
    checked_in_by = Column(String, nullable=True) # Coordinator / Admin name
    desk_number = Column(String, nullable=True) # Assigned desk / table / lab slot
    goodies_status = Column(String, default="PENDING") # PENDING / COLLECTED
    goodies_count = Column(Integer, default=0) # e.g. 6 kits
    goodies_collected_at = Column(String, nullable=True)
    goodies_distributed_by = Column(String, nullable=True) # Organizer name
    checkin_notes = Column(Text, default="")
    present_members_count = Column(Integer, default=0)
    present_member_ids = Column(Text, default="[]") # JSON list of member IDs who checked in

    registered_at = Column(String, default=utc_now)
    updated_at = Column(String, default=utc_now, onupdate=utc_now)

    members = relationship("Member", back_populates="team", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="team", cascade="all, delete-orphan")

class Member(Base):
    __tablename__ = "members"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    team_id = Column(String, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, default="")
    phone = Column(String, default="")
    is_leader = Column(Boolean, default=False)
    gender = Column(String, nullable=False) # Male / Female / Other
    college = Column(String, default="")
    course = Column(String, default="")
    branch = Column(String, default="")
    year = Column(String, default="")
    student_id = Column(String, default="")
    entry_status = Column(String, default="PENDING") # PENDING / CHECKED_IN
    checked_in_at = Column(String, nullable=True)
    goodies_received = Column(Boolean, default=False)
    created_at = Column(String, default=utc_now)

    team = relationship("Team", back_populates="members")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    team_id = Column(String, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    registration_id = Column(String, nullable=False, index=True)
    team_name = Column(String, nullable=False)
    order_id = Column(String, unique=True, index=True, nullable=False)
    transaction_id = Column(String, unique=True, index=True, nullable=True) # UTR number
    proof_key = Column(String, nullable=True) # Cloudflare R2 object key
    proof_url = Column(String, nullable=True) # Direct view URL / Signed download
    payment_mode = Column(String, default="ONLINE", nullable=True) # ONLINE / OFFLINE_CASH
    collector_name = Column(String, nullable=True) # Name of organizer who collected cash
    receipt_no = Column(String, nullable=True) # Offline Cash receipt token
    amount = Column(Float, default=300.0, nullable=False)
    currency = Column(String, default="INR", nullable=False)
    status = Column(String, default="PENDING", nullable=False) # PENDING / PROCESSING / SUCCESS / FAILED
    admin_notes = Column(Text, default="")
    created_at = Column(String, default=utc_now)
    updated_at = Column(String, default=utc_now, onupdate=utc_now)

    team = relationship("Team", back_populates="payments")

class ContactMessage(Base):
    __tablename__ = "contact_messages"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(String, default=utc_now)

class Expense(Base):
    __tablename__ = "expenses"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, nullable=False)
    category = Column(String, default="General") # Refreshments, Printing, Banner, Certificates, Mementoes, Prizes, Stage & Sound, Misc
    amount = Column(Float, nullable=False)
    paid_to = Column(String, default="")
    notes = Column(Text, default="")
    created_at = Column(String, default=utc_now)

class AdminLoginLog(Base):
    __tablename__ = "admin_login_logs"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    admin_id = Column(String, nullable=True)
    email = Column(String, nullable=False)
    name = Column(String, nullable=True)
    role = Column(String, nullable=True)
    google_email = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    status = Column(String, default="SUCCESS") # SUCCESS / FAILED
    timestamp = Column(String, default=utc_now)

class DeletedTeamArchive(Base):
    __tablename__ = "deleted_teams_archive"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    team_id = Column(String, nullable=False)
    registration_id = Column(String, nullable=False)
    team_name = Column(String, nullable=False)
    college = Column(String, default="")
    university = Column(String, default="")
    city = Column(String, default="")
    state = Column(String, default="")
    leader_name = Column(String, default="")
    leader_email = Column(String, default="")
    leader_phone = Column(String, default="")
    leader_gender = Column(String, default="")
    leader_course = Column(String, default="")
    leader_branch = Column(String, default="")
    leader_year = Column(String, default="")
    selected_problem_id = Column(String, nullable=True)
    selected_problem_title = Column(String, nullable=True)
    members_data = Column(Text, default="[]") # Full JSON of 6 members
    payment_data = Column(Text, default="{}") # Full JSON of payment details
    deleted_by_admin = Column(String, default="Admin")
    deleted_by_email = Column(String, default="")
    deleted_at = Column(String, default=utc_now)
    reason = Column(String, default="Admin Deletion")

