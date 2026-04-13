"""
LED Effects Library — curated presets from major RGB ecosystems.

Sources/inspiration:
  - OpenRGB (open source, 1000+ devices)
  - Philips Hue (smart home lighting scenes)
  - Razer Chroma (gaming effects)
  - Corsair iCUE (peripheral effects)
  - ASUS Aura Sync (motherboard/peripheral effects)
  - MSI Mystic Light (gaming laptop effects)
  - SteelSeries Engine (keyboard effects)
  - Alienware AlienFX (Dell gaming effects)
  - NZXT CAM (case/AIO effects)
  - SignalRGB (community effects)

All effects are defined as portable presets that can be applied to
any device supporting the corresponding capability.

Zero telemetry. Zero external calls. Just pretty lights.
"""

from dataclasses import dataclass, field
from enum import IntEnum


class EffectType(IntEnum):
    """How the effect animates."""
    STATIC = 0        # Solid color, no animation
    BREATHING = 1     # Fade in/out
    CYCLE = 2         # Cycle through colors
    WAVE = 3          # Color wave across LEDs
    REACTIVE = 4      # React to key presses
    GRADIENT = 5      # Static gradient across LEDs
    RAIN = 6          # Random drops (like Matrix)
    RIPPLE = 7        # Ripple from press point
    STARLIGHT = 8     # Random twinkling
    FIRE = 9          # Fire/lava animation
    AUDIO = 10        # React to audio (if supported)
    TEMPERATURE = 11  # Color shifts with CPU/GPU temp
    CUSTOM = 99       # User-defined


