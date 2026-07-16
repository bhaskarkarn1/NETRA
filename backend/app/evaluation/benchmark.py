"""
NETRA Evaluation Benchmark — Detection Accuracy Metrics

This script evaluates NETRA's scam detection accuracy against a curated
test dataset of 30 scam + 30 benign messages with ground-truth labels.

Metrics computed:
- Precision (true positives / predicted positives)
- Recall (true positives / actual positives)
- F1 Score (harmonic mean of precision & recall)
- Per-category accuracy
- Confusion matrix

Usage:
    python -m app.evaluation.benchmark

Requires: Running backend server on localhost:8000
"""

import asyncio
import json
import time
from dataclasses import dataclass

# ---------- Ground-Truth Test Dataset ----------

@dataclass
class TestCase:
    text: str
    is_scam: bool
    expected_type: str | None  # Expected scam_type, None for benign
    category: str  # For grouping accuracy


EVALUATION_DATASET: list[TestCase] = [
    # ===== SCAM MESSAGES (30) =====

    # Digital Arrest (5)
    TestCase(
        text="Hello, this is CBI Officer Sharma. Your Aadhaar number has been used to open 17 bank accounts for money laundering. We have an arrest warrant ready. You must verify your identity RIGHT NOW or face immediate arrest. Do NOT disconnect this call or tell anyone.",
        is_scam=True, expected_type="Digital Arrest", category="digital_arrest",
    ),
    TestCase(
        text="Sir, I am calling from Mumbai Cyber Crime Branch. Your name has appeared in a money laundering case. A non-bailable warrant has been issued. You must transfer Rs 2,50,000 as security deposit to clear your name. Stay on the line.",
        is_scam=True, expected_type="Digital Arrest", category="digital_arrest",
    ),
    TestCase(
        text="This is Inspector Patel from Delhi Police Cyber Cell. We have intercepted a parcel containing drugs and fake passports linked to your phone number. You are under digital surveillance. Pay the fine now or we will arrest you within 2 hours.",
        is_scam=True, expected_type="Digital Arrest", category="digital_arrest",
    ),
    TestCase(
        text="Madam, TRAI has found that your mobile number 98xxxxx321 is involved in sending abusive messages. Your number will be blocked in 2 hours. Press 1 to speak to the officer or face legal action.",
        is_scam=True, expected_type="Digital Arrest", category="digital_arrest",
    ),
    TestCase(
        text="I am Sub Inspector Verma. Your son has been detained at the police station for a narcotics case. To get him released on bail immediately, transfer Rs 50,000 to this account: A/C 3456789012, IFSC: SBIN0001234.",
        is_scam=True, expected_type="Digital Arrest", category="digital_arrest",
    ),

    # UPI/Payment Fraud (5)
    TestCase(
        text="Congratulations! You have won Rs 10 Lakh in Flipkart Lucky Draw. To claim your prize, pay Rs 999 processing fee via UPI to lucky.draw@ybl. Offer valid for 30 minutes only!",
        is_scam=True, expected_type="UPI/Payment Fraud", category="upi_fraud",
    ),
    TestCase(
        text="Dear customer, your SBI account has been temporarily blocked due to KYC expiry. Click here to update your KYC immediately: http://sbi-kyc-update.xyz/verify or your account will be permanently closed.",
        is_scam=True, expected_type="KYC Fraud", category="upi_fraud",
    ),
    TestCase(
        text="I sent you Rs 5000 extra by mistake through Google Pay. Please return it to 9876543210@okicici. Check your GPay - I am sending the request now.",
        is_scam=True, expected_type="UPI/Payment Fraud", category="upi_fraud",
    ),
    TestCase(
        text="Your electricity bill is overdue. Supply will be disconnected today. Pay immediately via this link: www.pay-electricity-bill.co.in/urgent. Payment ref: EL2024-78345.",
        is_scam=True, expected_type="UPI/Payment Fraud", category="upi_fraud",
    ),
    TestCase(
        text="We noticed suspicious login to your Paytm wallet. Verify now by sharing OTP sent to your registered mobile. Our executive ID: PTM-8834. This is urgent - your wallet will be frozen.",
        is_scam=True, expected_type="OTP Fraud", category="upi_fraud",
    ),

    # Job Scam (5)
    TestCase(
        text="Work from home opportunity! Earn Rs 5000-Rs 15000 daily just by liking YouTube videos. No experience needed. Pay Rs 500 registration fee to start earning. WhatsApp: 7890123456.",
        is_scam=True, expected_type="Job Scam", category="job_scam",
    ),
    TestCase(
        text="Dear applicant, you have been selected for Amazon Data Entry position. Salary: Rs 45,000/month. To confirm your joining, pay Rs 2,000 for training materials and company ID card. Contact HR: 8901234567.",
        is_scam=True, expected_type="Job Scam", category="job_scam",
    ),
    TestCase(
        text="Congratulations! Your profile has been shortlisted for part-time typing work at Google India. Earn Rs 800/hour. Complete registration at http://google-hiring-india.tk/register with Rs 1500 security deposit.",
        is_scam=True, expected_type="Job Scam", category="job_scam",
    ),
    TestCase(
        text="Hi, I am Priya from an international trading company. We need people to rate products on our app. You will earn commission on every task. Start with a small investment of Rs 3000 and earn Rs 500 per task. Join our Telegram group.",
        is_scam=True, expected_type="Task Scam", category="job_scam",
    ),
    TestCase(
        text="URGENT HIRING: Customer care executive needed. No interview. Join immediately. Salary Rs 25K-Rs 40K. Just pay Rs 750 for verification. Call: 9012345678. Limited seats.",
        is_scam=True, expected_type="Job Scam", category="job_scam",
    ),

    # Investment Fraud (5)
    TestCase(
        text="Invest in our AI-powered stock trading platform and get guaranteed 45% monthly returns. Minimum investment Rs 10,000. Over 5,000 investors already earning. WhatsApp +91 7654321098 to join our VIP group.",
        is_scam=True, expected_type="Investment Fraud", category="investment_fraud",
    ),
    TestCase(
        text="Exclusive cryptocurrency opportunity: Buy NETRA coin at Rs 2 today, it will be Rs 200 by next month. Our insider analysts guarantee this. Transfer via UPI to crypto.invest@paytm. Limited time offer!",
        is_scam=True, expected_type="Investment Fraud", category="investment_fraud",
    ),
    TestCase(
        text="Join our Telegram trading group. Our AI bot gives 95% accurate signals. Past month returns: 67%. Sign up with Rs 5000 to access premium signals. We are SEBI registered (claim). Contact: 8765432109.",
        is_scam=True, expected_type="Investment Fraud", category="investment_fraud",
    ),
    TestCase(
        text="Double your money in 90 days with our fixed deposit scheme. RBI approved (not really). Interest rate: 24% p.a. Minimum deposit: Rs 50,000. Agent: Rajesh Kumar, 9876012345.",
        is_scam=True, expected_type="Investment Fraud", category="investment_fraud",
    ),
    TestCase(
        text="Sir, I am calling from a well-known brokerage firm. We have a special IPO allocation for you. Invest Rs 1 lakh and get guaranteed allotment. Returns expected 200% in 1 week. Transfer to our partner account immediately.",
        is_scam=True, expected_type="Investment Fraud", category="investment_fraud",
    ),

    # Romance/Impersonation (5)
    TestCase(
        text="Hi dear, I am Sarah from London. I found your profile very attractive. I want to send you a gift package worth $5000 but customs require Rs 15,000 clearance fee. Can you help? I will repay double.",
        is_scam=True, expected_type="Romance Scam", category="romance_scam",
    ),
    TestCase(
        text="I am a US Army officer deployed in Syria. I have $2.5 million in a box that I need to ship to India. I need a trustworthy person to receive it. Just pay the shipping insurance of Rs 25,000.",
        is_scam=True, expected_type="Romance Scam", category="romance_scam",
    ),
    TestCase(
        text="Hello beta, this is your uncle calling from Canada. I am stuck at the airport and my wallet got stolen. Please urgently transfer Rs 30,000 to this account so I can buy a new ticket. Don't tell mom.",
        is_scam=True, expected_type="Impersonation Fraud", category="romance_scam",
    ),
    TestCase(
        text="This is the RBI Governor's office. We are launching a special welfare scheme for senior citizens. Transfer Rs 5000 registration fee and you will receive Rs 5,00,000 in your account within 7 days.",
        is_scam=True, expected_type="Government Impersonation", category="romance_scam",
    ),
    TestCase(
        text="Dear friend, I am a Nigerian prince and I need help transferring $45 million inheritance. I will give you 30% share. Just pay the legal processing fee of Rs 1,00,000. Very urgent and confidential.",
        is_scam=True, expected_type="Advance Fee Fraud", category="romance_scam",
    ),

    # Miscellaneous Scams (5)
    TestCase(
        text="Your parcel from Amazon has been held at customs. Tracking #AM-7834521. Pay Rs 2,499 customs duty to release: http://amazon-customs-pay.in/release. Your package will be returned to sender in 24 hours.",
        is_scam=True, expected_type="Courier/Customs Scam", category="misc_scam",
    ),
    TestCase(
        text="Free iPhone 15 Pro! You are our lucky visitor. Just pay Rs 499 shipping charges. Offer expires in 10 minutes. Enter your bank details at http://free-iphone-india.com/claim now!",
        is_scam=True, expected_type="Lottery/Prize Scam", category="misc_scam",
    ),
    TestCase(
        text="Your Aadhaar card 5678-XXXX-XXXX has been linked to money laundering case MUM/CYB/2024/5567. Appear before court within 24 hours or pay Rs 1,50,000 fine via UPI: court.fine@sbi.",
        is_scam=True, expected_type="Digital Arrest", category="misc_scam",
    ),
    TestCase(
        text="Loan approved! Rs 5,00,000 pre-approved personal loan at 0% interest for 6 months. Pay Rs 3,500 processing fee to activate. SMS LOAN to 56789 or call 1800-XXX-XXXX. Hurry, limited time!",
        is_scam=True, expected_type="Loan Fraud", category="misc_scam",
    ),
    TestCase(
        text="Namaste, I am calling from Airtel. Your SIM will be deactivated in 2 hours because your KYC is pending. Share your Aadhaar number and OTP to verify. Otherwise your number 9988776655 will be permanently blocked.",
        is_scam=True, expected_type="KYC Fraud", category="misc_scam",
    ),

    # ===== BENIGN MESSAGES (30) =====

    TestCase(
        text="Hi, your order #12345 has been shipped via Delhivery. Expected delivery: July 15. Track at www.delhivery.com/track/12345.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Dear customer, your SBI account XX4523 has been credited with Rs 25,000.00 on 10-Jul. Available balance: Rs 1,45,678.50. - SBI.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Reminder: Your HDFC credit card bill of Rs 12,345 is due on 15-Jul-2024. Pay on time to avoid late fees. Net banking: www.hdfcbank.com.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Your OTP for SBI YONO login is 784523. Valid for 5 minutes. Do not share this OTP with anyone. - SBI.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Thank you for your payment of Rs 599 to Netflix India. Your subscription has been renewed. Next billing date: 10-Aug-2024.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Hey, can we meet for coffee tomorrow at 4 PM? There is a new cafe near Koramangala that I wanted to try.",
        is_scam=False, expected_type=None, category="benign_personal",
    ),
    TestCase(
        text="Mom, I will be late today. Have a team meeting that will go until 7 PM. Don't wait for dinner.",
        is_scam=False, expected_type=None, category="benign_personal",
    ),
    TestCase(
        text="Happy birthday! Wishing you a wonderful year ahead. Let's celebrate this weekend with the whole group!",
        is_scam=False, expected_type=None, category="benign_personal",
    ),
    TestCase(
        text="Hi team, please review the Q2 report and share your feedback by EOD Friday. The client presentation is next Monday.",
        is_scam=False, expected_type=None, category="benign_work",
    ),
    TestCase(
        text="Your Swiggy order is on the way! Estimated delivery in 25 minutes. Track your order in the Swiggy app.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Appointment confirmed: Dr. Mehta, Apollo Hospital, 10:30 AM on 12-Jul-2024. Please carry your previous reports and insurance card.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Dear voter, polling for Lok Sabha Elections 2024 is on April 19. Your polling booth: Government School, Sector 22. Carry valid ID proof.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Your Uber ride with driver Ramesh (KA-01-AB-1234) is arriving in 3 minutes. OTP for ride: 4521.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="The weather forecast for Bangalore: Partly cloudy, high of 28C, low of 19C. Chance of rain: 40%. Carry an umbrella.",
        is_scam=False, expected_type=None, category="benign_info",
    ),
    TestCase(
        text="Your IRCTC ticket has been confirmed. PNR: 4567890123. Train: Rajdhani Express 12301. Date: 20-Jul-2024. Berth: B2-45.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Reminder: Please file your income tax return by July 31, 2024. Visit www.incometax.gov.in for e-filing. - IT Department.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Hi Bhaskar, this is a reminder about tomorrow's standup at 10 AM. Please update your JIRA tickets before the meeting.",
        is_scam=False, expected_type=None, category="benign_work",
    ),
    TestCase(
        text="Your Amazon Prime membership has been renewed for Rs 1,499/year. Thank you for being a Prime member. Enjoy free delivery!",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Dear parent, the school will remain closed on Monday due to heavy rainfall forecast. Online classes will be conducted as per the regular schedule.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Your gas cylinder booking has been confirmed. Delivery expected in 3-5 business days. Booking ID: HP-2024-789012.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="The Indian cricket team won the match by 7 wickets. Virat Kohli scored a brilliant 89 off 62 balls. India leads the series 2-1.",
        is_scam=False, expected_type=None, category="benign_info",
    ),
    TestCase(
        text="Your Zerodha Kite account statement for June 2024 is ready. Download from Console: console.zerodha.com. Total P&L: +Rs 12,345.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Sir, this is from BSNL. Your broadband plan has been upgraded to 100 Mbps at no extra cost. Enjoy faster internet from today!",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Meeting notes from today's product review: 1) Launch date confirmed for Aug 1. 2) Design finalized. 3) QA testing starts next week. 4) Marketing assets due by July 25.",
        is_scam=False, expected_type=None, category="benign_work",
    ),
    TestCase(
        text="Your vaccination appointment for COVID-19 booster dose is scheduled for July 18 at 2:00 PM at PHC Koramangala. - CoWIN.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Happy Diwali! May this festival of lights bring joy and prosperity to your family. Have a safe and wonderful celebration!",
        is_scam=False, expected_type=None, category="benign_personal",
    ),
    TestCase(
        text="The library books you requested are ready for pickup: Sapiens and Thinking, Fast and Slow. Please collect by July 20.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Hi, the electrician will come tomorrow between 10 AM - 12 PM to fix the AC. Please make sure someone is at home.",
        is_scam=False, expected_type=None, category="benign_personal",
    ),
    TestCase(
        text="Your EPF contribution for June 2024: Employee share Rs 1,800, Employer share Rs 1,800. Total balance: Rs 4,56,789. - EPFO.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
    TestCase(
        text="Congratulations! Your home loan application with ICICI Bank has been approved for Rs 35,00,000 at 8.5% p.a. Visit your nearest branch with documents for final processing.",
        is_scam=False, expected_type=None, category="benign_notification",
    ),
]


# ---------- Benchmark Runner ----------

async def run_benchmark():
    """Run all test cases against the live NETRA API and compute metrics."""
    import httpx

    API_BASE = "http://localhost:8000"
    results = []

    print(f"\n{'='*70}")
    print(f"  NETRA Detection Benchmark - {len(EVALUATION_DATASET)} Test Cases")
    print(f"{'='*70}\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, tc in enumerate(EVALUATION_DATASET):
            try:
                start = time.monotonic()
                response = await client.post(
                    f"{API_BASE}/api/detect",
                    json={"text": tc.text, "input_type": "text"},
                )
                elapsed = time.monotonic() - start

                if response.status_code != 200:
                    print(f"  [{i+1:02d}] ERROR: HTTP {response.status_code}")
                    results.append({
                        "index": i, "ground_truth": tc.is_scam,
                        "predicted": None, "correct": False,
                        "category": tc.category, "error": True,
                    })
                    continue

                data = response.json()
                predicted_scam = data.get("scam_type") is not None
                confidence = data.get("confidence", 0)

                # For scam cases: confidence >= 0.4 and scam_type is not None = positive
                # For benign cases: scam_type is None or confidence < 0.4 = negative
                if tc.is_scam:
                    correct = predicted_scam and confidence >= 0.4
                else:
                    correct = not predicted_scam or confidence < 0.4

                status = "OK" if correct else "FAIL"
                label = "SCAM" if tc.is_scam else "SAFE"
                pred_label = f"{data.get('scam_type', 'None')} ({confidence:.2f})"

                print(f"  [{i+1:02d}] {status:4s} [{label:4s}] -> {pred_label:40s} ({elapsed:.1f}s)")

                results.append({
                    "index": i,
                    "ground_truth": tc.is_scam,
                    "predicted": predicted_scam,
                    "confidence": confidence,
                    "predicted_type": data.get("scam_type"),
                    "expected_type": tc.expected_type,
                    "correct": correct,
                    "category": tc.category,
                    "latency_s": round(elapsed, 2),
                    "error": False,
                })

            except Exception as e:
                print(f"  [{i+1:02d}] ERROR: {e}")
                results.append({
                    "index": i, "ground_truth": tc.is_scam,
                    "predicted": None, "correct": False,
                    "category": tc.category, "error": True,
                })

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)

    # ---------- Compute Metrics ----------
    valid = [r for r in results if not r.get("error")]

    true_positives = sum(1 for r in valid if r["ground_truth"] and r["predicted"])
    false_positives = sum(1 for r in valid if not r["ground_truth"] and r["predicted"])
    true_negatives = sum(1 for r in valid if not r["ground_truth"] and not r["predicted"])
    false_negatives = sum(1 for r in valid if r["ground_truth"] and not r["predicted"])

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = sum(1 for r in valid if r["correct"]) / len(valid) if valid else 0

    avg_latency = sum(r.get("latency_s", 0) for r in valid) / len(valid) if valid else 0

    print(f"\n{'='*70}")
    print(f"  RESULTS")
    print(f"{'='*70}")
    print(f"\n  Confusion Matrix:")
    print(f"  {'':>20} | Predicted SCAM | Predicted SAFE")
    print(f"  {'Actual SCAM':>20} | {true_positives:>14} | {false_negatives:>14}")
    print(f"  {'Actual SAFE':>20} | {false_positives:>14} | {true_negatives:>14}")

    print(f"\n  Metrics:")
    print(f"  {'Accuracy':>20}: {accuracy:.1%}")
    print(f"  {'Precision':>20}: {precision:.1%}")
    print(f"  {'Recall':>20}: {recall:.1%}")
    print(f"  {'F1 Score':>20}: {f1:.3f}")
    print(f"  {'Avg Latency':>20}: {avg_latency:.2f}s")
    print(f"  {'Total Test Cases':>20}: {len(EVALUATION_DATASET)}")
    print(f"  {'Errors':>20}: {len(results) - len(valid)}")

    # Per-category breakdown
    categories = sorted(set(r["category"] for r in valid))
    print(f"\n  Per-Category Accuracy:")
    for cat in categories:
        cat_results = [r for r in valid if r["category"] == cat]
        cat_acc = sum(1 for r in cat_results if r["correct"]) / len(cat_results) if cat_results else 0
        print(f"  {'  ' + cat:>25}: {cat_acc:.0%} ({sum(1 for r in cat_results if r['correct'])}/{len(cat_results)})")

    print(f"\n{'='*70}\n")

    # Save results
    output = {
        "metrics": {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "avg_latency_s": round(avg_latency, 2),
        },
        "confusion_matrix": {
            "true_positives": true_positives,
            "false_positives": false_positives,
            "true_negatives": true_negatives,
            "false_negatives": false_negatives,
        },
        "total_cases": len(EVALUATION_DATASET),
        "results": results,
    }

    with open("evaluation_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print("  Results saved to evaluation_results.json")

    return output


if __name__ == "__main__":
    asyncio.run(run_benchmark())
