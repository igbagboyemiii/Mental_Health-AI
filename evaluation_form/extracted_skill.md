---
name: bsc-defence-questions
description: >
  Generates rigorous viva voce (oral defence) questions from a final year BSc project report,
  provides model answers grounded in the student's own report, and outputs everything as a
  Word document. Use this skill whenever a student uploads their project and asks for defence
  questions, practice questions, viva questions, answers to defence questions, or wants to
  prepare for their project presentation or defence. Also triggers on phrases like "generate
  questions from my project", "help me prepare for my defence", "what questions will they ask
  me", "give me questions and answers for my defence", "prepare me for my viva". The skill reads
  every chapter, generates exactly 25 questions per chapter (5 sub-categories x 5 questions each)
  plus 25 general questions, writes a model answer for every question drawn from the report
  (supplemented by web search for technical gaps), and adds a study nudge wherever the report
  does not give enough information for a confident answer. Output is a personalised .docx document.
---

# BSc Defence Question Generator with Answers

Read a student's final year BSc project report. Generate a comprehensive, personalised bank
of viva voce questions — exactly 25 per chapter, 25 general. For every question, write:
1. A **model answer** drawn from the student's own report
2. A **study nudge** if the report does not give enough for a full answer
3. A **web-sourced supplement** for technical questions the report does not fully address

Output: a personalised `.docx` question-and-answer bank.

---

## Overview

**Target document**: BSc final year project (any discipline, 50–70 pages typical)
**Output**: Personalised `.docx` question + answer bank
**Questions**: exactly 25 per chapter (5 sub-categories × 5 questions each) + 25 general = up to 150 questions
**Every question has**: a model answer + optional study nudge + optional web supplement
**Tone**: Examiner-level questions; supportive, coaching answers addressed to the student

---

## Step 1 — Get the project file

The student must upload their project report (PDF or DOCX).

If no file is present, respond:
> "Please upload your project report (PDF or Word document) and I'll generate your full defence Q&A bank."

Once the file is present, read the appropriate skill and extract the full text:
- For DOCX: read `/mnt/skills/public/file-reading/SKILL.md` and follow it
- For PDF: read `/mnt/skills/public/pdf-reading/SKILL.md` and follow it

---

## Step 2 — Extract key metadata

Scan the title page and opening pages for:
- **Student name** — use first name throughout in direct address
- **Project title** — reference in questions
- **Department / course / discipline**
- **Chapter titles and structure**
- **Research objectives** — extract verbatim, numbered exactly as written
- **Theoretical framework / model used**
- **Key methods, tools, software, languages**
- **Key findings and results** — specific numbers, percentages, scores, conclusions

---

## Step 3 — Deep-read every chapter

Read the full text carefully. Build an internal knowledge base per chapter:

**Chapter One**: Background claims and citations, problem statement sentences, objectives, scope, significance claims, key terms introduced
**Chapter Two**: Theories and frameworks, cited authors and years, comparison tables, research gap statement, conceptual model
**Chapter Three**: Research design, sample size, sampling technique, instrument description, analysis methods, software tools, ethical procedures, system architecture (for dev projects)
**Chapter Four**: Specific result figures, table and figure numbers, discussion claims, evaluation criteria and scores, comparisons to literature
**Chapter Five**: Conclusion statements, limitations, recommendations, any new material

Flag as you read:
- **Strong/sweeping claims** → will become Challenge questions
- **Vague or undefined terms** → will become Clarification questions
- **Unjustified decisions** → will become Justification questions
- **Objectives without matching results** → will become Mapping questions
- **Thin sections** (concept mentioned but not explained) → will trigger study nudges

---

## Step 4 — For each question: write Question + Answer + Nudge

For every question generated, produce three components:

### 4a — The Question
Specific to the student's actual content. Every question must name real things from the report:
real objectives, real cited authors, real methods, real result figures, real sentences written by the student.
Never use generic placeholders like "[Author]" or "[Method]" — replace with actual names.

### 4b — The Model Answer
The answer must be drawn **directly from the report**. Follow this logic:

**IF the report answers it clearly:**
Write a 3–6 sentence model answer in first-person voice ("In my project, I...") that the student
could say aloud in their defence. Quote or closely paraphrase key sentences from the report where
appropriate. Make the answer sound natural and confident — like a student who truly owns their work.

**IF the report partially answers it:**
Write the partial answer from the report, then clearly mark: `[SUPPLEMENT — see study nudge]`
and provide a study nudge (see 4c).

