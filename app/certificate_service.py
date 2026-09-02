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


TEMPLATE_PATH = os.path.join(BASE_DIR, "sih_spiderman_certificate_2026.png")
if not os.path.exists(TEMPLATE_PATH):
    FALLBACK = os.path.join(BASE_DIR, "sih_official_certificate_template.png")
    if os.path.exists(FALLBACK):
        TEMPLATE_PATH = FALLBACK
    else:
        PARENT_DIR = os.path.dirname(BASE_DIR)
        CANDIDATE = os.path.join(PARENT_DIR, "2nd - 3rd (2).png")
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
        
        # Dynamic Font Scaling for Long Names
        clean_name = (student_name or "Participant Name").upper()
        name_len = len(clean_name)
        
        if name_len > 28:
            name_font_size = 17
            underline_offset = 5
        elif name_len > 22:
            name_font_size = 19
            underline_offset = 6
        elif name_len > 16:
            name_font_size = 22
            underline_offset = 7
        else:
            name_font_size = 25
            underline_offset = 8
            
        c.setFont("Helvetica-Bold", name_font_size)
        c.setFillColor(colors.HexColor("#1e3a8a"))
        c.drawCentredString(center_x, 258, clean_name)
        
        # Underline for name scaled proportionally
        name_str_w = c.stringWidth(clean_name, "Helvetica-Bold", name_font_size)
        name_w = min(420, max(180, name_str_w + 24))
        c.setStrokeColor(colors.HexColor("#ea580c"))
        c.setLineWidth(1.5)
        c.line((width - name_w) / 2.0, 258 - underline_offset, (width + name_w) / 2.0, 258 - underline_offset)

        
        # Elegant Team Representation
        team_clean = (team_name or "Participant Team").strip()
        
        # 'of' in italic serif muted, Team Name in bold deep slate
        c.setFont("Times-Italic", 13)
        c.setFillColor(colors.HexColor("#475569"))
        of_w = c.stringWidth("of Team  ", "Times-Italic", 13)
        
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.HexColor("#0f172a"))
        name_part_w = c.stringWidth(team_clean, "Helvetica-Bold", 14)
        
        total_team_w = of_w + name_part_w
        start_team_x = center_x - (total_team_w / 2.0)
        
        # Draw "of Team"
        c.setFont("Times-Italic", 13)
        c.setFillColor(colors.HexColor("#475569"))
        c.drawString(start_team_x, 226, "of Team  ")
        
        # Draw "TeamName"
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.HexColor("#0f172a"))
        c.drawString(start_team_x + of_w, 226, team_clean)
        
        # Decorative micro dots around team
        c.setFillColor(colors.HexColor("#ea580c"))
        c.circle(start_team_x - 14, 230, 2, fill=1, stroke=0)
        c.circle(start_team_x + total_team_w + 14, 230, 2, fill=1, stroke=0)
        
        # Description
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor("#64748b"))
        c.drawCentredString(center_x, 198, "for active innovation, technical excellence, and committed participation")
        c.drawCentredString(center_x, 183, "in the Smart India Hackathon 2026 Internal College Round.")


        
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
    Send an email via SMTP (Gmail, etc.) with all team certificates (or single member certificate) attached.
    """
    if not smtp_user or not smtp_pass:
        raise ValueError("SMTP Credentials are not configured.")
        
    msg = MIMEMultipart()
    sender_display = f"{from_name} <{smtp_user}>" if from_name else smtp_user
    msg["From"] = sender_display
    msg["To"] = leader_email
    
    members_count = len(certificate_attachments)
    is_single = (members_count == 1)

    if is_single:
        msg["Subject"] = f"Official Certificate for {leader_name} • Smart India Hackathon 2026"
        greeting = f"Dear <strong>{leader_name}</strong>,"
        congrats_text = f"Congratulations on your outstanding participation, technical excellence, and dedication representing <strong>Team {team_name}</strong> in the <strong>Smart India Hackathon 2026 Internal College Round</strong>!"
        package_box = f"""
        <div class="highlight-box">
            <p style="margin: 0; font-weight: 700; color: #0f172a; font-size: 15px;">Official Certificate Attached:</p>
            <p style="margin: 4px 0 0 0; color: #475569; font-size: 14px;">
                Your verified, high-resolution A4 digital certificate <strong>({certificate_attachments[0][0]})</strong> is attached to this email. You can download and keep it for your academic and career portfolio.
            </p>
        </div>
        """
        extra_note = ""
    else:
        msg["Subject"] = f"Official Team Certificates Package: Team '{team_name}' • Smart India Hackathon 2026"
        greeting = f"Dear <strong>{leader_name}</strong> (Team Leader),"
        congrats_text = f"Congratulations to you and all members of <strong>Team {team_name}</strong> for your innovative technical project and performance in the <strong>Smart India Hackathon 2026 Internal College Round</strong>!"
        package_box = f"""
        <div class="highlight-box">
            <p style="margin: 0; font-weight: 700; color: #0f172a; font-size: 15px;">Complete Team Certificate Package:</p>
            <p style="margin: 4px 0 0 0; color: #475569; font-size: 14px;">
                We have attached all <strong>{members_count} official PDF certificates</strong> for every registered member of your team in this single email.
            </p>
        </div>
        """
        extra_note = "<p style='color: #475569; font-size: 14px;'>Please forward the respective individual PDF certificates to each of your team members.</p>"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; background-color: #f1f5f9; margin: 0; padding: 24px; }}
            .card {{ max-width: 620px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; }}
            .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #ea580c 100%); color: #ffffff; padding: 32px 24px; text-align: center; }}
            .badge {{ display: inline-block; background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.3); padding: 4px 14px; border-radius: 9999px; font-size: 11px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; color: #fbbf24; margin-bottom: 10px; }}
            .header h1 {{ margin: 0; font-size: 24px; font-weight: 900; letter-spacing: 0.5px; color: #ffffff; }}
            .header p {{ margin: 6px 0 0 0; color: #e2e8f0; font-size: 13px; font-weight: 500; }}
            .content {{ padding: 32px 28px; color: #334155; line-height: 1.65; font-size: 15px; }}
            .highlight-box {{ background-color: #f8fafc; border-left: 4px solid #ea580c; padding: 16px 20px; border-radius: 8px; margin: 22px 0; border-top: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; }}
            .footer {{ background: #f8fafc; padding: 20px 24px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <span class="badge">Official Recognition</span>
                <h1>Smart India Hackathon 2026</h1>
                <p>Internal Hackathon Round • Ministry of Education & AICTE Initiative</p>
            </div>
            <div class="content">
                <p style="font-size: 16px;">{greeting}</p>
                <p>{congrats_text}</p>
                
                {package_box}
                
                {extra_note}
                
                <p style="margin-top: 24px;">Wishing you endless success and innovation in your future hackathons!</p>
                
                <div style="margin-top: 28px; padding-top: 18px; border-top: 1px dashed #cbd5e1;">
                    <p style="margin: 0; font-weight: 700; color: #0f172a; font-size: 14px;">SIH 2026 Organizing Committee</p>
                    <p style="margin: 2px 0 0 0; color: #64748b; font-size: 12px;">Hackathon Management & Innovation Cell</p>
                </div>
            </div>
            <div class="footer">
                This is an automated certificate dispatch from the official SIH 2026 Portal.
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

