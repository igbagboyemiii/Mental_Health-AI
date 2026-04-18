# Product Requirements Document (PRD)
## MindGuard — Cross-Platform Depressive Text Detection System

**Version:** 1.0  
**Date:** April 2026  
**Status:** Draft for Review

---

## 1. Executive Summary

MindGuard is an AI-powered, cross-platform mental health monitoring system designed to passively and actively detect depressive language patterns from user-generated text across multiple surfaces — browser, mobile, and desktop. It uses a Retrieval-Augmented Generation (RAG) pipeline backed by semantic embeddings (FAISS) and a fine-tuned Language Model to classify risk levels and trigger appropriate interventions.

> [!IMPORTANT]
> This system handles sensitive mental health data. All design decisions must be evaluated against ethical guidelines, clinical best practices, and applicable privacy regulations (HIPAA, GDPR, NDPR).

---

## 2. Architecture Review

### 2.1 Proposed Architecture

```
┌────────────────────┐
│   Browser Extension│  ← Passive monitoring of typed text (opt-in)
└─────────┬──────────┘
          │
┌─────────▼──────────┐
│   Mobile Input App │  ← Active journaling + passive keyboard monitoring
└─────────┬──────────┘
          │
┌─────────▼──────────┐
│  Desktop App        │  ← Optional deep monitoring + dashboard
└─────────┬──────────┘
          │
  ┌───────▼────────┐
  │  Backend API   │  ← Orchestration, auth, rate limiting, logging
  │  (AI Model)    │
  └───────┬────────┘
          │
┌─────────▼──────────────────────────────┐
│  RAG + Risk Detection System           │
│  (FAISS + Embeddings + LLM)            │
└────────────────────────────────────────┘
```

### 2.2 Architecture Strengths ✅

| Strength | Details |
|---|---|
| **Cross-platform coverage** | Captures text from browsers, mobile, and desktop for holistic monitoring |
| **RAG augmentation** | Semantic retrieval improves detection accuracy over pure classification |
| **Modular design** | Each client layer is independently deployable; the AI backend is decoupled |
| **FAISS efficiency** | Vector similarity search scales well for real-time inference |
| **Optional desktop** | Avoids forcing unnecessary permissions; lowers adoption friction |

### 2.3 Architecture Gaps & Recommendations ⚠️

| Gap | Risk | Recommendation |
|---|---|---|
| **No offline/edge inference** | Cloud dependency creates latency & privacy concerns | Add on-device model (e.g., TensorFlow Lite / ONNX) as first-pass filter |
| **No consent & audit layer** | Regulatory non-compliance, ethical violations | Add explicit consent management & audit logging at API gateway |
| **No alerting/intervention layer** | Detection without action is incomplete | Add a downstream **Crisis Intervention Engine** (notifications, escalation) |
| **No feedback loop** | Model will drift over time without retraining signals | Add clinician-reviewed feedback pipeline to support continuous learning |
| **Single API bottleneck** | Backend is a single point of failure | Design for horizontal scaling + circuit breakers |
| **No context window** | Single-message analysis misses longitudinal patterns | Add user-level temporal context store (rolling 30-day window) |

### 2.4 Recommended Enhanced Architecture

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Browser    │  │   Mobile     │  │   Desktop    │
│   Extension  │  │   App        │  │   App        │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       └─────────────────▼──────────────────┘
                         │
              ┌──────────▼───────────┐
              │   Consent Manager    │  ← Explicit opt-in, data control
              │   + Audit Logger     │
              └──────────┬───────────┘
                         │
              ┌──────────▼───────────┐
              │   API Gateway        │  ← Auth, rate limiting, routing
              └──────────┬───────────┘
                         │
         ┌───────────────▼────────────────┐
         │  On-Device Prefilter (Edge AI) │  ← Noise reduction, privacy
         └───────────────┬────────────────┘
                         │
         ┌───────────────▼────────────────┐
         │  Temporal Context Store        │  ← Rolling user history
         └───────────────┬────────────────┘
                         │
         ┌───────────────▼────────────────┐
         │  RAG + Risk Detection Engine   │
         │  (FAISS + Embeddings + LLM)    │
         └───────────────┬────────────────┘
                         │
         ┌───────────────▼────────────────┐
         │  Crisis Intervention Engine    │  ← Alerts, escalation, resources
         └───────────────┬────────────────┘
                         │
         ┌───────────────▼────────────────┐
         │  Clinician Review + Feedback   │  ← Continuous model improvement
         └────────────────────────────────┘
