"""
Populates incidents.db with realistic mock fintech incidents so the platform
is demoable immediately after setup. Safe to re-run: it wipes and recreates
the three tables first.

Usage: python seed_data.py
"""

from datetime import datetime, timedelta, timezone

from app import DB_PATH, init_db
import sqlite3


def iso(dt):
    return dt.isoformat(timespec="seconds")


def main():
    init_db()
    db = sqlite3.connect(DB_PATH)
    db.execute("DELETE FROM reports")
    db.execute("DELETE FROM timeline_entries")
    db.execute("DELETE FROM incidents")
    db.commit()

    now = datetime.now(timezone.utc)

    incidents = [
        dict(
            incident_type="Suspicious Transaction",
            days_ago=1, hours_ago=3,
            description=(
                "Automated fraud model flagged a burst of 14 outbound transfers "
                "from a single merchant account within 6 minutes, each just under "
                "the manual-review threshold. Destination accounts were opened "
                "in the last 48 hours."
            ),
            initial_severity="Critical",
            reporter="R. Fatima (Fraud Ops)",
            status="Investigating",
            timeline=[
                (2.9, "R. Fatima (Fraud Ops)", "Account frozen pending review.", "note"),
                (2.5, "R. Fatima (Fraud Ops)", "Confirmed structuring pattern; escalated to compliance.", "note"),
            ],
        ),
        dict(
            incident_type="Unauthorized Access",
            days_ago=4, hours_ago=1,
            description=(
                "Admin panel login succeeded from an unrecognized IP in a country "
                "the account owner has never logged in from, immediately after 6 "
                "failed attempts from a different IP."
            ),
            initial_severity="High",
            reporter="M. Anwar (SOC)",
            status="Resolved",
            timeline=[
                (3.8, "M. Anwar (SOC)", "Session revoked, password reset forced.", "note"),
                (3.7, "M. Anwar (SOC)", "MFA re-enrolled. No downstream changes found in audit log.", "note"),
                (3.5, "M. Anwar (SOC)", "Status changed from Investigating to Resolved.", "status_change"),
            ],
        ),
        dict(
            incident_type="Phishing",
            days_ago=6, hours_ago=5,
            description=(
                "Multiple customer support tickets reporting an SMS impersonating "
                "our OTP sender ID, linking to a lookalike login page collecting "
                "card numbers."
            ),
            initial_severity="High",
            reporter="S. Khan (Support Lead)",
            status="Resolved",
            timeline=[
                (5.9, "S. Khan (Support Lead)", "Takedown request filed with hosting provider.", "note"),
                (5.5, "S. Khan (Support Lead)", "Customer advisory published in-app.", "note"),
                (5.0, "S. Khan (Support Lead)", "Domain taken offline, confirmed by third party.", "note"),
                (4.9, "S. Khan (Support Lead)", "Status changed from Investigating to Resolved.", "status_change"),
            ],
        ),
        dict(
            incident_type="Failed Authentication",
            days_ago=8, hours_ago=0,
            description=(
                "Rate limiter tripped on the login endpoint: ~4,000 failed attempts "
                "across 300 distinct usernames from a narrow IP range, consistent "
                "with credential stuffing using a leaked password list."
            ),
            initial_severity="Medium",
            reporter="A. Bilal (Platform)",
            status="Closed",
            timeline=[
                (7.8, "A. Bilal (Platform)", "IP range blocked at the edge.", "note"),
                (7.5, "A. Bilal (Platform)", "No accounts compromised; all attempts blocked by MFA or rate limit.", "note"),
                (7.4, "A. Bilal (Platform)", "Status changed from Investigating to Resolved.", "status_change"),
                (7.0, "A. Bilal (Platform)", "Status changed from Resolved to Closed.", "status_change"),
            ],
        ),
        dict(
            incident_type="System Outage",
            days_ago=10, hours_ago=2,
            description=(
                "Payment gateway integration timed out for 22 minutes during a "
                "provider-side deploy, causing failed transaction confirmations "
                "for an estimated 340 users."
            ),
            initial_severity="High",
            reporter="H. Naveed (Infra)",
            status="Closed",
            timeline=[
                (9.9, "H. Naveed (Infra)", "Failover to secondary gateway completed.", "note"),
                (9.8, "H. Naveed (Infra)", "Provider confirmed root cause; incident closed on their side.", "note"),
                (9.7, "H. Naveed (Infra)", "Status changed from Investigating to Resolved.", "status_change"),
                (9.0, "H. Naveed (Infra)", "Status changed from Resolved to Closed.", "status_change"),
            ],
        ),
        dict(
            incident_type="Data Exfiltration",
            days_ago=13, hours_ago=4,
            description=(
                "DLP alert on an internal analyst account: a query result "
                "containing ~1,200 customer records was exported to a personal "
                "cloud storage link outside normal working hours."
            ),
            initial_severity="Critical",
            reporter="R. Fatima (Fraud Ops)",
            status="Resolved",
            timeline=[
                (12.9, "R. Fatima (Fraud Ops)", "Account access suspended, link revoked at source.", "note"),
                (12.7, "R. Fatima (Fraud Ops)", "Confirmed with analyst: sanctioned backup for a manager-approved audit, but done through an unapproved channel.", "note"),
                (12.5, "R. Fatima (Fraud Ops)", "Policy reminder issued; approved export tooling identified for future use.", "note"),
                (12.0, "R. Fatima (Fraud Ops)", "Status changed from Investigating to Resolved.", "status_change"),
            ],
        ),
        dict(
            incident_type="Insider Threat",
            days_ago=16, hours_ago=1,
            description=(
                "Support agent accessed 40+ customer accounts with no associated "
                "open tickets over a two-day period, flagged by the access-pattern "
                "anomaly job."
            ),
            initial_severity="Medium",
            reporter="M. Anwar (SOC)",
            status="Investigating",
            timeline=[
                (15.9, "M. Anwar (SOC)", "HR and legal looped in per policy.", "note"),
                (15.5, "M. Anwar (SOC)", "Access temporarily restricted to ticket-linked accounts only.", "note"),
            ],
        ),
        dict(
            incident_type="Suspicious Transaction",
            days_ago=19, hours_ago=6,
            description=(
                "Chargeback rate on a single merchant category spiked to 9x "
                "baseline over 48 hours, concentrated on newly onboarded "
                "merchant accounts."
            ),
            initial_severity="Medium",
            reporter="R. Fatima (Fraud Ops)",
            status="Closed",
            timeline=[
                (18.5, "R. Fatima (Fraud Ops)", "Merchant category placed on manual review.", "note"),
                (18.0, "R. Fatima (Fraud Ops)", "Three merchant accounts terminated for policy violations.", "note"),
                (17.8, "R. Fatima (Fraud Ops)", "Status changed from Investigating to Resolved.", "status_change"),
                (17.0, "R. Fatima (Fraud Ops)", "Status changed from Resolved to Closed.", "status_change"),
            ],
        ),
        dict(
            incident_type="Malware/Ransomware",
            days_ago=22, hours_ago=2,
            description=(
                "Endpoint protection quarantined a macro-enabled attachment on a "
                "finance team workstation before execution; attachment arrived "
                "via a spoofed vendor invoice email."
            ),
            initial_severity="Low",
            reporter="A. Bilal (Platform)",
            status="Closed",
            timeline=[
                (21.9, "A. Bilal (Platform)", "Workstation isolated and reimaged as precaution.", "note"),
                (21.5, "A. Bilal (Platform)", "No lateral movement found. Vendor contact list updated with verified sender domain.", "note"),
                (21.3, "A. Bilal (Platform)", "Status changed from Investigating to Resolved.", "status_change"),
                (21.0, "A. Bilal (Platform)", "Status changed from Resolved to Closed.", "status_change"),
            ],
        ),
    ]

    for inc in incidents:
        discovery = now - timedelta(days=inc["days_ago"], hours=inc["hours_ago"])
        cur = db.execute(
            """INSERT INTO incidents
               (incident_type, discovery_time, description, severity, initial_severity,
                reporter, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                inc["incident_type"],
                iso(discovery),
                inc["description"],
                inc["initial_severity"],
                inc["initial_severity"],
                inc["reporter"],
                "Open",  # placeholder, corrected below once we know current severity
                iso(discovery),
            ),
        )
        incident_id = cur.lastrowid

        db.execute(
            "INSERT INTO timeline_entries (incident_id, author, note, entry_type, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (incident_id, inc["reporter"],
             f"Incident reported. Initial severity set to {inc['initial_severity']}.",
             "system", iso(discovery)),
        )
        # first status transition for anything not still Open
        if inc["status"] != "Open":
            db.execute(
                "INSERT INTO timeline_entries (incident_id, author, note, entry_type, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (incident_id, inc["reporter"], "Status changed from Open to Investigating.",
                 "status_change", iso(discovery + timedelta(minutes=15))),
            )

        for hours_before_now, author, note, entry_type in inc["timeline"]:
            ts = now - timedelta(hours=hours_before_now)
            db.execute(
                "INSERT INTO timeline_entries (incident_id, author, note, entry_type, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (incident_id, author, note, entry_type, iso(ts)),
            )

        db.execute("UPDATE incidents SET status = ? WHERE id = ?", (inc["status"], incident_id))

    db.commit()
    db.close()
    print(f"Seeded {len(incidents)} mock incidents into {DB_PATH}")


if __name__ == "__main__":
    main()
