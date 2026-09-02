import os
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH = os.path.join(BASE_DIR, "SIH Logo.png")
if not os.path.exists(LOGO_PATH):
    PARENT_DIR = os.path.dirname(BASE_DIR)
    LOGO_CANDIDATE = os.path.join(PARENT_DIR, "SIH Logo.png")
    if os.path.exists(LOGO_CANDIDATE):
        LOGO_PATH = LOGO_CANDIDATE
    else:
        LOGO_PATH = None

# Custom Colors
NAVY = colors.HexColor("#0f172a")        # Deep slate / navy
ROYAL_BLUE = colors.HexColor("#1e3a8a")  # Deep blue
GOLD = colors.HexColor("#d97706")        # Rich amber gold
MUTED = colors.HexColor("#475569")       # Slate 600
BG_IVORY = colors.HexColor("#fefdfb")    # Clean ivory parchment tint

def draw_luxury_border(c, width, height):
    """Draw a rich, double-line ornate certificate border with corner rosettes."""
    c.saveState()
    
    # Outer background
    c.setFillColor(BG_IVORY)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    
    # Outer primary border
    c.setStrokeColor(ROYAL_BLUE)
    c.setLineWidth(4)
    c.rect(20, 20, width - 40, height - 40, fill=0, stroke=1)
    
    # Inner gold border
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.rect(26, 26, width - 52, height - 52, fill=0, stroke=1)
    
    # Thin subtle frame
    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.setLineWidth(0.5)
    c.rect(32, 32, width - 64, height - 64, fill=0, stroke=1)
    
    # Corner Ornaments (Top-Left, Top-Right, Bottom-Left, Bottom-Right)
    corners = [
        (26, 26),
        (width - 26, 26),
        (26, height - 26),
        (width - 26, height - 26)
    ]
    c.setFillColor(GOLD)
    for cx, cy in corners:
        c.circle(cx, cy, 5, fill=1, stroke=0)
        c.setStrokeColor(ROYAL_BLUE)
        c.setLineWidth(0.8)
        c.circle(cx, cy, 9, fill=0, stroke=1)
    
    # Subtle background watermark logo if exists
    if LOGO_PATH and os.path.exists(LOGO_PATH):
        try:
            c.saveState()
            if hasattr(c, "setFillAlpha"):
                c.setFillAlpha(0.06)
            wm_w = 340
            wm_h = 170
            c.drawImage(
                LOGO_PATH,
                (width - wm_w) / 2.0,
                (height - wm_h) / 2.0,
                width=wm_w,
                height=wm_h,
                mask='auto',
                preserveAspectRatio=True
            )
            c.restoreState()
        except Exception:
            pass
            
    c.restoreState()


TEMPLATE_PATH = os.path.join(BASE_DIR, "sih_official_certificate_template.png")
if not os.path.exists(TEMPLATE_PATH):
    PARENT_DIR = os.path.dirname(BASE_DIR)
    CANDIDATE = os.path.join(PARENT_DIR, "2nd - 3rd.png")
    if os.path.exists(CANDIDATE):
        TEMPLATE_PATH = CANDIDATE
    else:
        TEMPLATE_PATH = None

