"""
HELIOS Engineering Pronunciation Resolver
Provides configurable pronunciation resolution for engineering, hardware, and AI terms.
Substitutions only exist in the TTS representation and never mutate display text.
"""
import os
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)

# Built-in technical pronunciation dictionary for hardware, AI, and systems engineering
DEFAULT_TECHNICAL_DICTIONARY: Dict[str, str] = {
    # Microcontrollers & SoCs (case-insensitive)
    "ESP32-S3": "E S P thirty two S three",
    "ESP32-C3": "E S P thirty two C three",
    "ESP32": "E S P thirty two",
    "RP2040": "R P two zero four zero",
    "RP2350": "R P two three five zero",
    "STM32": "S T M thirty two",
    "NRF52": "N R F fifty two",
    "ATmega328P": "A T mega three twenty eight P",
    "AVR": "A V R",

    # Embedded Buses & Protocols (case-insensitive)
    "GPIO": "G P I O",
    "I2C": "I two C",
    "I²C": "I two C",
    "SPI": "S P I",
    "UART": "you art",
    "USART": "you sart",
    "PWM": "P W M",
    "PCB": "P C B",
    "PCBs": "P C B s",
    "MOSFET": "moss fet",
    "MOSFETs": "moss fets",
    "VRM": "V R M",
    "JTAG": "jay tag",
    "SWD": "S W D",
    "DMA": "D M A",
    "OTA": "O T A",
    "SMD": "S M D",
    "SMT": "S M T",
    "KiCad": "key cad",

    # Web & Software Tech (case-insensitive)
    "API": "A P I",
    "APIs": "A P I s",
    "HTTP": "H T T P",
    "HTTPS": "H T T P S",
    "WebSocket": "web socket",
    "WebSockets": "web sockets",
    "FastAPI": "fast A P I",
    "SQL": "sequel",
    "SQLite": "sequel lite",
    "PostgreSQL": "post gres",
    "Postgres": "post gres",
    "JSON": "jason",
    "YAML": "yam el",
    "CLI": "C L I",
    "GUI": "gooey",
    "LLM": "L L M",
    "LLMs": "L L M s",
    "TTS": "T T S",
    "STT": "S T T",
    "VAD": "V A D",
    "ONNX": "on ix",
    "CPU": "C P U",
    "GPU": "G P U",
    "SDK": "S D K",
    "IDE": "I D E",
    "CI/CD": "C I C D",
    "IoT": "I o T",
    "asyncio": "a sync I O",
    "PyTorch": "pie torch",
    "NumPy": "num pie",
    "SciPy": "sigh pie",
    "Nginx": "engine X",
    "Redis": "red iss",
    "GitHub": "git hub",
    "GitLab": "git lab",
    "Linux": "linn ucks",
    "Ubuntu": "oo boon too",
}

# Terms that MUST match case-sensitively to avoid colliding with common English words
# e.g., "CAN" (bus) vs "can" (verb), "RAM" vs "ram" (animal), "PR" (pull request), "PID" (loop)
DEFAULT_CASE_SENSITIVE_DICTIONARY: Dict[str, str] = {
    "CAN": "can",        # CAN bus spoken as word 'can' or spelled
    "PID": "P I D",
    "RAM": "ram",
    "VRAM": "V ram",
    "DAC": "D A C",
    "ADC": "A D C",
    "IC": "I C",
    "ICs": "I C s",
    "PR": "P R",
    "PRs": "P R s",
    "AI": "A I",
    "IP": "I P",
    "OS": "O S",
    "IO": "I O",
}


