"""Conservative default educational supplement entries (used by seeding)."""

DEFAULT_SUPPLEMENTS = [
    {
        "name": "Creatine monohydrate",
        "category": "performance",
        "purpose": "Supports high-intensity strength and power output and may aid "
                   "lean-mass gains alongside resistance training.",
        "evidence_summary": "One of the most-studied sports supplements; consistent "
                            "small-to-moderate benefits for repeated high-intensity efforts.",
        "default_dose": "3–5",
        "dose_unit": "g/day",
        "timing": "Any consistent time of day; with a meal is fine.",
        "frequency": "Daily (maintenance protocol; no loading phase required)",
        "bodyweight_based": False,
        "maximum_recommended_amount": "5 g/day is a standard maintenance dose.",
        "warnings": "May cause 1–3 lb of water-weight gain. Stay hydrated.",
        "interactions": "Discuss with a physician if you have kidney disease or take "
                        "nephroactive medication.",
        "contraindications": "Pre-existing kidney disease without medical supervision.",
    },
    {
        "name": "Magnesium",
        "category": "vitamin_mineral",
        "purpose": "Supports normal muscle and nervous-system function; useful when "
                   "dietary intake is below the recommended amount.",
        "evidence_summary": "Benefits are clearest when correcting a dietary shortfall. "
                            "Total dietary requirement (RDA ~310–420 mg/day for adults) "
                            "includes food — supplemental magnesium only tops up the gap.",
        "default_dose": "100–200",
        "dose_unit": "mg/day (supplemental, elemental)",
        "timing": "Evening, with food, if it causes GI upset.",
        "frequency": "Daily if diet is short",
        "bodyweight_based": False,
        "maximum_recommended_amount": "Keep supplemental magnesium at or below 350 mg/day "
                                      "(the tolerable upper intake for supplements).",
        "warnings": "High doses can cause loose stools; oxide form is poorly absorbed.",
        "interactions": "Can affect absorption of certain antibiotics and medications — "
                        "separate dosing by 2+ hours and ask a pharmacist.",
        "contraindications": "Kidney impairment without medical supervision.",
    },
    {
        "name": "Caffeine",
        "category": "performance",
        "purpose": "Acute performance aid for training sessions; reduces perceived effort.",
        "evidence_summary": "Well-supported ergogenic aid. Common effective range is about "
                            "1.5–3 mg per kg bodyweight taken 30–60 minutes pre-training. "
                            "Tolerance, sleep, and total daily intake matter.",
        "default_dose": "100–200",
        "dose_unit": "mg pre-workout",
        "timing": "30–60 minutes before training; avoid within 8 hours of bedtime.",
        "frequency": "Training days as tolerated",
        "bodyweight_based": True,
        "maximum_recommended_amount": "Keep total daily intake from all sources at or "
                                      "below ~400 mg for most healthy adults.",
        "warnings": "Can disturb sleep, raise heart rate, and cause jitters or anxiety. "
                    "Account for coffee and energy drinks in the daily total.",
        "interactions": "Stimulant medications, some antidepressants; discuss with a "
                        "physician if you have heart-rhythm or blood-pressure issues.",
        "contraindications": "Uncontrolled hypertension, arrhythmia, pregnancy (limit per "
                             "medical guidance), caffeine sensitivity.",
    },
    {
        "name": "Protein powder (whey or plant)",
        "category": "protein",
        "purpose": "Convenient way to reach the daily protein target when whole-food "
                   "protein falls short.",
        "evidence_summary": "Food-first: it is a food supplement, not a requirement. "
                            "Useful for hitting protein targets around a busy schedule.",
        "default_dose": "20–40",
        "dose_unit": "g per serving",
        "timing": "Any time; often post-workout or as a snack.",
        "frequency": "As needed to reach the daily protein target",
        "bodyweight_based": False,
        "maximum_recommended_amount": "No specific limit beyond the daily protein target.",
        "warnings": "Whey contains dairy; choose plant or isolate options if lactose "
                    "intolerant.",
        "interactions": "",
        "contraindications": "Dairy allergy (for whey).",
    },
    {
        "name": "Electrolytes",
        "category": "hydration",
        "purpose": "Replace sodium/potassium/magnesium lost in sweat during long or hot "
                   "training sessions.",
        "evidence_summary": "Most useful for sessions over ~60–90 minutes, heavy sweaters, "
                            "or hot environments. Shorter sessions rarely need them.",
        "default_dose": "Per product label",
        "dose_unit": "serving",
        "timing": "During or after long/hot sessions.",
        "frequency": "As conditions warrant",
        "bodyweight_based": False,
        "maximum_recommended_amount": "Follow the product label; account for dietary sodium.",
        "warnings": "People on sodium-restricted diets should check with their physician.",
        "interactions": "Blood-pressure medication, diuretics.",
        "contraindications": "Medically restricted sodium or potassium intake.",
    },
    {
        "name": "Fish oil (EPA/DHA)",
        "category": "general_health",
        "purpose": "Source of omega-3 fatty acids when oily-fish intake is low.",
        "evidence_summary": "Food-first: two servings of oily fish per week covers most "
                            "needs. Supplementation is a convenience alternative.",
        "default_dose": "1–2",
        "dose_unit": "g combined EPA+DHA/day",
        "timing": "With meals.",
        "frequency": "Daily if fish intake is low",
        "bodyweight_based": False,
        "maximum_recommended_amount": "Stay at or below 3 g/day EPA+DHA unless medically "
                                      "directed.",
        "warnings": "Mild GI upset or fishy aftertaste possible.",
        "interactions": "Blood thinners (anticoagulants) — consult a physician.",
        "contraindications": "Fish/shellfish allergy (check source), upcoming surgery "
                             "(discuss with your surgeon).",
    },
    {
        "name": "Vitamin D3",
        "category": "vitamin_mineral",
        "purpose": "Supports normal bone and immune function when sun exposure and "
                   "dietary intake are limited.",
        "evidence_summary": "Most useful for people with low blood levels — ideally "
                            "confirmed by a blood test rather than assumed. Not "
                            "automatically prescribed at high doses.",
        "default_dose": "1000–2000",
        "dose_unit": "IU/day",
        "timing": "With a fat-containing meal.",
        "frequency": "Daily, mainly in low-sunlight months",
        "bodyweight_based": False,
        "maximum_recommended_amount": "Do not exceed 4000 IU/day without physician "
                                      "supervision and blood-level monitoring.",
        "warnings": "Fat-soluble — excess accumulates. Megadoses are not appropriate "
                    "without testing.",
        "interactions": "Certain diuretics, steroids, and weight-loss drugs.",
        "contraindications": "Hypercalcemia, granulomatous disease, kidney stones history "
                             "(seek medical guidance).",
    },
]
