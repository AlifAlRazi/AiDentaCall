# DentaCall Clinic Specification

This specification serves as the single source of truth for Grand Canal Dental Clinic. It defines operating hours, personnel, services, booking constraints, emergency triage rules, and agent guardrails.

---

## 1. Clinic Profile

- **Clinic Name:** Grand Canal Dental Clinic
- **Trading Entity:** Grand Canal Dental Partners Ltd.
- **Physical Address:** 12 Grand Canal Quay, Grand Canal Dock, Dublin 2, D02 X2Y8, Ireland
- **Primary Telephone:** `+353 1 234 5678` (E.164 format)
- **Primary Email:** `reception@grandcanaldental.ie`
- **Emergency Helpline:** `+353 1 234 9999`
- **Timezone:** `Europe/Dublin` (Irish Standard Time IST `UTC+1` from late March to late October; Greenwich Mean Time GMT `UTC+0` in winter).
- **Default Currency:** EUR (€)

---

## 2. Operating Hours & Schedule Rules

All operational and scheduling times are defined in **Europe/Dublin** local time. At the database layer, all appointments, slots, and holds are stored canonically in **UTC**.

| Day | Clinic Hours | Lunch Break (No Routine Appts) | Available Appointment Types |
| :--- | :--- | :--- | :--- |
| **Monday** | 08:30 – 18:00 | 13:00 – 14:00 | All Services |
| **Tuesday** | 08:30 – 18:00 | 13:00 – 14:00 | All Services |
| **Wednesday** | 08:30 – 18:00 | 13:00 – 14:00 | All Services |
| **Thursday** | 08:30 – 18:00 | 13:00 – 14:00 | All Services |
| **Friday** | 08:30 – 17:00 | 13:00 – 14:00 | All Services |
| **Saturday** | 09:00 – 14:00 | None | Emergency & Hygiene Only |
| **Sunday** | **Closed** | — | Emergency on-call divert only |

### Statutory Irish Public Holidays (Clinic Closed)
The clinic observes all Republic of Ireland public and bank holidays:
1. New Year's Day (1 January)
2. St. Brigid's Day (First Monday in February, or 1 Feb if Friday)
3. St. Patrick's Day (17 March)
4. Easter Monday (Moveable)
5. May Day Bank Holiday (First Monday in May)
6. June Bank Holiday (First Monday in June)
7. August Bank Holiday (First Monday in August)
8. October Bank Holiday (Last Monday in October)
9. Christmas Day (25 December)
10. St. Stephen's Day (26 December)

*Note: On bank holidays, the AI receptionist informs callers that the clinic is closed for the bank holiday and provides emergency triage or takes a callback message.*

---

## 3. Practitioners & Rosters

The clinic employs three registered dental practitioners (Irish Dental Council registered):

### 1. Dr. Sean O'Connor, BDS NUI
- **Registration ID:** `IE-DEN-44821`
- **Role:** Lead General Dentist & Clinical Partner
- **Specialisms:** Comprehensive general dentistry, routine check-ups, restorative crowns, preventative care.
- **Roster:**
  - Monday: 08:30 – 17:30
  - Tuesday: 08:30 – 17:30
  - Wednesday: 08:30 – 17:30
  - Thursday: 08:30 – 17:30
  - Friday: Off
  - Saturday: Off

### 2. Dr. Aoife Murphy, BA BDentSc TCD
- **Registration ID:** `IE-DEN-51209`
- **Role:** Associate General & Paediatric Dental Surgeon
- **Specialisms:** Preventative hygiene, tooth-colored composite restorations, pediatric dental care, routine exams.
- **Roster:**
  - Monday: Off
  - Tuesday: 08:30 – 17:00
  - Wednesday: 08:30 – 17:00
  - Thursday: 08:30 – 17:00
  - Friday: 08:30 – 17:00
  - Saturday: 09:00 – 14:00 (Rotational cover)

### 3. Dr. Liam Kelly, BDS NUI, Dip Clin Dent
- **Registration ID:** `IE-DEN-39744`
- **Role:** Senior Dental Surgeon (Endodontics & Oral Surgery Lead)
- **Specialisms:** Acute toothache, emergency trauma stabilization, root canal therapy (pulpectomy/extirpation), surgical extractions.
- **Roster:**
  - Monday: 08:30 – 17:30
  - Tuesday: Off
  - Wednesday: 08:30 – 17:30
  - Thursday: Off
  - Friday: 08:30 – 17:00
  - Saturday: 09:00 – 14:00 (Emergency priority lead on duty)

---

## 4. Service Catalog, Durations, and Fees

The clinic offers six transparently priced standard services. All listed prices include VAT where applicable (medical/dental care is generally VAT-exempt under Irish revenue rules).

| Code | Service Name | Clinical Duration | Buffer Time | Total Slot | Price (EUR) | Description & Inclusions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `CHECKUP` | **Routine Dental Examination** | 30 mins | 5 mins | 35 mins | **€65.00** | Full oral health exam, soft tissue and periodontal screening, bite assessment, treatment planning. |
| `HYGIENE` | **Scale & Polish (Hygiene)** | 45 mins | 5 mins | 50 mins | **€90.00** | Ultrasonic descaling, gentle plaque and calculus removal, stain polishing, oral hygiene advice. |
| `FILLING` | **Composite (White) Filling** | 45 mins | 10 mins | 55 mins | **€130.00** | Single-surface aesthetic tooth-colored composite resin restoration, local anaesthesia included. |
| `EMERGENCY` | **Emergency Pain & Trauma Assessment** | 30 mins | 5 mins | 35 mins | **€80.00** | Immediate symptom triage, targeted diagnostic x-ray, acute pain relief or temporary dressing. |
| `EXTRACTION`| **Simple Tooth Extraction** | 45 mins | 15 mins | 60 mins | **€140.00** | Non-surgical extraction of a single erupted tooth, local anaesthesia, post-op gauze pack, healing guide. |
| `ROOT_CANAL`| **Root Canal Consult & Stage 1** | 60 mins | 15 mins | 75 mins | **€220.00** | Diagnostic evaluation, pulp extirpation, antibacterial disinfection, and temporary tooth seal. |

