"""
email_service.py — backend/services/email_service.py
Gmail SMTP email notification service for MotorInsure AI

Setup (one-time, ~5 min):
  1. Go to your Google Account → Security → 2-Step Verification → turn ON
  2. Then go to: https://myaccount.google.com/apppasswords
  3. Create an App Password → select "Mail" → copy the 16-character password
  4. Set environment variables (or fill constants below for dev/demo):
       EMAIL_SENDER   = "yourname@gmail.com"
       EMAIL_PASSWORD = "abcd efgh ijkl mnop"   ← 16-char App Password (spaces OK)

Non-blocking: if credentials are not configured the send is skipped silently —
policy/renewal flow always completes regardless.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ── Credentials ────────────────────────────────────────────────────────────────
EMAIL_SENDER   = os.getenv("EMAIL_SENDER",   "sanuthi.research.sliit@gmail.com")   
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "ckbs bbqt szkw ogbv")   
SMTP_HOST      = "smtp.gmail.com"
SMTP_PORT      = 587


# ── Core send ──────────────────────────────────────────────────────────────────

def _send_email(to_email: str, subject: str, html_body: str) -> dict:
    """Send an HTML email via Gmail SMTP. Returns {"sent": bool, ...}."""
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        msg = ("Gmail not configured — set EMAIL_SENDER and EMAIL_PASSWORD "
               "environment variables (use a Gmail App Password, not your login password)")
        print(f"[Email] SKIP — {msg}")
        return {"sent": False, "error": msg}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"ABC Motor Insurance <{EMAIL_SENDER}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD.replace(" ", ""))
            server.sendmail(EMAIL_SENDER, to_email, msg.as_string())

        print(f"[Email] ✓ Sent  to={to_email}  subject={subject!r}")
        return {"sent": True, "to": to_email}
    except smtplib.SMTPAuthenticationError:
        err = ("Gmail authentication failed — make sure you used an App Password "
               "(not your Gmail login password). See: myaccount.google.com/apppasswords")
        print(f"[Email] ✗ {err}")
        return {"sent": False, "error": err}
    except Exception as e:
        print(f"[Email] ✗ Send failed: {e}")
        return {"sent": False, "error": str(e)}


# ── Risk helpers ───────────────────────────────────────────────────────────────

def _risk_color(score) -> str:
    if score is None: return "#64748b"
    s = int(score)
    if s < 25: return "#16a34a"
    if s < 50: return "#f59e0b"
    if s < 70: return "#ea580c"
    return "#dc2626"

def _risk_label(score) -> str:
    if score is None: return "N/A"
    s = int(score)
    if s < 25: return "Low Risk"
    if s < 50: return "Moderate Risk"
    if s < 70: return "High Risk"
    return "Very High Risk"

def _shap_rows(drivers: list) -> str:
    if not drivers: return ""
    rows = ""
    for d in drivers[:4]:
        is_risk  = d.get("direction") == "increases_risk"
        arrow    = "▲" if is_risk else "▼"
        color    = "#dc2626" if is_risk else "#16a34a"
        bar_pct  = 75 if d.get("magnitude") == "high" else 45 if d.get("magnitude") == "medium" else 20
        feature  = str(d.get("feature", "")).replace("_", " ")
        reason   = d.get("reason", "")
        shap_val = float(d.get("shap_value", 0))
        rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;width:36px;
                     font-size:16px;color:{color};text-align:center">{arrow}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9">
            <div style="font-weight:600;font-size:13px;color:#0f172a;margin-bottom:4px">{feature}</div>
            <div style="font-size:11px;color:#64748b;margin-bottom:6px">{reason}</div>
            <div style="height:5px;background:#f1f5f9;border-radius:3px">
              <div style="height:5px;width:{bar_pct}%;background:{color};border-radius:3px"></div>
            </div>
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;
                     font-family:monospace;font-size:12px;color:{color};
                     text-align:right;white-space:nowrap">
            {'+' if shap_val > 0 else ''}{shap_val:.3f}
          </td>
        </tr>"""
    return rows


# ── HTML templates ─────────────────────────────────────────────────────────────