def generate_single_certificate_bytes(
    student_name: str,
    team_name: str,
    college_name: str = "",
    role: str = "Participant",
    cert_type: str = "Participation",  # Participation / Winner / Finalist / Appreciation
    event_title: str = "Smart India Hackathon 2026 (Internal Hackathon)",
    sign_1_title: str = "Convener / SPOC",
    sign_1_name: str = "SIH Coordinator",
    sign_2_title: str = "Head of Institution",
    sign_2_name: str = "Principal / Director",
    issue_date: str = "September 2026"
) -> bytes:
    """Generate a high-resolution, landscape A4 PDF certificate for a student."""
    buffer = io.BytesIO()
    
    # Landscape A4: 841.89 pt width x 595.27 pt height
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    # Check if user's actual official SIH template image exists
    if TEMPLATE_PATH and os.path.exists(TEMPLATE_PATH):
        # Draw full background template perfectly scaled to A4 Landscape
        c.drawImage(TEMPLATE_PATH, 0, 0, width=width, height=height)
        
        # Center Coordinates for Dynamic Text Overlay
        center_x = width / 2.0
        
        # Participant Full Name (Safely placed clearly below the pre-printed green 'Certificate' script)
        c.setFont("Helvetica-Bold", 24)
        c.setFillColor(colors.HexColor("#1e3a8a"))
        clean_name = (student_name or "Participant Name").upper()
        c.drawCentredString(center_x, 260, clean_name)
        
        # Underline for name
        name_w = min(380, max(220, c.stringWidth(clean_name, "Helvetica-Bold", 24) + 30))
        c.setStrokeColor(colors.HexColor("#ea580c"))
        c.setLineWidth(1.5)
        c.line((width - name_w) / 2.0, 252, (width + name_w) / 2.0, 252)
        
        # Team Name Only (No role, no college)
        team_clean = (team_name or "Participant Team").strip()
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(colors.HexColor("#0f172a"))
        c.drawCentredString(center_x, 230, f"Team:  \"{team_clean}\"")
        
        # Description
        c.setFont("Helvetica", 10.5)
        c.setFillColor(colors.HexColor("#475569"))
        c.drawCentredString(center_x, 204, "for active innovation, technical excellence, and committed participation")
        c.drawCentredString(center_x, 188, "in the Smart India Hackathon 2026 Internal College Round.")

        
        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer.getvalue()

    # Fallback to luxury canvas border if template image is missing
    draw_luxury_border(c, width, height)
    top_y = height - 60

    if LOGO_PATH and os.path.exists(LOGO_PATH):
        try:
            logo_w = 110
            logo_h = 45
            c.drawImage(
                LOGO_PATH,
                (width - logo_w) / 2.0,
                top_y - 25,
                width=logo_w,
                height=logo_h,
                mask='auto',
                preserveAspectRatio=True
            )
        except Exception:
            pass
    
    # 3. Main Institution / Event Header
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(GOLD)
    c.drawCentredString(width / 2.0, top_y - 42, "GOVERNMENT OF INDIA & AICTE / MIC INITIATIVE")
    
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(ROYAL_BLUE)
    c.drawCentredString(width / 2.0, top_y - 68, event_title.upper())
    
    # 4. Certificate of ... Banner
    c.setFont("Times-BoldItalic", 28)
    c.setFillColor(NAVY)
    title_text = f"CERTIFICATE OF {cert_type.upper()}"
    c.drawCentredString(width / 2.0, top_y - 110, title_text)
    
    # Decorative line under certificate title
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    line_w = 180
    c.line((width - line_w) / 2.0, top_y - 118, (width + line_w) / 2.0, top_y - 118)
    
    # 5. Body - "This is proudly presented to"
    c.setFont("Times-Italic", 13)
    c.setFillColor(MUTED)
    c.drawCentredString(width / 2.0, top_y - 145, "This is proudly presented to")
    
    # 6. Student's Full Name (Large & Bold)
    c.setFont("Helvetica-Bold", 26)
    c.setFillColor(ROYAL_BLUE)
    c.drawCentredString(width / 2.0, top_y - 180, (student_name or "Participant Name").upper())
    
    # Underline for name
    name_w = min(460, max(260, c.stringWidth((student_name or "").upper(), "Helvetica-Bold", 26) + 40))
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line((width - name_w) / 2.0, top_y - 188, (width + name_w) / 2.0, top_y - 188)
    
    # 7. Body Details
    role_text = "as Team Leader" if role.lower() == "leader" else "as Active Team Member"
    team_clean = (team_name or "Participant Team").strip()
    college_clean = (college_name or "").strip()
    
    c.setFont("Helvetica", 12)
    c.setFillColor(NAVY)
    
    line1 = f"of Team  \"{team_clean}\"  {role_text}"
    c.drawCentredString(width / 2.0, top_y - 215, line1)
    
    if college_clean:
        line2 = f"representing {college_clean}"
        c.setFont("Helvetica-Oblique", 11)
        c.setFillColor(MUTED)
        c.drawCentredString(width / 2.0, top_y - 235, line2)
        desc_y = top_y - 265
    else:
        desc_y = top_y - 245
        
    c.setFont("Helvetica", 11)
    c.setFillColor(MUTED)
    line3 = "for exemplary technical innovation, teamwork, and dedicated participation"
    line4 = "in the Smart India Hackathon 2026 Internal College Round."
    c.drawCentredString(width / 2.0, desc_y, line3)
    c.drawCentredString(width / 2.0, desc_y - 18, line4)
    
    # 8. Signatures Section at Bottom
    sig_y = 90
    sig_left_x = 160
    sig_right_x = width - 160
    
    # Left Signature Line
    c.setStrokeColor(NAVY)
    c.setLineWidth(1)
    c.line(sig_left_x - 80, sig_y, sig_left_x + 80, sig_y)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(NAVY)
    c.drawCentredString(sig_left_x, sig_y - 15, sign_1_name)
    c.setFont("Helvetica", 9)
    c.setFillColor(MUTED)
    c.drawCentredString(sig_left_x, sig_y - 28, sign_1_title)
    
    # Center Seal / Date
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(GOLD)
    c.drawCentredString(width / 2.0, sig_y - 5, "★ OFFICIAL MERIT RECORD ★")
    c.setFont("Helvetica", 9)
    c.setFillColor(MUTED)
    c.drawCentredString(width / 2.0, sig_y - 20, f"Issued: {issue_date}")
    
    # Right Signature Line
    c.setStrokeColor(NAVY)
    c.setLineWidth(1)
    c.line(sig_right_x - 80, sig_y, sig_right_x + 80, sig_y)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(NAVY)
    c.drawCentredString(sig_right_x, sig_y - 15, sign_2_name)
    c.setFont("Helvetica", 9)
    c.setFillColor(MUTED)
    c.drawCentredString(sig_right_x, sig_y - 28, sign_2_title)
    
    c.showPage()
    c.save()
    
    buffer.seek(0)
    return buffer.getvalue()