**IF the report does not answer it at all (technical or conceptual gap):**
- First check: can a web search fill this gap? If yes, search and write a brief, accurate
  supplementary answer clearly labelled `[From general knowledge / web search]`
- Then write a study nudge directing the student to understand this concept properly

### 4c — The Study Nudge
Write a study nudge whenever:
- The report does not contain enough information for a full confident answer
- The student used a concept, tool, framework, or technique without explaining it properly in the report
- The answer relies on knowledge the student should have but the report does not demonstrate

Format the nudge as:
> 📚 **Study nudge**: [Direct, friendly instruction telling the student exactly what to read or learn.
> Name the concept, the framework, the technique. Tell them why this is likely to come up.
> Keep it to 2–4 sentences.]

**Do NOT write a nudge if the report already gives a complete, confident answer.**

---

## Step 5 — Answer source labels

Every answer must carry one of these source labels so the student knows where it came from:

- `[From your report]` — answer drawn fully from the student's own text
- `[Partial — from your report]` — report gives some of the answer; nudge covers the rest  
- `[From general knowledge]` — technical/conceptual answer not in the report; sourced from web or knowledge
- `[From your report + general knowledge]` — blend of both

---

## Step 6 — Question categories and templates

Generate questions for each chapter using the templates below.
**Replace every placeholder with real content from the student's report.**

STRICT RULE: Every chapter must have EXACTLY 25 questions — 5 sub-categories × 5 questions each.
No chapter may have fewer than 25 or more than 25 questions.
Count before writing the JSON.

---

### Chapter One — exactly 25 questions (5 per sub-category)

**Sub-category A — Background and Context (questions 1–5)**
Pick 5 from:
- "Explain the broad context of your study in your own words without reading from the document."
- "You stated [exact quoted sentence from background] — what is the evidence behind this claim?"
- "Why is [student's specific topic] relevant now — not five years ago and not in general?"
- "How does your background section lead logically to [student's specific stated problem]?"
- "Define [specific key term introduced in background] precisely without reading your document."
- "Which single source most shaped your background section and why?"
- "You mentioned [specific claim] — is this still true today, or has the situation changed?"
- "What would have been different about this study if conducted [5 years earlier]?"

**Sub-category B — Statement of the Problem (questions 6–10)**
Pick 5 from:
- "State your research problem in one sentence without looking at your document."
- "Why is [student's specific problem] a problem? Who specifically does it affect and how?"
- "What would happen if [specific problem] remained unsolved for the next ten years?"
- "You wrote: '[exact problem statement sentence]' — what evidence directly supports this claim?"
- "Why is this a research problem and not a practical challenge [relevant professional] could fix without a study?"
- "Has [student's specific problem] been studied in similar contexts? What justifies studying it here?"
- "You cited [real author, year] to support your problem — what exactly did that study find?"
- "How did you establish this was a genuine gap rather than something already addressed?"

**Sub-category C — Aims and Objectives (questions 11–15)**
Pick 5 from:
- "Explain the difference between your aim and your objectives without referring to the document."
- "How does Objective [N]: '[exact objective text]' directly address your stated problem?"
- "If you removed Objective [N] entirely, would your study still be complete? Why or why not?"
- "Which of your objectives was the most difficult to achieve and why?"
- "How will you know Objective [N] has been successfully met — what is your measure of success?"
- "Is there any aspect of your stated problem that none of your objectives address?"
- "Do your research questions map one-to-one to your objectives? Walk me through the mapping."
- "Are your objectives achievable within a single academic year at BSc level? Justify this."

**Sub-category D — Scope and Significance (questions 16–20)**
Pick 5 from:
- "What does your study deliberately not cover, and why did you draw the boundary there?"
- "Who are the primary beneficiaries of this research — be specific?"
- "What is the practical significance — what changes in [student's context] because of this work?"
- "What is the academic contribution — what does this add to knowledge in [student's discipline]?"
- "Could your scope have been broader? What would you gain or lose?"
- "If your study were never published, what would the field miss?"
- "What type of [relevant professional or organisation] could use your findings tomorrow?"
- "Is your study significant at a local, national, or international level — justify that claim."

**Sub-category E — Direct Sentence Challenges (questions 21–25)**
Pick 5 actual sentences from the student's Chapter One and challenge each directly:
- Quote a strong claim: "You wrote '[exact sentence]' — defend this with evidence."
- Quote a vague term: "You used '[term]' throughout — define it precisely."
- Quote an uncited claim: "You stated '[claim]' without a reference — where does this come from?"
- Quote an objective: "You wrote 'to [objective]' — what would success look like for this?"
- Quote a significance or scope sentence and ask the student to justify or defend it.