```

---

## 3. Product Goals

### 3.1 Primary Goals
1. Accurately detect depressive and suicidal ideation in user-generated text with ≥85% precision and recall.
2. Provide timely, context-aware intervention recommendations across all platforms.
3. Maintain full user privacy with explicit consent and data minimization.

### 3.2 Success Metrics (KPIs)

| Metric | Target |
|---|---|
| Detection Precision | ≥ 85% |
| Detection Recall | ≥ 85% |
| F1 Score | ≥ 0.85 |
| False Positive Rate | < 10% |
| Latency (API response) | < 500ms (P95) |
| User Consent Rate | ≥ 70% of active users |
| Crisis Escalation Accuracy | ≥ 95% on validated high-risk cases |
| Monthly Active Users (6-month target) | 10,000+ |

---

## 4. Users & Stakeholders

### 4.1 User Personas

| Persona | Description | Primary Surface |
|---|---|---|
| **At-Risk Individual** | Person experiencing depressive episodes, may or may not be aware | Mobile + Browser |
| **Mental Health Professional** | Therapist monitoring consented patients | Desktop Dashboard |
| **Caregiver / Guardian** | Family member monitoring a consented dependent | Mobile |
| **Researcher** | Academic studying linguistic patterns in mental health | API / Dashboard |
| **Platform Admin** | System administrator managing users and compliance | Admin Dashboard |

### 4.2 Stakeholders
- Mental health clinicians (advisors on clinical validity)
- Ethics review board
- Legal / compliance team (HIPAA, GDPR, NDPR)
- Engineering team
- Product team

---

## 5. Functional Requirements

### 5.1 Browser Extension

| ID | Requirement | Priority |
|---|---|---|
| BR-01 | User must explicitly opt-in to text monitoring with granular consent controls | P0 |
| BR-02 | Extension must capture text from form inputs, text areas, and rich text editors | P0 |
| BR-03 | Extension must NOT capture passwords, credit card fields, or private browsing sessions | P0 |
| BR-04 | Extension must batch and encrypt text before transmitting to API | P0 |
| BR-05 | Extension must support Chrome, Firefox, Edge, and Safari | P1 |
| BR-06 | Extension must display an unobtrusive status indicator (active/paused) | P1 |
| BR-07 | Extension must allow users to pause/resume monitoring per-site | P1 |
| BR-08 | Extension must support on-device pre-filtering before cloud transmission | P2 |

### 5.2 Mobile App

| ID | Requirement | Priority |
|---|---|---|
| MB-01 | App must provide an active journaling interface with daily prompts | P0 |
| MB-02 | App must support passive mood check-ins (emoji/slider scale) | P0 |
| MB-03 | App must support optional keyboard monitoring with explicit consent | P1 |
| MB-04 | App must display personalized risk trend over time (7-day, 30-day) | P1 |
| MB-05 | App must support iOS and Android (React Native or Flutter) | P0 |
| MB-06 | App must support offline journaling with sync when connected | P1 |
| MB-07 | App must send push notifications for check-ins and crisis resources | P0 |
| MB-08 | App must support biometric authentication (Face ID / Fingerprint) | P1 |

### 5.3 Desktop App (Optional Module)

| ID | Requirement | Priority |
|---|---|---|
| DK-01 | Desktop app must provide a comprehensive monitoring dashboard | P1 |
| DK-02 | Desktop app must allow mental health professionals to view consented patient data | P1 |
| DK-03 | Desktop app must support Windows, macOS, and Linux | P2 |
| DK-04 | Desktop app must provide exportable reports (PDF/CSV) | P2 |

### 5.4 Backend API

| ID | Requirement | Priority |
|---|---|---|
| API-01 | API must authenticate all requests via OAuth 2.0 / JWT | P0 |
| API-02 | API must enforce per-user rate limiting | P0 |
| API-03 | API must accept text payloads and return risk classification + confidence score | P0 |
| API-04 | API must maintain an audit log of all inferences (GDPR Article 22) | P0 |
| API-05 | API must support horizontal scaling (containerized via Docker/Kubernetes) | P1 |
| API-06 | API must provide a `/health` endpoint and expose metrics (Prometheus) | P1 |
| API-07 | API must anonymize user data before passing to AI inference layer | P0 |

### 5.5 RAG + Risk Detection Engine

| ID | Requirement | Priority |
|---|---|---|
| AI-01 | System must classify text into risk tiers: `None`, `Low`, `Moderate`, `High`, `Crisis` | P0 |
| AI-02 | System must use FAISS vector store for semantic retrieval of similar clinical cases | P0 |
| AI-03 | System must incorporate temporal context (user history over 30 days) | P1 |
| AI-04 | System must output explainable results (key phrases, reasoning summary) | P1 |
| AI-05 | System must be fine-tuned on clinically validated depressive text datasets | P0 |
| AI-06 | System must support continuous retraining from clinician feedback | P2 |
| AI-07 | System must detect code-switching and non-English depressive markers | P2 |

### 5.6 Crisis Intervention Engine

| ID | Requirement | Priority |
|---|---|---|
| CI-01 | System must trigger immediate push notification on `Crisis` classification | P0 |
| CI-02 | System must display localized crisis hotline numbers and resources | P0 |
| CI-03 | System must alert designated emergency contacts (with user consent) | P1 |
| CI-04 | System must escalate to connected mental health professional if assigned | P1 |
| CI-05 | System must log all crisis events with outcome tracking | P0 |

---

## 6. Non-Functional Requirements

### 6.1 Privacy & Ethics

| ID | Requirement |
|---|---|
| PRI-01 | All data must be encrypted in transit (TLS 1.3) and at rest (AES-256) |
| PRI-02 | User data must never be sold or shared with third parties without explicit consent |
| PRI-03 | Users must be able to export or delete all their data at any time (right to erasure) |
| PRI-04 | System must implement differential privacy for aggregate analytics |
| PRI-05 | Automated decisions must never directly trigger involuntary intervention without human review |
| PRI-06 | System must be compliant with HIPAA, GDPR, and Nigeria's NDPR |

### 6.2 Performance

| Requirement | Target |
|---|---|
| API inference latency | < 500ms (P95) |
| API availability | 99.9% uptime SLA |
| Concurrent users supported | 10,000+ |
| FAISS query time | < 100ms |
| Mobile app cold start | < 2 seconds |

### 6.3 Security

- Penetration tested every 6 months
- Role-Based Access Control (RBAC) for all dashboard views
- Zero-trust network architecture for internal services
- Regular dependency auditing (OWASP Top 10 mitigations)

---

## 7. AI Model Requirements

### 7.1 Model Architecture
- **Base model:** Fine-tuned BERT / RoBERTa or domain-adapted LLM (e.g., Mental-BERT, MentalRoBERTa)
- **Retrieval layer:** FAISS with sentence-transformer embeddings (e.g., `all-MiniLM-L6-v2` or clinical variants)
- **LLM reasoning:** Lightweight LLM for explainability output (e.g., Mistral 7B / Llama 3)
- **Edge model:** Distilled/quantized variant (ONNX/TFLite) for on-device pre-filtering

### 7.2 Training Data Requirements

| Dataset | Purpose |
|---|---|
| CLEF eRisk datasets | Depressive text classification benchmark |
| Reddit Mental Health Dataset | Real-world informal depressive language |
| DAIC-WOZ | Clinical depression interviews |
| Custom annotated corpus | Domain-specific fine-tuning (clinician-labeled) |
| Synthetic augmentation | Addressing data imbalance via LLM-generated samples |

> [!WARNING]
> All training data must be ethically sourced, anonymized, and IRB/ethics-board approved before use.

### 7.3 Risk Classification Schema

| Level | Description | System Action |
|---|---|---|
| `None` | No indicators detected | No action |
| `Low` | Mild negative sentiment, stress markers | Log + trend tracking |
| `Moderate` | Consistent negative patterns, hopelessness language | In-app wellness nudge |
| `High` | Explicit depressive ideation, self-harm language | Push notification + resources |
| `Crisis` | Suicidal ideation, imminent risk markers | Immediate alert + emergency contacts |

---

## 8. Data Flow

```
User Input (text)
      │
      ▼
