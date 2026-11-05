"""Built-in voice presets.

Copied from OpenVoiceChanger (MIT License, Copyright (c) 2024 Sioaeko)
https://github.com/sioaeko/OpenVoiceChanger  backend/services/preset_store.py (BUILTIN_PRESETS)
"""

BUILTIN_PRESETS = [
    {
        "id": "clean",
        "name": "Clean",
        "emoji": "🎙️",
        "description": "No coloration — raw model or mic output",
        "settings": {"pitch_shift": 0, "formant_shift": 0, "effects": {}},
    },
    {
        "id": "chipmunk",
        "name": "Chipmunk",
        "emoji": "🐿️",
        "description": "High pitch, bright formants",
        "settings": {
            "pitch_shift": 7,
            "formant_shift": 4,
            "effects": {},
        },
    },
    {
        "id": "helium",
        "name": "Helium",
        "emoji": "🎈",
        "description": "Balloon-gas timbre, mostly formants",
        "settings": {
            "pitch_shift": 3,
            "formant_shift": 7,
            "effects": {},
        },
    },
    {
        "id": "deep",
        "name": "Deep Voice",
        "emoji": "🎩",
        "description": "Lowered pitch with darker formants",
        "settings": {
            "pitch_shift": -6,
            "formant_shift": -4,
            "effects": {"eq": {"enabled": True, "low": 4, "high": -2}},
        },
    },
    {
        "id": "monster",
        "name": "Monster",
        "emoji": "👹",
        "description": "Growling low pitch with drive",
        "settings": {
            "pitch_shift": -9,
            "formant_shift": -5,
            "effects": {
                "distortion": {"enabled": True, "drive": 0.45},
                "reverb": {"enabled": True, "size": 0.35, "mix": 0.25},
            },
        },
    },
    {
        "id": "robot",
        "name": "Robot",
        "emoji": "🤖",
        "description": "Ring-mod metal voice with bit reduction",
        "settings": {
            "pitch_shift": 0,
            "formant_shift": 0,
            "effects": {
                "robot": {"enabled": True, "freq": 90},
                "bitcrush": {"enabled": True, "bits": 10, "down": 2},
            },
        },
    },
    {
        "id": "alien",
        "name": "Alien",
        "emoji": "👽",
        "description": "Slow ring-mod wobble with chorus",
        "settings": {
            "pitch_shift": 2,
            "formant_shift": 2,
            "effects": {
                "robot": {"enabled": True, "freq": 28},
                "chorus": {"enabled": True, "rate": 1.6, "depth": 0.7, "mix": 0.5},
            },
        },
    },
    {
        "id": "whisper",
        "name": "Whisper",
        "emoji": "🤫",
        "description": "Breathy noise-excited voice",
        "settings": {
            "pitch_shift": 0,
            "formant_shift": 0,
            "effects": {
                "whisper": {"enabled": True, "mix": 0.85},
                "gain": {"enabled": True, "db": 4},
            },
        },
    },
    {
        "id": "ghost",
        "name": "Ghost",
        "emoji": "👻",
        "description": "Whispery echoes in a large space",
        "settings": {
            "pitch_shift": -2,
            "formant_shift": 0,
            "effects": {
                "whisper": {"enabled": True, "mix": 0.6},
                "reverb": {"enabled": True, "size": 0.85, "mix": 0.5},
                "echo": {"enabled": True, "time": 0.42, "feedback": 0.45, "mix": 0.3},
            },
        },
    },
    {
        "id": "telephone",
        "name": "Telephone",
        "emoji": "📞",
        "description": "Narrowband landline call",
        "settings": {
            "pitch_shift": 0,
            "formant_shift": 0,
            "effects": {
                "telephone": {"enabled": True},
                "compressor": {"enabled": True, "threshold": -24, "ratio": 4},
            },
        },
    },
    {
        "id": "megaphone",
        "name": "Megaphone",
        "emoji": "📣",
        "description": "Distorted PA horn",
        "settings": {
            "pitch_shift": 0,
            "formant_shift": 0,
            "effects": {
                "telephone": {"enabled": True},
                "distortion": {"enabled": True, "drive": 0.55},
                "gain": {"enabled": True, "db": 3},
            },
        },
    },
    {
        "id": "radio",
        "name": "Radio DJ",
        "emoji": "📻",
        "description": "Broadcast warmth and compression",
        "settings": {
            "pitch_shift": 0,
            "formant_shift": 0,
            "effects": {
                "eq": {"enabled": True, "low": 3, "high": 2},
                "compressor": {"enabled": True, "threshold": -26, "ratio": 5},
                "gain": {"enabled": True, "db": 2},
            },
        },
    },
    {
        "id": "cave",
        "name": "Cave",
        "emoji": "🕳️",
        "description": "Long dark echoes",
        "settings": {
            "pitch_shift": 0,
            "formant_shift": 0,
            "effects": {
                "reverb": {"enabled": True, "size": 0.85, "mix": 0.45},
                "echo": {"enabled": True, "time": 0.35, "feedback": 0.5, "mix": 0.35},
                "eq": {"enabled": True, "low": 2, "high": -4},
            },
        },
    },
    {
        "id": "stadium",
        "name": "Stadium",
        "emoji": "🏟️",
        "description": "Huge announcement reverb",
        "settings": {
            "pitch_shift": 0,
            "formant_shift": 0,
            "effects": {
                "echo": {"enabled": True, "time": 0.6, "feedback": 0.4, "mix": 0.4},
                "reverb": {"enabled": True, "size": 1.0, "mix": 0.5},
                "compressor": {"enabled": True, "threshold": -20, "ratio": 3},
            },
        },
    },
    {
        "id": "underwater",
        "name": "Underwater",
        "emoji": "🌊",
        "description": "Muffled, slowly wobbling depths",
        "settings": {
            "pitch_shift": 0,
            "formant_shift": -2,
            "effects": {
                "eq": {"enabled": True, "low": 6, "high": -12},
                "chorus": {"enabled": True, "rate": 0.3, "depth": 0.8, "mix": 0.6},
            },
        },
    },
    {
        "id": "arcade",
        "name": "Arcade",
        "emoji": "🕹️",
        "description": "8-bit crushed game cabinet voice",
        "settings": {
            "pitch_shift": 2,
            "formant_shift": 0,
            "effects": {
                "bitcrush": {"enabled": True, "bits": 6, "down": 6},
                "eq": {"enabled": True, "low": -2, "high": 4},
            },
        },
    },
]

PRESETS_BY_ID = {p["id"]: p for p in BUILTIN_PRESETS}