---

### Chapter Two — exactly 25 questions (5 per sub-category)

**Sub-category A — Breadth and Thematic Coverage (questions 1–5)**
Pick 5 from:
- "What are the three most important themes in your literature review and why those three?"
- "What major author or work in [student's field] did you not include, and why not?"
- "How did you decide which literature to include and which to leave out?"
- "If you reduced your review to its five most essential sources, which would you keep?"
- "Is your literature review current — does it reflect where [field] stands today?"
- "What is the oldest source you cited — [actual oldest source] — and is it still relevant?"
- "Which paragraph in your Chapter Two reflects the most original thinking on your part?"
- "Are there themes relevant to [student's topic] that your chapter does not cover — why?"

**Sub-category B — Critical Engagement with Sources (questions 6–10)**
Pick 5 from:
- "How do [real Author A, Year] and [real Author B, Year] agree or contradict each other on [specific topic]?"
- "Which study in your literature review do you most disagree with, and why?"
- "You cited [real author, year] — what were the limitations of that study?"
- "Did any source change your original thinking about [topic]? Which one and how?"
- "What is the strongest counter-argument to your research that you found in the literature?"
- "Did you find studies that directly contradict your main argument? How did you handle them?"
- "Is your review a summary of others' work, or do you make your own argument? Show me where."
- "Which source is cited most often in your review — why is it so central?"

**Sub-category C — Theoretical or Conceptual Framework (questions 11–15)**
Pick 5 from:
- "What [framework/theory] underpins your study, and why did you choose it over [real alternative]?"
- "If you had chosen [specific alternative framework], how would your study differ?"
- "Explain your conceptual framework without referring to your document."
- "How does your framework connect to each of your research objectives?"
- "Who developed [specific framework used], when, and what was its original context?"
- "Has [specific framework] been criticised in the literature — what do critics say?"
- "Does your framework actually guide your methodology, or is it only present in Chapter Two?"
- "What are the known limitations of [specific framework] — how did you account for them?"

**Sub-category D — Research Gap (questions 16–20)**
Pick 5 from:
- "State the research gap your study fills in two sentences — without reading the document."
- "How did you identify this gap — from reading, or as a prior assumption?"
- "Why is this gap worth filling at BSc level rather than requiring a higher-level study?"
- "Does Chapter Two lead logically to the gap you claim? Walk me through the argument."
- "Could a reader arrive at a different conclusion about the gap from your review?"
- "How long has this gap existed — why has it not been addressed before?"
- "Does your methodology actually address the gap identified, or something adjacent?"
- "Is the gap a knowledge gap, a methods gap, or a context gap — be specific?"

**Sub-category E — Specific Citation Challenges (questions 21–25)**
Pick 5 real citations from the student's Chapter Two and challenge each directly:
- "[Real Author, Year] — summarise the main finding in two sentences."
- "You used [real author, year] to support [specific claim] — does that source actually say that?"
- "You compared [real item A] and [real item B] — what was your conclusion?"
- "Your most recent citation is [real most recent] — is there more recent work you did not include?"
- "If [most important cited source] had reached the opposite conclusion, how would Chapter Two change?"

---

### Chapter Three — exactly 25 questions (5 per sub-category)

**Sub-category A — Research Design and Philosophy (questions 1–5)**
Pick 5 from:
- "What is your research design, and why did you choose it over [specific named alternative]?"
- "What philosophical assumptions underlie your methodology — positivist, interpretivist, pragmatist?"
- "How does your [specific design] directly enable you to answer each of your objectives?"
- "What are the known weaknesses of [student's design] — how did you mitigate them?"
- "Could a purely [alternative approach] have answered your research questions — why or why not?"
- "If you had unlimited time and resources, what methodology would you have used instead?"
- "What is the difference between your research design and your research method — explain with reference to your own project?"
- "If a critic said your design is not appropriate for your objectives, how would you respond?"

**Sub-category B — Population, Sample and Sampling (questions 6–10)**
Pick 5 from:
- "How did you determine your sample size of [real number]? Walk me through the reasoning."
- "Is your sample of [real number] representative of [real stated population]? How do you know?"
- "You used [real sampling technique] — why not [specific named alternative]?"
- "What are the limitations of [real sampling technique] for the conclusions you have drawn?"
- "Could your findings be generalised beyond [real study context]? To whom and under what conditions?"
- "Were there groups in your population excluded from your sample — why?"
- "If your sample had been half the size, would your conclusions still hold — explain?"
- "How did you access your sample — and could that access method have introduced bias?"