def _base_template(title: str, content: str) -> str:
    year = datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 0">
    <tr><td align="center">
      <table width="620" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:16px;overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,0,0,.08);max-width:620px">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#0f4c81 0%,#1a7a4a 100%);
                     padding:32px 40px;text-align:center">
            <div style="font-size:28px;margin-bottom:6px">🏍</div>
            <div style="color:#ffffff;font-size:22px;font-weight:700;
                        letter-spacing:-.3px">ABC Motor Insurance</div>
            <div style="color:#bfdbfe;font-size:13px;margin-top:4px">
              AI-Powered Risk-Based Premium System · Sri Lanka
            </div>
          </td>
        </tr>

        <!-- Content -->
        <tr><td style="padding:36px 40px">{content}</td></tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f8fafc;padding:24px 40px;border-top:1px solid #e2e8f0;
                     text-align:center">
            <div style="font-size:12px;color:#94a3b8;line-height:1.7">
              This is an automated confirmation from <strong>ABC Motor Insurance</strong>.<br>
              Please keep this email as proof of your policy registration.<br>
              For queries: <a href="mailto:info@abcinsurance.lk"
                style="color:#0f4c81;text-decoration:none">info@abcinsurance.lk</a>
              &nbsp;|&nbsp; +94 11 234 5678<br>
              <span style="color:#cbd5e1">© {year} ABC Motor Insurance. All rights reserved.</span>
            </div>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def build_policy_html(
    customer_name: str,
    policy_id: str,
    vehicle_model: str,
    vehicle_type: str,
    gross_premium: float,
    net_premium: float,
    stamp_duty: float,
    vat: float,
    cess: float,
    risk_score,
    ncb_pct: float,
    start_date: str,
    end_date: str,
    risk_label: str = "",
    shap_drivers: list = None,
) -> str:
    first      = str(customer_name).strip().split()[0] if customer_name else "Customer"
    r_color    = _risk_color(risk_score)
    r_label    = _risk_label(risk_score)
    shap_section = ""
    if shap_drivers:
        shap_section = f"""
        <div style="margin-top:28px">
          <div style="font-size:14px;font-weight:700;color:#0f172a;margin-bottom:14px">
            🧠 AI Risk Drivers <span style="font-size:11px;font-weight:400;color:#64748b;
            background:#f0f9ff;padding:2px 8px;border-radius:10px;margin-left:6px">
            Interventional SHAP</span>
          </div>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
            {_shap_rows(shap_drivers)}
          </table>
          <p style="font-size:11px;color:#94a3b8;margin-top:8px">
            SHAP values show each feature's contribution to your risk score
            relative to the average policyholder.
          </p>
        </div>"""

    content = f"""
      <!-- Greeting -->
      <div style="margin-bottom:24px">
        <div style="font-size:20px;font-weight:700;color:#0f172a;margin-bottom:6px">
          ✅ Policy Confirmed, {first}!
        </div>
        <p style="color:#64748b;font-size:14px;margin:0;line-height:1.6">
          Your motor insurance policy has been successfully registered with
          ABC Insurance. Please keep this confirmation for your records.
        </p>
      </div>

      <!-- Policy ID badge -->
      <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;
                  padding:16px 20px;margin-bottom:24px;text-align:center">
        <div style="font-size:11px;color:#3b82f6;font-weight:600;
                    text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">
          Policy Number
        </div>
        <div style="font-size:26px;font-weight:800;color:#0f4c81;
                    font-family:monospace;letter-spacing:2px">{policy_id}</div>
        <div style="font-size:12px;color:#64748b;margin-top:4px">
          Valid: {start_date} &nbsp;→&nbsp; {end_date}
        </div>
      </div>

      <!-- Two-column: Vehicle + Risk -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px">
        <tr>
          <!-- Vehicle -->
          <td width="48%" valign="top"
              style="background:#f8fafc;border-radius:10px;padding:16px 18px;
                     border:1px solid #e2e8f0">
            <div style="font-size:11px;font-weight:700;color:#64748b;
                        text-transform:uppercase;letter-spacing:.8px;margin-bottom:12px">
              🚗 Vehicle Details
            </div>
            <div style="font-size:14px;font-weight:700;color:#0f172a;margin-bottom:4px">
              {vehicle_model}
            </div>
            <div style="font-size:12px;color:#64748b">{vehicle_type} · Comprehensive Cover</div>
          </td>
          <td width="4%"></td>
          <!-- Risk Score -->
          <td width="48%" valign="top"
              style="background:#f8fafc;border-radius:10px;padding:16px 18px;
                     border:1px solid #e2e8f0;text-align:center">
            <div style="font-size:11px;font-weight:700;color:#64748b;
                        text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px">
              🛡 AI Risk Score
            </div>
            <div style="font-size:42px;font-weight:800;color:{r_color};
                        line-height:1">{risk_score if risk_score is not None else '—'}</div>
            <div style="font-size:12px;font-weight:600;color:{r_color};
                        margin-top:4px">{r_label}</div>
            <div style="font-size:11px;color:#94a3b8;margin-top:4px">
              NCB Applied: {int(ncb_pct)}%
            </div>
          </td>
        </tr>
      </table>

      <!-- Premium breakdown -->
      <div style="margin-bottom:24px">
        <div style="font-size:14px;font-weight:700;color:#0f172a;margin-bottom:12px">
          💰 Premium Breakdown
        </div>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
          <tr style="background:#f8fafc">
            <td style="padding:10px 16px;font-size:13px;color:#475569;
                       border-bottom:1px solid #f1f5f9">Net Premium</td>
            <td style="padding:10px 16px;font-size:13px;color:#0f172a;font-weight:600;
                       text-align:right;border-bottom:1px solid #f1f5f9">
              LKR {int(net_premium):,}</td>
          </tr>
          <tr>
            <td style="padding:10px 16px;font-size:13px;color:#475569;
                       border-bottom:1px solid #f1f5f9">Stamp Duty (1%)</td>
            <td style="padding:10px 16px;font-size:13px;color:#0f172a;
                       text-align:right;border-bottom:1px solid #f1f5f9">
              LKR {int(stamp_duty):,}</td>
          </tr>
          <tr style="background:#f8fafc">
            <td style="padding:10px 16px;font-size:13px;color:#475569;
                       border-bottom:1px solid #f1f5f9">VAT (8%)</td>
            <td style="padding:10px 16px;font-size:13px;color:#0f172a;
                       text-align:right;border-bottom:1px solid #f1f5f9">
              LKR {int(vat):,}</td>
          </tr>
          <tr>
            <td style="padding:10px 16px;font-size:13px;color:#475569;
                       border-bottom:1px solid #e2e8f0">CESS (0.5%)</td>
            <td style="padding:10px 16px;font-size:13px;color:#0f172a;
                       text-align:right;border-bottom:1px solid #e2e8f0">
              LKR {int(cess):,}</td>
          </tr>
          <tr style="background:linear-gradient(90deg,#0f4c81 0%,#1a6fa0 100%)">
            <td style="padding:14px 16px;font-size:14px;font-weight:700;color:#ffffff">
              Gross Total
            </td>
            <td style="padding:14px 16px;font-size:18px;font-weight:800;
                       color:#ffffff;text-align:right">
              LKR {int(gross_premium):,}
            </td>
          </tr>
        </table>
      </div>
      {shap_section}"""

    return _base_template(f"Policy Confirmation — {policy_id}", content)


