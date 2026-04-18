# test_data.py
# ─────────────────────────────────────────────────────────────
# Labelled test sentences for model evaluation
# Label 2 = High Risk, 1 = Moderate Risk, 0 = Low Risk
# ─────────────────────────────────────────────────────────────

TEST_DATA = [

    # ── HIGH RISK — label 2 ───────────────────────────────────
    ("I feel completely hopeless and want to die",                      2),
    ("I cant go on anymore, there is no reason to live",               2),
    ("I have been thinking about ending my life",                      2),
    ("I want to harm myself, I cant take it anymore",                  2),
    ("Suicide feels like the only way out for me",                     2),
    ("I feel worthless and better off dead",                           2),
    ("I tried to cut myself last night",                               2),
    ("I have been planning to overdose on my medication",              2),
    ("Nobody cares about me, I want to disappear forever",             2),
    ("I decided I cant go on any longer",                              2),
    ("I dont want to be here anymore, nothing matters",                2),
    ("I feel so hopeless, cant stop thinking about unaliving",         2),
    ("I want to hurt myself, the pain is too much",                    2),
    ("Better off without me, I should just end it all",                2),
    ("I have no reason to keep living, I give up",                     2),

    # ── MODERATE RISK — label 1 ───────────────────────────────
    ("I have been feeling really depressed and anxious for weeks",     1),
    ("Everything feels empty and I have been struggling badly",        1),
    ("I feel overwhelmed and exhausted, I cant stop crying",           1),
    ("I have been suffering from panic attacks every day",             1),
    ("I feel numb and disconnected from everything around me",         1),
    ("I am exhausted and feel completely helpless lately",             1),
    ("I feel so lost and broken, nothing brings me joy",               1),
    ("I have been dealing with a lot of trauma and feel desperate",    1),
    ("I feel alone and scared, struggling to get through each day",    1),
    ("I am deeply struggling with my mental health right now",         1),
    ("Feeling broken and empty inside, grief is overwhelming me",      1),
    ("I feel desperate and hurting, dont know how much more I can take",1),

    # ── LOW RISK — label 0 ────────────────────────────────────
    ("I have had a rough week and feeling a bit stressed",             0),
    ("Feeling a little worried about my exams but I will manage",      0),
    ("Today was difficult, feeling frustrated after an argument",      0),
    ("I have been feeling a bit down lately but nothing serious",      0),
    ("I am nervous about a job interview tomorrow",                    0),
    ("Feeling a bit lonely today since my friends are busy",           0),
    ("Just tired from work, need some rest this weekend",              0),
    ("A little upset about something that happened at school",         0),
    ("Feeling confused about a decision I need to make",               0),
    ("Had a bad day but things will get better I think",               0),

    # ── EDGE CASES ────────────────────────────────────────────
    ("not hopeless, actually feeling okay today",                      0),
    ("I am not sad or worried, things are going well",                 0),
    ("I want to harm someone, I am so angry",                         1),
    ("cant go on",                                                     2),
    ("I dont want to be here anymore",                                 2),
]