### Buffer Rules
- Each booking reserves both the **Clinical Duration** and the subsequent **Buffer Time**.
- A dentist cannot be double-booked during either the clinical duration or the buffer window.
- Buffer time allows room sanitization, sterilization changeover, and note-taking.

---

## 5. Cancellation & Reschedule Policy

1. **24-Hour Notice Rule:**
   - Any cancellation or rescheduling request must be received at least **24 hours prior** to the scheduled appointment start time.
   - If cancelled or rescheduled **>= 24 hours in advance**: No cancellation fee is assessed.
2. **Late Cancellations (< 24 Hours):**
   - A late cancellation fee of **€30.00** applies to cancellations or reschedules made inside the 24-hour window, added to the patient's account.
3. **No-Show Policy:**
   - Missed appointments without notification incur a **€50.00** failure-to-attend fee.
   - Future bookings for patients with two or more no-shows require an upfront prepayment deposit.
4. **Agent Action:**
   - When a caller requests cancellation or rescheduling, the agent must check the elapsed hours before the appointment.
   - If < 24 hours remain, the agent must inform the caller of the €30 late cancellation policy and confirm they wish to proceed before committing the action.

---

## 6. Emergency Medical Policy & Triage Protocol

Patient safety is paramount. The voice agent must detect dental and medical emergencies and follow a strict escalation protocol.

### Emergency Indicators
- **Uncontrolled or heavy bleeding** from the mouth following trauma or extraction that persists past 20 minutes of firm pressure.
- **Rapid or severe facial, neck, or submandibular swelling** causing airway difficulty, swallowing pain, or eye restriction (risk of Ludwig's Angina).
- **Dental trauma / avulsed adult tooth:** A permanent tooth knocked clean out of the mouth within the past 60 minutes.
- **Severe, unbearable dental pain** accompanied by fever, chills, dizziness, or confusion.
- **Suspected jaw fracture** or traumatic facial injury with malocclusion.

### Emergency Action Protocol
1. **Immediate De-escalation & Warning:**
   - The agent MUST interrupt routine booking dialogue immediately upon identifying an emergency trigger.
   - Voice response tone: Calm, firm, clear.
2. **Operating Hours Action:**
   - During clinic hours: Offer immediate transfer to the duty dental surgeon at `+353 1 234 9999` or book the next available immediate emergency slot (`EMERGENCY`).
3. **Out-of-Hours / Critical Danger Action:**
   - If the patient is having difficulty breathing, swallowing, or experiencing severe bleeding: Instruct them immediately to hang up and dial **999 or 112** (Irish Emergency Services) or proceed directly to the nearest hospital Emergency Department (St. James's Hospital A&E or Mater Misericordiae Hospital, Dublin).
4. **Knocked-Out (Avulsed) Adult Tooth Protocol:**
   - Deliver immediate first-aid instructions:
     > *"Please do not touch the root of the tooth; hold it only by the crown. Gently place the tooth in a cup of cold milk or inside your cheek if safe, and attend our clinic or an emergency department within 60 minutes for the best chance of saving it."*

---

## 7. Absolute Boundaries (What the Agent Must NEVER Do)

The voice and text agent operates under strict clinical and regulatory guardrails:

1. **NO Medical or Dental Advice:**
   - The agent must NEVER advise patients on taking specific prescription medications, adjusting dosages, or stopping prescribed treatments.
   - The agent must NEVER endorse home remedies, unapproved analgesics, or diagnose drug interactions.
2. **NO Clinical Diagnosis:**
   - The agent must NEVER attempt to diagnose the caller's medical or dental condition (e.g. NEVER say: *"That sounds like a periapical abscess"* or *"You have advanced periodontitis"*).
   - Permitted phrasing: *"I understand you are experiencing sharp sensitivity to cold. Let us book an examination with Dr. O'Connor so our dentist can thoroughly examine the tooth."*
3. **NO Price Promises Outside the Official Fee Schedule:**
   - The agent must strictly adhere to the 6 published service prices.
   - It must NEVER offer discounts, negotiate fees, or quote custom estimates for complex procedures (e.g., implants, veneers, full orthodontics, bone grafts) that require in-person dental consultation.
   - Phrasing: *"Our consultation and assessment fee is €65. If additional treatments like crowns or bridges are needed, the dentist will provide you with a written treatment plan and estimate after your exam."*
4. **NO Patient Record Disclosure Without Verification:**
   - The agent must NEVER disclose appointment times, medical notes, or personal details without verifying caller identity:
     - Full Name
     - Date of Birth (YYYY-MM-DD)
     - Phone Number match
   - The agent must NEVER discuss one patient's appointments or details with another caller (strictly compliant with GDPR and the Irish Data Protection Act 2018).
5. **NO Schedule Overrides:**
   - The agent cannot book appointments outside clinic operating hours, during staff lunch breaks, on bank holidays, or onto unavailable dentists without human administrative override.
