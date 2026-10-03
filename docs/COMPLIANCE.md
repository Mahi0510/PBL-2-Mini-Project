# Privacy, Fairness and Legal Checklist

*This is a practical checklist, not legal advice. Have a lawyer review it before you process real candidates.*

## What the software already does

* **Human in the loop** - the AI only scores and suggests. Every status change (interview / hold / reject) and every email is triggered by an HR user.
* **Consent** - candidates must tick a privacy notice before applying; the timestamp is stored with the application.
* **Right to erasure** - HR can permanently delete a candidate's record, resume PDF and email history from the dashboard.
* **Retention limit** - applications are deleted automatically after `RETENTION_DAYS` (default 365).
* **Access control** - all HR pages, APIs and resume previews need a login; failed logins are rate-limited; applications are rate-limited.
* **Audit log** - screening, decisions, emails and deletions are logged.
* **Data minimisation** - the screener ignores name, gender, age, photo and address; it only compares skills/text with the job description.

## What you (the operator) still need to do

1. **Privacy policy** - publish one that names who processes the data, why, for how long, and how to request deletion. Link it from the careers page.
2. **Know your law**:
   * *India* - Digital Personal Data Protection Act, 2023 (consent, purpose limitation, erasure).
   * *EU/UK* - GDPR (Art. 22 limits solely-automated decisions; keep a human reviewer) and the EU AI Act, which treats recruitment AI as **high-risk** (documentation, oversight, transparency duties).
   * *USA* - e.g. New York City Local Law 144 requires an independent **bias audit** and candidate notice for automated employment tools; Illinois and others have similar rules.
3. **Bias audit** - test the scoring on a sample of real, anonymised resumes. Keyword matching can disadvantage people who describe the same skills differently (e.g. career gaps, non-English CVs, different terminology).
4. **Secure hosting** - HTTPS, strong admin password, regular backups, OS updates.
5. **Email** - send from a company domain address, not a personal Gmail account.
6. **Sub-processors** - if you use Gmail/SES/hosting providers, list them in your privacy policy.