class EngineeringPronunciationResolver:
    """
    Resolves technical terms to phonetic/expanded spoken representations.
    
    Resolution Priority:
    1. Explicit runtime user dictionary (passed via set_user_dictionary or kwargs)
    2. User configuration file (e.g. config/pronunciation.yaml)
    3. HELIOS built-in technical dictionary
    4. Normal text
    5. Optional phoneme/IPA input for Kokoro TTS
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._default_config_path()
        self.user_dictionary: Dict[str, str] = {}
        self.file_dictionary: Dict[str, str] = {}
        self.case_sensitive_terms: Dict[str, str] = dict(DEFAULT_CASE_SENSITIVE_DICTIONARY)
        self.case_insensitive_terms: Dict[str, str] = dict(DEFAULT_TECHNICAL_DICTIONARY)
        self._compiled_regexes: List[Tuple[re.Pattern, str]] = []

        self.reload()

    def _default_config_path(self) -> Path:
        # Check ai-router/config/pronunciation.yaml or current working directory
        base = Path(__file__).resolve().parent.parent.parent.parent
        return base / "config" / "pronunciation.yaml"

    def reload(self):
        """Reload user configuration dictionary from file and rebuild patterns."""
        self.file_dictionary.clear()
        if self.config_path and Path(self.config_path).exists() and yaml is not None:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        # Support top-level dictionary or 'pronunciations' section
                        items = data.get("pronunciations", data)
                        if isinstance(items, dict):
                            self.file_dictionary = {str(k): str(v) for k, v in items.items()}
                            logger.info(f"Loaded {len(self.file_dictionary)} custom pronunciations from {self.config_path}")
            except Exception as e:
                logger.warning(f"Could not load pronunciation config from {self.config_path}: {e}")

        self._rebuild_patterns()

    def set_user_dictionary(self, dictionary: Dict[str, str]):
        """Set explicit runtime user dictionary with highest priority."""
        self.user_dictionary = dict(dictionary)
        self._rebuild_patterns()

    def add_pronunciation(self, term: str, spoken: str, case_sensitive: bool = False):
        """Dynamically add or override a pronunciation."""
        self.user_dictionary[term] = spoken
        if case_sensitive:
            self.case_sensitive_terms[term] = spoken
        else:
            self.case_insensitive_terms[term] = spoken
        self._rebuild_patterns()

    def _rebuild_patterns(self):
        """
        Build compiled regex patterns ordered by term length descending,
        ensuring longer compounds (e.g. ESP32-S3) are matched before subcomponents (ESP32).
        """
        combined_ci: Dict[str, str] = dict(self.case_insensitive_terms)
        combined_cs: Dict[str, str] = dict(self.case_sensitive_terms)

        # Merge file dictionary
        for k, v in self.file_dictionary.items():
            if k.isupper() and len(k) <= 4:
                combined_cs[k] = v
            else:
                combined_ci[k] = v

        # Merge user dictionary (highest priority)
        for k, v in self.user_dictionary.items():
            if k.isupper() and len(k) <= 4:
                combined_cs[k] = v
            else:
                combined_ci[k] = v

        patterns = []

        # Sort case-sensitive terms by length descending
        sorted_cs = sorted(combined_cs.keys(), key=len, reverse=True)
        for term in sorted_cs:
            replacement = combined_cs[term]
            pattern = re.compile(rf"(?<![a-zA-Z0-9_-])({re.escape(term)})(?![a-zA-Z0-9_-])")
            patterns.append((pattern, replacement))

        # Sort case-insensitive terms by length descending
        sorted_ci = sorted(combined_ci.keys(), key=len, reverse=True)
        for term in sorted_ci:
            replacement = combined_ci[term]
            pattern = re.compile(rf"(?<![a-zA-Z0-9_-])({re.escape(term)})(?![a-zA-Z0-9_-])", re.IGNORECASE)
            patterns.append((pattern, replacement))

        self._compiled_regexes = patterns

    def resolve(self, text: str, extra_user_dict: Optional[Dict[str, str]] = None) -> str:
        """
        Apply pronunciation replacements to the TTS representation.
        Returns the resolved text. Display text is unchanged.
        """
        if not text:
            return ""

        # If extra runtime dict provided for this sentence, apply first
        if extra_user_dict:
            for term, replacement in sorted(extra_user_dict.items(), key=lambda x: len(x[0]), reverse=True):
                pat = re.compile(rf"(?<![a-zA-Z0-9_-])({re.escape(term)})(?![a-zA-Z0-9_-])", re.IGNORECASE)
                text = pat.sub(replacement, text)

        for pattern, replacement in self._compiled_regexes:
            text = pattern.sub(replacement, text)

        return text