def send_team_certificates_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    from_name: str,
    leader_email: str,
    leader_name: str,
    team_name: str,
    certificate_attachments: list  # list of tuples: (filename, bytes_data)
):
    """
    Send an email via SMTP (Gmail, etc.) with all team certificates attached.
    """
    if not smtp_user or not smtp_pass:
        raise ValueError("SMTP Credentials are not configured.")
        
    msg = MIMEMultipart()
    sender_display = f"{from_name} <{smtp_user}>" if from_name else smtp_user
    msg["From"] = sender_display
    msg["To"] = leader_email
    msg["Subject"] = f"Certificates for Team '{team_name}' - Smart India Hackathon 2026"
    
    # HTML Body
    members_count = len(certificate_attachments)
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; }}
            .card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }}
            .header {{ background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%); color: #ffffff; padding: 28px 24px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 22px; font-weight: 800; letter-spacing: 0.5px; }}
            .header p {{ margin: 6px 0 0 0; color: #fbbf24; font-size: 14px; font-weight: 600; text-transform: uppercase; }}
            .content {{ padding: 28px 24px; color: #334155; line-height: 1.6; font-size: 15px; }}
            .highlight-box {{ background-color: #f1f5f9; border-left: 4px solid #d97706; padding: 14px 18px; border-radius: 6px; margin: 20px 0; }}
            .footer {{ background: #f8fafc; padding: 18px 24px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <h1>Smart India Hackathon 2026</h1>
                <p>Official Participation & Merit Certificates</p>
            </div>
            <div class="content">
                <p>Dear <strong>{leader_name}</strong> (Team Leader),</p>
                <p>Congratulations to you and all members of <strong>Team {team_name}</strong> for your participation and performance in the <strong>Smart India Hackathon 2026 Internal Hackathon</strong>!</p>
                
                <div class="highlight-box">
                    <p style="margin: 0; font-weight: 600; color: #0f172a;">Attached Certificates Package:</p>
                    <p style="margin: 4px 0 0 0; color: #475569;">
                        We have attached <strong>{members_count} official PDF certificates</strong> for all registered members of your team in this email.
                    </p>
                </div>
                
                <p>Please download and forward respective individual certificates to each of your team members.</p>
                
                <p style="margin-top: 24px;">Wishing you the very best in your innovation journey!</p>
                
                <p style="margin-bottom: 0;">Warm regards,<br><strong>SIH 2026 Organizing Committee & Hackathon Cell</strong></p>
            </div>
            <div class="footer">
                This is an automated delivery from the official SIH Hackathon Management Portal.
            </div>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(html_content, "html"))
    
    # Attach all PDFs
    for filename, pdf_bytes in certificate_attachments:
        part = MIMEBase("application", "pdf")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)
        
    # Connect & Send
    use_ssl = (smtp_port == 465)
    if use_ssl:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        server.starttls()
        
    try:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [leader_email], msg.as_string())
    finally:
        server.quit()