**Sub-category C — Data Collection Instrument (questions 11–15)**
Pick 5 from:
- "Walk me through your [real instrument type] — what does each section measure and why?"
- "How did you validate your instrument — did you pilot test it? What changed after the pilot?"
- "Why did you not use [specific named alternative instrument] instead?"
- "How did you ensure your questions did not lead respondents toward particular answers?"
- "How did you measure [specific real construct] — which exact item or question addressed it?"
- "If a participant misunderstood [specific question], how would that affect your results?"
- "Did you adapt your instrument from existing literature or create it from scratch — justify that?"
- "How many items were in your instrument and why that number specifically?"

**Sub-category D — Data Analysis (questions 16–20)**
Pick 5 from:
- "What analysis technique did you use, and why is it appropriate for your data type?"
- "Why did you not use [specific named alternative technique] for your analysis?"
- "Walk me step by step through how you went from raw data to the results in Chapter Four."
- "What software did you use — [real software] — and are you confident it was the right choice?"
- "How did you handle missing data, outliers, or invalid responses?"
- "What assumptions does [student's actual technique] make — were those assumptions met?"
- "Could you have used a simpler technique and gotten the same answer — what would you lose?"
- "If analysis produced an unexpected result, how would you determine if it was real or an error?"

**Sub-category E — Validity, Reliability and Ethics (questions 21–25)**
Pick 5 from:
- "How did you ensure validity — that you measured what you intended to measure?"
- "How did you ensure reliability — that another researcher would get similar results?"
- "What ethical procedures were followed before data collection — was ethical approval obtained?"
- "How did you protect the privacy and anonymity of your participants?"
- "What would have completely invalidated your methodology — did any of those risks materialise?"
- "Is your study internally valid — were there confounding variables you did not control?"
- "Is your study externally valid — can findings transfer to other contexts? Under what conditions?"
- "If a participant later withdrew consent, how would that have affected your results?"

---

### Chapter Four — exactly 25 questions (5 per sub-category)

**Sub-category A — Results Presentation and Interpretation (questions 1–5)**
Pick 5 from:
- "Walk me through your most important result — what does it show and what does it mean?"
- "Which result surprised you the most, and why?"
- "Take me through [real Table/Figure number] — explain every element without reading captions."
- "How did you decide what to include in your results and what to leave out?"
- "Which result is the weakest in terms of evidence — what would make it stronger?"
- "If your instrument produced flawed data you did not catch, how would that change your results?"
- "How would you present your key result to a non-technical audience in under one minute?"
- "Are there any results you found difficult to explain — how did you handle them?"

**Sub-category B — Objective-to-Result Mapping (questions 6–10)**
For each real objective, generate one question; pick 5 total:
- "How does [specific result or section] directly answer Objective [N]: '[exact text]'?"
- "Objective [N] asked you to [text] — where exactly in Chapter Four is this addressed?"
- "Which objective was hardest to address with your results, and why?"
- "Is any objective only partially answered by your results — which one and what is missing?"
- "Which result best demonstrates your overall aim has been achieved?"
- "Did any result go beyond what your objectives asked for — is that a strength or a problem?"
- "If you removed one result from Chapter Four, which would have the least impact on your objectives?"

**Sub-category C — Discussion Quality (questions 11–15)**
Pick 5 from:
- "How do your findings compare to [real cited study from Chapter Two] — confirm, contradict, or extend?"
- "What does [specific result] mean for the field — beyond just this study?"
- "Is [specific result value] strong or weak by the standards of the field — how do you know?"
- "Is there an alternative interpretation of your main finding you did not discuss?"
- "How confident are you in your results — and what would make you more confident?"
- "Which finding will be most useful to future researchers — and why?"
- "Did your discussion change your original hypothesis or expectations — in what way?"
- "Did your results challenge anything you stated in Chapter One or Two — how did you handle that?"

**Sub-category D — Evaluation Methodology (questions 16–20)**
Pick 5 from:
- "How did you evaluate your [system/model/output] — what specific criteria did you use and why?"
- "Why did you not use [specific named alternative evaluation method]?"
- "What benchmark did you compare your results against — where does that benchmark come from?"
- "Are your evaluation criteria subjective or objective — how does that affect credibility?"
- "What would a result have looked like for you to conclude your approach had failed?"
- "How do your evaluation results translate to real-world performance outside study conditions?"
- "Could your evaluation have been more rigorous — what would you change?"
- "Did participants know your objectives — could that have biased the evaluation results?"