@dataclass
class Color:
    r: int = 0
    g: int = 0
    b: int = 0

    @classmethod
    def hex(cls, h: str) -> "Color":
        h = h.lstrip("#")
        return cls(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    def to_tuple(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)

    def __str__(self):
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"


@dataclass
class EffectPreset:
    """A named LED effect preset."""
    name: str
    description: str
    effect_type: EffectType
    colors: list[Color] = field(default_factory=list)
    speed: int = 3        # 1=slow, 5=fast
    brightness: int = 80  # 0-100
    direction: int = 0    # 0=default, 1=reverse
    category: str = ""    # Grouping tag
    source: str = ""      # Which ecosystem inspired this


# ============================================================
#  PRESET LIBRARY
# ============================================================

PRESETS: list[EffectPreset] = [

    # --- SOLID COLORS ---
    EffectPreset("Arctic White", "Clean white. Like a fresh install.", EffectType.STATIC,
                 [Color.hex("#ffffff")], category="Solid", source="Universal"),
    EffectPreset("Midnight Off", "Lights out. Stealth mode.", EffectType.STATIC,
                 [Color.hex("#000000")], category="Solid", source="Universal"),
    EffectPreset("Electric Blue", "The classic gamer blue.", EffectType.STATIC,
                 [Color.hex("#0066ff")], category="Solid", source="Corsair iCUE"),
    EffectPreset("Dragon Red", "MSI's signature. Fear the dragon.", EffectType.STATIC,
                 [Color.hex("#ff1a1a")], category="Solid", source="MSI Mystic Light"),
    EffectPreset("ROG Red", "Republic of Gamers energy.", EffectType.STATIC,
                 [Color.hex("#cc0000")], category="Solid", source="ASUS Aura"),
    EffectPreset("Alien Cyan", "Alienware teal. Otherworldly.", EffectType.STATIC,
                 [Color.hex("#00e5ff")], category="Solid", source="Alienware AlienFX"),
    EffectPreset("Razer Green", "The snake's signature.", EffectType.STATIC,
                 [Color.hex("#00ff00")], category="Solid", source="Razer Chroma"),
    EffectPreset("Corsair Yellow", "Sails of victory.", EffectType.STATIC,
                 [Color.hex("#ffcc00")], category="Solid", source="Corsair iCUE"),
    EffectPreset("NZXT Purple", "Build it beautiful.", EffectType.STATIC,
                 [Color.hex("#7b2fbe")], category="Solid", source="NZXT CAM"),
    EffectPreset("SteelSeries Orange", "Precision. Steel. Orange.", EffectType.STATIC,
                 [Color.hex("#ff6600")], category="Solid", source="SteelSeries Engine"),
    EffectPreset("HyperX Red", "Kingston's fury unleashed.", EffectType.STATIC,
                 [Color.hex("#e60012")], category="Solid", source="HyperX NGENUITY"),
    EffectPreset("Logitech Blue", "G-series blue.", EffectType.STATIC,
                 [Color.hex("#00b8fc")], category="Solid", source="Logitech G HUB"),

    # --- BREATHING / PULSE ---
    EffectPreset("Calm Pulse", "Slow breathing. Like meditation for your desk.",
                 EffectType.BREATHING, [Color.hex("#3b82f6")],
                 speed=2, category="Ambient", source="Philips Hue"),
    EffectPreset("Heartbeat Red", "Your PC has a pulse. It's alive.",
                 EffectType.BREATHING, [Color.hex("#ef4444")],
                 speed=3, category="Ambient", source="Razer Chroma"),
    EffectPreset("Ocean Breath", "In... out... like waves on a beach.",
                 EffectType.BREATHING, [Color.hex("#0ea5e9"), Color.hex("#0d9488")],
                 speed=2, category="Ambient", source="Philips Hue"),
    EffectPreset("Neon Pulse", "Cyberpunk vibes in your peripheral vision.",
                 EffectType.BREATHING, [Color.hex("#f0abfc"), Color.hex("#818cf8")],
                 speed=3, category="Ambient", source="SignalRGB"),
    EffectPreset("Aurora Pulse", "Northern lights, desktop edition.",
                 EffectType.BREATHING, [Color.hex("#22c55e"), Color.hex("#0ea5e9"), Color.hex("#8b5cf6")],
                 speed=2, category="Ambient", source="NZXT CAM"),

    # --- SPECTRUM / CYCLE ---
    EffectPreset("Full Spectrum", "Every color. No commitment issues.",
                 EffectType.CYCLE, [], speed=3, category="Dynamic", source="OpenRGB"),
    EffectPreset("Slow Spectrum", "Rainbow, but make it classy.",
                 EffectType.CYCLE, [], speed=1, category="Dynamic", source="Corsair iCUE"),
    EffectPreset("Fast Rave", "Your keyboard at 3am. No judgment.",
                 EffectType.CYCLE, [], speed=5, category="Dynamic", source="Razer Chroma"),

    # --- WAVE ---
    EffectPreset("Rainbow Wave", "The classic. Never gets old. (It does.)",
                 EffectType.WAVE, [], speed=3, category="Dynamic", source="OpenRGB"),
    EffectPreset("Ocean Wave", "Blue-green waves rolling across your keys.",
                 EffectType.WAVE, [Color.hex("#0066cc"), Color.hex("#00ccaa"), Color.hex("#004488")],
                 speed=2, category="Dynamic", source="Corsair iCUE"),
    EffectPreset("Lava Flow", "Volcanic RGB. Hot stuff.",
                 EffectType.WAVE, [Color.hex("#ff3300"), Color.hex("#ff6600"), Color.hex("#ffcc00")],
                 speed=3, category="Dynamic", source="MSI Mystic Light"),
    EffectPreset("Matrix Rain", "You've been living in a dream world, Neo.",
                 EffectType.RAIN, [Color.hex("#00ff41")],
                 speed=4, category="Dynamic", source="SignalRGB"),
    EffectPreset("Purple Haze", "Excuse me while I light my keyboard.",
                 EffectType.WAVE, [Color.hex("#7c3aed"), Color.hex("#c084fc"), Color.hex("#4c1d95")],
                 speed=2, category="Dynamic", source="ASUS Aura"),

    # --- REACTIVE ---
    EffectPreset("Ripple Blue", "Your keypresses make waves. Deep.",
                 EffectType.RIPPLE, [Color.hex("#3b82f6")],
                 speed=3, category="Reactive", source="Razer Chroma"),
    EffectPreset("Ripple White", "Clean ripples. Minimal effort, maximum flex.",
                 EffectType.RIPPLE, [Color.hex("#ffffff")],
                 speed=3, category="Reactive", source="SteelSeries Engine"),
    EffectPreset("Starlight", "Random sparkles. Like your code quality.",
                 EffectType.STARLIGHT, [Color.hex("#ffffff"), Color.hex("#60a5fa")],
                 speed=3, category="Reactive", source="Corsair iCUE"),

    # --- GRADIENT ---
    EffectPreset("Sunset", "Golden hour on your desk.",
                 EffectType.GRADIENT, [Color.hex("#f97316"), Color.hex("#ec4899"), Color.hex("#8b5cf6")],
                 category="Gradient", source="Philips Hue"),
    EffectPreset("Ice & Fire", "Song of your CPU and GPU temps.",
                 EffectType.GRADIENT, [Color.hex("#3b82f6"), Color.hex("#8b5cf6"), Color.hex("#ef4444")],
                 category="Gradient", source="SignalRGB"),
    EffectPreset("Forest", "Touch grass, digitally.",
                 EffectType.GRADIENT, [Color.hex("#064e3b"), Color.hex("#059669"), Color.hex("#a7f3d0")],
                 category="Gradient", source="Philips Hue"),
    EffectPreset("Vaporwave", "A E S T H E T I C",
                 EffectType.GRADIENT, [Color.hex("#ff6ec7"), Color.hex("#7873f5"), Color.hex("#00d4ff")],
                 category="Gradient", source="SignalRGB"),
    EffectPreset("Thermal Map", "Colors shift with your CPU temp. Science!",
                 EffectType.TEMPERATURE, [Color.hex("#3b82f6"), Color.hex("#22c55e"),
                                          Color.hex("#f59e0b"), Color.hex("#ef4444")],
                 category="Smart", source="LightDeck Original"),

    # --- PRODUCTIVITY / WORK ---
    EffectPreset("Focus White", "Pure white. No distractions. Just work.",
                 EffectType.STATIC, [Color.hex("#e8e8e8")],
                 brightness=60, category="Work", source="Philips Hue"),
    EffectPreset("Warm Reading", "Easy on the eyes for late sessions.",
                 EffectType.STATIC, [Color.hex("#ffa94d")],
                 brightness=40, category="Work", source="Philips Hue"),
    EffectPreset("Night Owl", "Dim red for 2am coding. Your retinas thank you.",
                 EffectType.STATIC, [Color.hex("#7f1d1d")],
                 brightness=25, category="Work", source="LightDeck Original"),
    EffectPreset("Deep Work", "Minimal purple. Dopamine optional.",
                 EffectType.STATIC, [Color.hex("#2e1065")],
                 brightness=30, category="Work", source="LightDeck Original"),

    # --- FIRE/SPECIAL ---
    EffectPreset("Campfire", "Warm flickering. S'mores not included.",
                 EffectType.FIRE, [Color.hex("#ff4500"), Color.hex("#ff8c00"), Color.hex("#ffd700")],
                 speed=3, category="Special", source="NZXT CAM"),
    EffectPreset("Police Siren", "Red/blue flash. For when your build fails.",
                 EffectType.CYCLE, [Color.hex("#ff0000"), Color.hex("#0000ff")],
                 speed=5, category="Special", source="SignalRGB"),
]


def get_categories() -> list[str]:
    """Get all unique effect categories."""
    cats = []
    seen = set()
    for p in PRESETS:
        if p.category not in seen:
            cats.append(p.category)
            seen.add(p.category)
    return cats


def get_presets_by_category(category: str) -> list[EffectPreset]:
    """Get all presets in a category."""
    return [p for p in PRESETS if p.category == category]


def get_preset_by_name(name: str) -> EffectPreset | None:
    """Find a preset by name."""
    for p in PRESETS:
        if p.name == name:
            return p
    return None


def get_sources() -> list[str]:
    """Get all source ecosystems represented."""
    sources = []
    seen = set()
    for p in PRESETS:
        if p.source not in seen:
            sources.append(p.source)
            seen.add(p.source)
    return sources
