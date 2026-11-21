"""Narration for "Adipose Tissue: Your Body's Energy Bank".

Each scene is a list of sentences. Sentences are synthesized one by one so the
renderer knows exactly when each one starts (for subtitles and animation cues).
"""

TITLE = "Adipose Tissue"
SUBTITLE = "Your Body's Energy Bank"

SCENES = [
    {
        "id": "hook",
        "sentences": [
            "About a fifth of a healthy body is made of one tissue we love to complain about: fat.",
            "But adipose tissue is far more than a storage bin.",
            "It's an organ with real jobs.",
            "Let's see how it works.",
        ],
    },
    {
        "id": "what",
        "sentences": [
            "Adipose tissue is a specialized connective tissue built from cells called adipocytes.",
            "Their main job is storing energy as lipids.",
            "Between the cells sits a thin mesh of reticular fibers, plus blood vessels and nerves.",
            "This tissue is richly supplied, because it's metabolically active.",
        ],
    },
    {
        "id": "where",
        "sentences": [
            "By location, we split fat into two groups.",
            "Subcutaneous fat sits just under the skin.",
            "Visceral fat surrounds your internal organs, like the kidneys and even the eyeballs.",
            "Subcutaneous fat helps with insulation.",
            "Visceral fat acts as a cushion that protects the organs from impact.",
        ],
    },
    {
        "id": "types",
        "sentences": [
            "By structure, there are three types of adipocytes.",
            "White adipocytes are the classic fat cells.",
            "Each one holds a single large lipid droplet that pushes the nucleus to the edge.",
            "Brown adipocytes are smaller and hold many little droplets, packed around a central nucleus.",
            "They contain lots of mitochondria, which gives them the brown color.",
            "The third type, beige adipocytes, was discovered more recently.",
            "They look like brown cells but live scattered inside white fat.",
        ],
    },
    {
        "id": "white",
        "sentences": [
            "White fat dominates in adults.",
            "Most of it lies in the layer beneath the skin.",
            "Its distribution differs between the sexes: women tend to carry more around the thighs and breasts, men more around the abdomen.",
            "Under the microscope, the fat droplets dissolve during slide preparation, leaving a delicate net of empty-looking cells.",
        ],
    },
    {
        "id": "brown",
        "sentences": [
            "Brown fat is the body's built-in heater.",
            "Newborns have plenty of it, about five percent of body mass, because they can't regulate temperature well yet.",
            "It burns energy to make heat instead of storing it.",
            "With age most of it disappears, but small amounts remain in adults, around the neck, between the shoulder blades, and near major vessels.",
        ],
    },
    {
        "id": "endocrine",
        "sentences": [
            "For a long time, fat was seen as a passive fuel tank.",
            "Today we know it's also an endocrine organ.",
            "It releases hormones such as leptin, which signals fullness, and adiponectin.",
            "These messengers reach the liver, pancreas, muscles and brain.",
            "Abdominal fat in particular has a strong influence on insulin resistance.",
        ],
    },
    {
        "id": "wrong",
        "sentences": [
            "Too much fat, or obesity, raises the risk of high blood pressure, type 2 diabetes, heart disease and stroke.",
            "Too little, as in the rare conditions called lipodystrophies, brings its own metabolic problems.",
            "The goal isn't zero fat.",
            "It's a healthy amount in the right places.",
        ],
    },
    {
        "id": "outro",
        "sentences": [
            "Fat tissue stores energy, cushions organs, keeps you warm and sends hormonal signals.",
            "Understand it, and you can work with your body instead of against it.",
            "Thanks for watching.",
        ],
    },
]

# Pronunciation helpers: text sent to TTS may differ from the subtitle text.
TTS_REPLACEMENTS = {
    "type 2": "type two",
    "lipodystrophies": "lipo-dystrophies",
}


# ---------------------------------------------------------------- 45 s reel cut
# Each reel scene reuses a full-video scene ("uses") with new, shorter narration.
# "map" retimes the original scene's sentence cues onto the reel sentences:
#   original_index: (reel_sentence, start_fraction, end_fraction)
# Original cues that are not mapped never fire.
REEL = [
    {
        "id": "r_hook", "uses": "hook",
        "sentences": [
            "About a fifth of your body is fat.",
            "But adipose tissue isn't just storage.",
            "It's an active organ with real jobs.",
        ],
        "map": {0: (0, 0, 1), 1: (1, 0, 1), 2: (2, 0, 1)},
    },
    {
        "id": "r_what", "uses": "what",
        "sentences": ["It's built from cells called adipocytes, which store energy as lipids."],
        "map": {0: (0, 0, 0.55), 1: (0, 0.6, 1)},
    },
    {
        "id": "r_types", "uses": "types",
        "sentences": [
            "White fat cells hold one big droplet.",
            "Brown ones hold many small droplets, and burn energy for heat.",
            "Beige cells are a mix of both.",
        ],
        "map": {0: (0, 0, 0.3), 1: (0, 0, 0.5), 2: (0, 0.3, 1), 3: (1, 0, 0.5), 4: (1, 0.4, 1),
                5: (2, 0, 0.6), 6: (2, 0.3, 1)},
    },
    {
        "id": "r_where", "uses": "where",
        "sentences": ["Under the skin, fat insulates.", "Around your organs, it cushions them."],
        "map": {0: (0, 0, 0.15), 1: (0, 0, 0.5), 3: (0, 0.45, 1), 2: (1, 0, 0.5), 4: (1, 0.4, 1)},
    },
    {
        "id": "r_endocrine", "uses": "endocrine",
        "sentences": ["It also releases hormones, like leptin, that signal your brain, liver and muscles."],
        "map": {1: (0, 0, 0.15), 2: (0, 0.08, 0.45), 3: (0, 0.45, 1)},
    },
    {
        "id": "r_wrong", "uses": "wrong",
        "sentences": ["Too much or too little causes problems.", "The goal is a healthy amount, in the right places."],
        "map": {0: (0, 0, 0.55), 1: (0, 0.35, 1), 2: (1, 0, 0.3), 3: (1, 0.3, 1)},
    },
    {
        "id": "r_outro", "uses": "outro",
        "sentences": ["Follow for more body science."],
        "map": {2: (0, 0, 1)},
    },
]