**Sub-category E — Statistical or Technical Claim Challenges (questions 21–25)**
Pick 5 real figures, scores, or claims from Chapter Four and challenge each directly:
- "Your result shows [real value] — is that good enough for real-world use? By what standard?"
- "You reported [real statistic] — interpret that in plain language without technical jargon."
- "You achieved [real score/rate] — how does this compare to the best results in the literature?"
- "You stated [specific claim in discussion] — what in your results directly supports that claim?"
- "You described this result as [positive descriptor] — by whose standard is it [descriptor]?"

---

### Chapter Five — exactly 25 questions (5 per sub-category)

**Sub-category A — Conclusion Quality (questions 1–5)**
Pick 5 from:
- "Summarise your entire project in three sentences without reading from the document."
- "What is the single most important finding of your study?"
- "Does your conclusion answer your original aim — walk me through the connection."
- "What is new about your work — what does the world know now that it did not before?"
- "Is your conclusion supported entirely by your results, or do some claims go beyond your data?"
- "You concluded [specific conclusion] — would you say the same if your sample had been different?"
- "Is your conclusion too strong, too weak, or appropriately calibrated to your evidence?"
- "What is the one sentence from your conclusion you are most proud of — and why?"

**Sub-category B — Limitations (questions 6–10)**
Pick 5 from:
- "What is the most significant limitation — the one that most affects your findings' reliability?"
- "How might your limitation of [real stated limitation] have affected your results — give an example."
- "You mentioned [real limitation] — why did it arise? Could it have been avoided?"
- "Are there limitations you did NOT mention in Chapter Five that you should have?"
- "How would you redesign the study to overcome your main limitation?"
- "Do your limitations undermine your conclusions, or are they still valid despite them?"
- "Which limitation is a design flaw versus an unavoidable constraint — distinguish them."
- "If a reader applied your findings in [different context], which limitation should they know?"

**Sub-category C — Recommendations for Future Work (questions 11–15)**
Pick 5 from:
- "What should the next researcher in this area do — be specific, not general."
- "Are your recommendations derived from your limitations, or are they generic — justify each."
- "If you had one more year to extend this project, what would you do first and why?"
- "Which recommendation is most urgent for the field, and why?"
- "Are your recommendations feasible at BSc level, or do they require PhD-level resources?"
- "Who specifically should act on your recommendations — researchers, practitioners, or policymakers?"
- "Is there a recommendation you considered but chose not to include — why did you leave it out?"

**Sub-category D — Whole-Project Coherence (questions 16–20)**
Pick 5 from:
- "Does Chapter Five fully address everything promised in Chapter One — go through objective by objective."
- "Is there anything in Chapter Two you did not use in your methodology or discussion — why include it?"
- "Your Chapter Three describes [method] — did Chapter Four use it as described, or were there deviations?"
- "Does the tone of your conclusion match the strength of your results — are you overclaiming?"
- "If someone read only Chapter One and Chapter Five, would they get an accurate picture of the project?"
- "Which chapter is the weakest, and what would you do to strengthen it?"
- "If submitted as a journal article, what would reviewers most likely ask you to revise?"
- "Is there anything in Chapter Four that contradicts something in Chapter One or Two?"

**Sub-category E — Personal Ownership and Reflection (questions 21–25)**
Pick 5 from:
- "What was the most difficult decision you made during this project — do you stand by it?"
- "What would you do completely differently if you started from scratch?"
- "What has this project taught you that no taught course could?"
- "If [relevant real-world organisation] wanted to implement your solution tomorrow, what would they need?"
- "What is the weakest part of your project — be completely honest."
- "If another student submitted this project as their own, what question would immediately expose them?"
- "What would you say to a sceptical examiner who does not believe your findings are reliable?"
- "What is the one thing about this project you are most proud of?"

---

### General Questions — exactly 25 questions (5 per category)

Generate exactly 5 questions per general category, all specific to this student's actual project.

**Category 1 — Ownership and Intellectual Depth (questions 1–5)**
Pick 5 that test whether the student truly understands and owns their own work:
- Define a key technical term from the report without using the same word
- Trace one idea from Chapter One all the way through to the conclusion
- Explain a figure or table without reading the caption
- Identify the weakest paragraph in the project and explain what is wrong with it
- Explain the project to a complete non-expert in 30 seconds