[On-device pre-filter] → Noise? → Drop
      │
      ▼ (potential risk detected)
[Encrypt + Anonymize]
      │
      ▼
[API Gateway] → Authenticate & Rate Limit
      │
      ▼
[Temporal Context Store] ← Retrieve user's 30-day history
      │
      ▼
[FAISS Retrieval] → Retrieve similar clinical embeddings
      │
      ▼
[LLM Risk Classifier] → Risk Level + Confidence + Explanation
      │
      ▼
[Intervention Engine] → Trigger appropriate response
      │
      ▼
[Audit Log + Feedback Store] → Clinician review queue
```

---

## 9. Phased Rollout Plan

### Phase 1 — MVP (Months 1–4)
- [ ] Fine-tune base depression detection model on benchmark datasets
- [ ] Build core Backend API (inference endpoint, auth, audit logging)
- [ ] Build Mobile App (journaling + mood check-in + risk trend view)
- [ ] Implement 5-level risk classification schema
- [ ] Basic crisis intervention (push notification + hotline display)
- [ ] Privacy-first consent management system

### Phase 2 — Expansion (Months 5–8)
- [ ] Browser extension (Chrome + Firefox)
- [ ] FAISS-backed RAG retrieval integration
- [ ] Temporal context store (30-day rolling window)
- [ ] Emergency contact alerting
- [ ] Clinician dashboard (desktop app v1)

### Phase 3 — Intelligence & Scale (Months 9–12)
- [ ] On-device edge AI pre-filter (ONNX/TFLite)
- [ ] Multilingual support (Yoruba, Hausa, French, Pidgin)
- [ ] Clinician feedback loop for continuous retraining
- [ ] Differential privacy for research analytics
- [ ] API open to institutional partners (hospitals, NGOs)

---

## 10. Open Questions & Design Decisions

> [!IMPORTANT]
> The following require stakeholder input before development begins.

1. **Consent model**: Should monitoring be fully opt-in per session, or persistent opt-in with easy opt-out? Persistent consent reduces friction but raises ethical concerns.

2. **Keyboard monitoring**: Mobile keyboard monitoring is high-value but extremely sensitive. Should it be limited to the in-app journal only, or extended to the system keyboard?

3. **Emergency contact escalation**: At what risk level should emergency contacts be notified automatically vs. after user confirmation? Automatic escalation at `Crisis` level may save lives but could erode trust.

4. **Clinician access model**: Should mental health professionals see raw text or only summarized insights? Raw text access has clinical utility but increases privacy exposure.

5. **Model hosting**: Cloud-only inference (lower cost, centralized control) vs. hybrid edge+cloud (stronger privacy, higher complexity)?

6. **Regulatory jurisdiction**: Which primary jurisdiction governs this product (Nigeria, EU, US, global)? This determines baseline compliance requirements.

7. **Dataset ethics**: Has IRB/ethics approval been obtained for training data collection and use?

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| High false positive rate causing alarm fatigue | High | High | Ensemble models + human-in-the-loop review |
| Privacy breach of sensitive mental health data | Medium | Critical | End-to-end encryption, minimal data retention, regular audits |
| User distrust of monitoring | High | High | Radical transparency, granular consent, open-source model card |
| Model bias against non-English or minority groups | Medium | High | Diverse training data, bias audits, multilingual support |
| Regulatory non-compliance | Medium | Critical | Engage legal counsel early; build compliance into architecture |
| Misuse by abusive partners/guardians | Low | Critical | Strict consent verification; user always retains data control |
| Over-reliance by users replacing professional care | Medium | High | Prominent disclaimers; integration with professional referral |

---

## 12. Ethical Framework

> [!CAUTION]
> This system must operate under a strict "**do no harm**" principle. It is a **supportive tool**, not a clinical diagnostic instrument. The following principles are non-negotiable:

1. **Autonomy**: Users retain full control over their data at all times.
2. **Transparency**: Users always know what is being monitored and why.
3. **Non-maleficence**: The system must never take actions that could cause harm (e.g., false crisis alarms).
4. **Beneficence**: Every feature must demonstrably improve user wellbeing.
5. **Human oversight**: No automated decision should bypass human review for high-stakes outcomes.
6. **Equity**: The system must perform equitably across demographic groups.

---

## 13. Glossary

| Term | Definition |
|---|---|
| RAG | Retrieval-Augmented Generation — combining vector retrieval with LLM reasoning |
| FAISS | Facebook AI Similarity Search — efficient vector similarity library |
| IRB | Institutional Review Board — ethics oversight for research |
| NDPR | Nigeria Data Protection Regulation |
| GDPR | General Data Protection Regulation (EU) |
| HIPAA | Health Insurance Portability and Accountability Act (US) |
| On-device / Edge AI | Model inference performed locally on user's device |
| Risk Tier | Classification level of detected depressive risk |

---

*Document Owner: Product Team*  
*Review Cycle: Quarterly*  
*Next Review: July 2026*