def build_renewal_html(
    customer_name: str,
    policy_id: str,
    renewal_id: str,
    vehicle_model: str,
    renewal_premium: float,
    previous_premium: float,
    pct_change: float,
    new_ncb: float,
    risk_score,
    risk_label: str,
    start_date: str,
    end_date: str,
    recommendation: str = "APPROVE",
    shap_drivers: list = None,
) -> str:
    first    = str(customer_name).strip().split()[0] if customer_name else "Customer"
    r_color  = _risk_color(risk_score)
    r_label  = _risk_label(risk_score)
    chg_sign = "+" if pct_change >= 0 else ""
    chg_col  = "#dc2626" if pct_change > 5 else "#16a34a" if pct_change < 0 else "#f59e0b"
    rec_col  = "#16a34a" if recommendation == "APPROVE" else "#f59e0b"
    rec_icon = "✅" if recommendation == "APPROVE" else "⚠️"

    shap_section = ""
    if shap_drivers:
        shap_section = f"""
        <div style="margin-top:28px">
          <div style="font-size:14px;font-weight:700;color:#0f172a;margin-bottom:14px">
            🧠 AI Risk Drivers <span style="font-size:11px;font-weight:400;color:#64748b;
            background:#f0f9ff;padding:2px 8px;border-radius:10px;margin-left:6px">
            Interventional SHAP</span>
          </div>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
            {_shap_rows(shap_drivers)}
          </table>
        </div>"""

    content = f"""
      <div style="margin-bottom:24px">
        <div style="font-size:20px;font-weight:700;color:#0f172a;margin-bottom:6px">
          🔄 Renewal Confirmed, {first}!
        </div>
        <p style="color:#64748b;font-size:14px;margin:0;line-height:1.6">
          Your motor insurance policy has been successfully renewed.
          Your coverage continues without interruption.
        </p>
      </div>

      <!-- IDs -->
      <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;
                  padding:16px 20px;margin-bottom:24px">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="text-align:center;border-right:1px solid #bfdbfe;padding-right:20px">
              <div style="font-size:11px;color:#3b82f6;font-weight:600;
                          text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">
                Policy Number</div>
              <div style="font-size:18px;font-weight:800;color:#0f4c81;
                          font-family:monospace">{policy_id}</div>
            </td>
            <td style="text-align:center;padding-left:20px">
              <div style="font-size:11px;color:#3b82f6;font-weight:600;
                          text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">
                Renewal ID</div>
              <div style="font-size:18px;font-weight:800;color:#0f4c81;
                          font-family:monospace">{renewal_id}</div>
            </td>
          </tr>
        </table>
        <div style="text-align:center;font-size:12px;color:#64748b;margin-top:12px;
                    border-top:1px solid #bfdbfe;padding-top:10px">
          Valid Period: <strong>{start_date}</strong> → <strong>{end_date}</strong>
        </div>
      </div>

      <!-- Vehicle + Risk -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px">
        <tr>
          <td width="48%" valign="top"
              style="background:#f8fafc;border-radius:10px;padding:16px 18px;
                     border:1px solid #e2e8f0">
            <div style="font-size:11px;font-weight:700;color:#64748b;
                        text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px">
              🚗 Vehicle</div>
            <div style="font-size:14px;font-weight:700;color:#0f172a">{vehicle_model}</div>
            <div style="font-size:12px;color:#64748b;margin-top:4px">
              New NCB: <strong>{int(new_ncb)}%</strong>
            </div>
          </td>
          <td width="4%"></td>
          <td width="48%" valign="top"
              style="background:#f8fafc;border-radius:10px;padding:16px 18px;
                     border:1px solid #e2e8f0;text-align:center">
            <div style="font-size:11px;font-weight:700;color:#64748b;
                        text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px">
              🛡 Risk Score</div>
            <div style="font-size:38px;font-weight:800;color:{r_color};
                        line-height:1">{risk_score if risk_score is not None else '—'}</div>
            <div style="font-size:12px;font-weight:600;color:{r_color};margin-top:3px">
              {r_label}</div>
            <div style="font-size:11px;color:{rec_col};font-weight:600;margin-top:6px">
              {rec_icon} {recommendation}</div>
          </td>
        </tr>
      </table>

      <!-- Premium comparison -->
      <div style="margin-bottom:24px">
        <div style="font-size:14px;font-weight:700;color:#0f172a;margin-bottom:12px">
          💰 Premium Summary
        </div>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
          <tr style="background:#f8fafc">
            <td style="padding:10px 16px;font-size:13px;color:#475569;
                       border-bottom:1px solid #f1f5f9">Previous Premium</td>
            <td style="padding:10px 16px;font-size:13px;color:#0f172a;
                       text-align:right;border-bottom:1px solid #f1f5f9">
              LKR {int(previous_premium):,}</td>
          </tr>
          <tr>
            <td style="padding:10px 16px;font-size:13px;color:#475569;
                       border-bottom:1px solid #e2e8f0">Change</td>
            <td style="padding:10px 16px;font-size:13px;font-weight:600;
                       color:{chg_col};text-align:right;border-bottom:1px solid #e2e8f0">
              {chg_sign}{pct_change:.1f}%</td>
          </tr>
          <tr style="background:linear-gradient(90deg,#0f4c81 0%,#1a6fa0 100%)">
            <td style="padding:14px 16px;font-size:14px;font-weight:700;color:#ffffff">
              Renewal Premium</td>
            <td style="padding:14px 16px;font-size:18px;font-weight:800;
                       color:#ffffff;text-align:right">
              LKR {int(renewal_premium):,}</td>
          </tr>
        </table>
      </div>
      {shap_section}"""

    return _base_template(f"Renewal Confirmation — {policy_id}", content)


# ── Public API ─────────────────────────────────────────────────────────────────

def send_policy_email(email: str, **kwargs) -> dict:
    """Send new policy HTML confirmation email. Never raises."""
    if not email or "@" not in str(email):
        return {"sent": False, "error": "No valid email address"}
    try:
        html    = build_policy_html(**kwargs)
        subject = f"Policy Confirmed — {kwargs.get('policy_id','')} | ABC Motor Insurance"
        return _send_email(email, subject, html)
    except Exception as e:
        print(f"[Email] send_policy_email error: {e}")
        return {"sent": False, "error": str(e)}


def send_renewal_email(email: str, **kwargs) -> dict:
    """Send renewal HTML confirmation email. Never raises."""
    if not email or "@" not in str(email):
        return {"sent": False, "error": "No valid email address"}
    try:
        html    = build_renewal_html(**kwargs)
        subject = f"Renewal Confirmed — {kwargs.get('policy_id','')} | ABC Motor Insurance"
        return _send_email(email, subject, html)
    except Exception as e:
        print(f"[Email] send_renewal_email error: {e}")
        return {"sent": False, "error": str(e)}