**Category 2 — Methodology Justification (questions 6–10)**
Pick 5 that press on design decisions:
- Why THIS design and not [specific named alternative]?
- Why THIS sample size and not larger or smaller?
- Why THESE tools and not [named alternatives]?
- What would have completely invalidated the methodology?
- What would a hostile reviewer say is fundamentally wrong with the methodology?

**Category 3 — Literature and Theory (questions 11–15)**
Pick 5 that test depth of reading:
- Which three sources most shaped this project and how specifically?
- Is there a source this project should have cited but did not?
- Does the theoretical framework actually connect to the methodology or is it decorative?
- If the most important cited source had reached the opposite conclusion, how would the project change?
- What is the most contested idea in this field's literature right now?

**Category 4 — Results and Claims (questions 16–20)**
Pick 5 that challenge claims:
- What is the strongest claim in this project — is it fully substantiated by the data?
- What is the weakest claim — what additional evidence would make it credible?
- Are there alternative explanations for the main findings not considered in the discussion?
- What does the project NOT prove despite what the conclusion might suggest?
- What would falsify the main finding of this project?

**Category 5 — Real-World Application and Ethics (questions 21–25)**
Pick 5:
- If deployed today, what would break first?
- Who could be harmed by this work if misapplied?
- What ethical implications were not discussed in the report?
- Is this scalable beyond the study context — under what conditions?
- What would a professional practitioner in this field say about the quality of this work?

## Step 7 — Handle technical/conceptual gaps with web search

For every question where the report does not provide a sufficient answer, AND the question involves
a technical concept, methodology, framework, tool, or statistical technique:

1. Search the web for a clear, accurate explanation of that concept
2. Write a brief (3–5 sentence) supplementary answer labelled `[From general knowledge]`
3. Write a study nudge directing the student to understand the concept before their defence

Examples of concepts that commonly require this:
- Statistical techniques (Cronbach's alpha, regression, SEM, t-test, chi-square)
- Sampling theory (power analysis, saturation, representativeness)
- Software tools (SPSS, R, Python libraries, SmartPLS, NVivo)
- Frameworks and models (TAM, UTAUT, DeLone & McLean, Agile, SDLC variants)
- Evaluation methods (SUS, ISO standards, benchmarking)
- Research philosophy terms (positivism, ontology, epistemology)
- Programming/technical concepts (APIs, databases, design patterns, protocols)

---

## Step 8 — Compile the JSON

**BEFORE writing the JSON, verify your counts:**
- Each chapter must have exactly 25 questions (count them)
- General section must have exactly 25 questions (5 per category)
- Total should be 150 questions (125 chapter + 25 general)
- If any chapter is short, generate the missing questions before proceeding

After verifying counts, write `/tmp/defence_questions.json` in this format:

```json
{
  "student_name": "Firstname Lastname",
  "project_title": "Full project title",
  "chapters": {
    "chapter1": {
      "title": "Introduction",
      "questions": [
        {
          "number": 1,
          "text": "Full question text — specific to the student's report",
          "tag": "Challenge",
          "answer": "In my project, I argued that... [drawn from report]. The key evidence I used was... [from report].",
          "answer_source": "From your report",
          "nudge": "📚 Study nudge: You should also be able to explain [concept] more precisely. Read [specific suggestion]. This is likely to come up because [reason]."
        }
      ]
    }
  },
  "general": {
    "categories": [
      {
        "name": "Ownership and Intellectual Depth",
        "questions": [
          {
            "number": 1,
            "text": "Full question text",
            "tag": "Ownership",
            "answer": "Model answer text",
            "answer_source": "From your report",
            "nudge": null
          }
        ]
      }
    ]
  },
  "tip": "A personalised preparation tip for the student based on what you found in their report."
}
```

**nudge field**: use a string when a nudge is needed; use `null` when the report gives a complete answer.

---

## Step 9 — Run the report generation script

```bash
node /home/claude/bsc-defence-questions/scripts/generate_questions_doc.js \
  --questions-file /tmp/defence_questions.json \
  --output /mnt/user-data/outputs/DefenceQA_<lastname>.docx
```

If the script is not present, write it fresh from the template in `scripts/generate_questions_doc.js` in this skill package before running.

---

## Step 10 — Present the output

After the script runs, call `present_files` with the output path.

Then tell the student:
- Total questions generated
- How many questions have study nudges (gaps to address before the defence)
- Top 3 areas to focus preparation on, based on what was found in their report
