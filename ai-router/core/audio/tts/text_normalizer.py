"""
HELIOS TTS Text Normalizer
Normalizes text for speech synthesis without mutating display text.
Extracts and expands markdown, math, units, abbreviations, and HELIOS tags.
"""
import re
from typing import Optional, Tuple

try:
    import emoji
except ImportError:
    emoji = None


class StreamingFilterState:
    """Maintains state across streaming LLM tokens/sentences."""
    def __init__(self):
        self.in_think_block: bool = False
        self.in_code_block: bool = False

    def reset(self):
        self.in_think_block = False
        self.in_code_block = False


class TextNormalizer:
    """
    Dedicated TTS-only text normalizer.
    Converts rich LLM output (markdown, equations, engineering units, tags)
    into clean, natural, phonetically pronounceable text.
    """

    def __init__(self):
        # Patterns for structural / system muting
        self.re_think = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
        self.re_code_fenced = re.compile(r"```.*?```", re.DOTALL)
        self.re_json_object = re.compile(r"\{\s*\"[^\"]+\"\s*:.*?\}", re.DOTALL)

        # HELIOS tags & metadata
        self.re_body_tags = re.compile(
            r"`*\[BODY\s*:[^\]\n]*(?:\]|>>+|>+\s*,|$)`*[,;\s]*", re.IGNORECASE
        )
        self.re_pose_tags = re.compile(r"\[POSE_JSON\s*:.*?\]", re.DOTALL | re.IGNORECASE)
        self.re_tool_executed = re.compile(r"\[Tool Executed:.*?\]", re.IGNORECASE)
        self.re_system_error = re.compile(r"\[System Error.*?\]", re.IGNORECASE)
        self.re_system_warning = re.compile(r"\[System Warning.*?\]", re.IGNORECASE)
        self.re_system_note = re.compile(r"\[System Note:.*?\]", re.IGNORECASE)
        self.re_bracket_coords = re.compile(r"\[\s*\d+\s*(?:,\s*[\d.]+\s*){3,}\]")
        self.re_input_req = re.compile(r"INPUT_REQUIRED::", re.IGNORECASE)
        self.re_approval_req = re.compile(r"APPROVAL_REQUIRED::.*", re.IGNORECASE)
        self.re_stream_interrupt = re.compile(r"\[STREAM-INTERRUPT\].*", re.IGNORECASE)
        self.re_vision_enforcement = re.compile(r"\[VISION ENFORCEMENT\].*", re.IGNORECASE)
        self.re_telemetry = re.compile(r"\[TELEMETRY\](?:\s*\{.*?\}|\s*:[^\n]*|\s*)", re.IGNORECASE)
        self.re_blank_audio = re.compile(r"\[BLANK_AUDIO\]", re.IGNORECASE)
        self.re_code_tag = re.compile(r"\[Code\]", re.IGNORECASE)
        self.re_link_tag = re.compile(r"\[Link\]", re.IGNORECASE)

        # Buttons and HTML
        self.re_button = re.compile(r"<button>(.*?)</button>", re.IGNORECASE)
        self.re_html_tags = re.compile(r"<[^>]+>")
        self.re_urls = re.compile(r"http[s]?://\S+")

        # Markdown syntax
        self.re_md_links = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
        self.re_md_images = re.compile(r"!\[[^\]]*\]\([^\)]+\)")
        self.re_md_headers = re.compile(r"^\s*#{1,6}\s+", re.MULTILINE)
        self.re_md_blockquotes = re.compile(r"^\s*>\s*", re.MULTILINE)
        self.re_md_bullets = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
        self.re_md_numbered = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)

        # Emoji fallback regex (matches common emojis if emoji package is missing)
        self.re_emojis = re.compile(
            "[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\uFE00-\uFE0F\U0001F900-\U0001F9FF]",
            flags=re.UNICODE,
        )

        # Math patterns
        self.re_math_power = re.compile(r"(\b\d+(?:\.\d+)?)\s*\^\s*(\d+(?:\.\d+)?\b)")
        self.re_math_plus = re.compile(r"(\b\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?\b)")
        self.re_math_minus = re.compile(r"(\b\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?\b)")
        self.re_math_times = re.compile(r"(\b\d+(?:\.\d+)?)\s*[\*×]\s*(\d+(?:\.\d+)?\b)")
        self.re_math_div = re.compile(r"(\b\d+(?:\.\d+)?)\s*[/÷]\s*(\d+(?:\.\d+)?\b)")
        self.re_math_pct = re.compile(r"(\b\d+(?:\.\d+)?)\s*%")
        self.re_math_temp_c = re.compile(r"(\b-?\d+(?:\.\d+)?)\s*°[Cc]\b")
        self.re_math_temp_f = re.compile(r"(\b-?\d+(?:\.\d+)?)\s*°[Ff]\b")
        self.re_math_degrees = re.compile(r"(\b\d+(?:\.\d+)?)\s*°")

        # Abbreviations
        self.abbreviations = [
            (re.compile(r"\be\.g\.,?\b", re.IGNORECASE), "for example"),
            (re.compile(r"\bi\.e\.,?\b", re.IGNORECASE), "that is"),
            (re.compile(r"\betc\.\b", re.IGNORECASE), "etcetera"),
            (re.compile(r"\bvs\.?\b", re.IGNORECASE), "versus"),
            (re.compile(r"\bapprox\.?\b", re.IGNORECASE), "approximately"),
            (re.compile(r"\bw/o\b", re.IGNORECASE), "without"),
            (re.compile(r"\bw/\b", re.IGNORECASE), "with"),
        ]

        # Units of measurement
        self.units = [
            # Voltage
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*mV\b"), r"\1 millivolts"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*V\b"), r"\1 volts"),
            # Current
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*uA\b", re.IGNORECASE), r"\1 microamps"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*µA\b"), r"\1 microamps"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*mA\b"), r"\1 milliamps"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*A\b"), r"\1 amps"),
            # Resistance
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*k[Ω\b]|kohm\b", re.IGNORECASE), r"\1 kilo ohms"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*M[Ω\b]|Mohm\b"), r"\1 mega ohms"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*(?:[Ω]|ohm|ohms)\b", re.IGNORECASE), r"\1 ohms"),
            # Capacitance
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*uF\b", re.IGNORECASE), r"\1 microfarads"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*µF\b"), r"\1 microfarads"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*nF\b"), r"\1 nanofarads"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*pF\b"), r"\1 picofarads"),
            # Frequency
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*GHz\b", re.IGNORECASE), r"\1 gigahertz"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*MHz\b", re.IGNORECASE), r"\1 megahertz"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*kHz\b", re.IGNORECASE), r"\1 kilohertz"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*Hz\b", re.IGNORECASE), r"\1 hertz"),
            # Rate / Performance
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*fps\b", re.IGNORECASE), r"\1 frames per second"),
            (re.compile(r"(\b\d+)\s*baud\b", re.IGNORECASE), r"\1 baud"),
            # Time
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*ms\b"), r"\1 milliseconds"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*(?:us|µs)\b"), r"\1 microseconds"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*ns\b"), r"\1 nanoseconds"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*s\b"), r"\1 seconds"),
            # Data / Memory
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*TB\b"), r"\1 terabytes"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*GB\b"), r"\1 gigabytes"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*MB\b"), r"\1 megabytes"),
            (re.compile(r"(\b\d+(?:\.\d+)?)\s*KB\b"), r"\1 kilobytes"),
        ]

    def filter_streaming_chunk(
        self, chunk: str, state: StreamingFilterState
    ) -> Tuple[Optional[str], StreamingFilterState]:
        """
        Process a chunk arriving from the streaming LLM, updating stateful
        blocks (such as <think> or ``` code blocks).
        Returns (clean_text, state) or (None, state) if completely muted.
        """
        if not chunk:
            return None, state

        text = chunk

        # Track <think> blocks
        if "<think>" in text:
            state.in_think_block = True
            text = text.split("<think>")[0]

        if "</think>" in text:
            state.in_think_block = False
            text = text.split("</think>")[-1]

        # Track ``` code blocks
        tick_count = text.count("```")
        if tick_count % 2 == 1:
            state.in_code_block = not state.in_code_block

        if state.in_think_block or state.in_code_block:
            return None, state

        normalized = self.normalize(text)
        if not normalized:
            return None, state

        return normalized, state

    def should_mute(self, text: str) -> bool:
        """Determines if the sentence/text should be completely muted for TTS."""
        if not text:
            return True
        # Completely fenced code block
        stripped = text.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            return True
        # Pure non-alphanumeric (dashes, ellipsis, punctuation only)
        if not re.search(r"[a-zA-Z0-9]", text):
            return True
        # Check for leaked raw tool call structures (excluding valid POSE_JSON character tags)
        clean = self.re_pose_tags.sub("", text)
        clean = self.re_body_tags.sub("", clean)
        if '"name":' in clean or '"arguments":' in clean or '"question":' in clean or '"success":' in clean or '"action":' in clean:
            return True
        if self.re_tool_executed.search(clean) or self.re_system_note.search(clean) or self.re_bracket_coords.search(clean):
            # Check if after removing these system tags anything alphanumeric remains
            remaining = self.re_bracket_coords.sub("", self.re_system_note.sub("", self.re_tool_executed.sub("", clean)))
            if not re.search(r"[a-zA-Z0-9]", remaining):
                return True
        return False

    def normalize(self, text: str) -> str:
        """
        Convert display text to normalized TTS-only representation.
        Does not mutate the caller's text string.
        """
        if not text:
            return ""

        s = text

        # 1. Strip think blocks if present in complete string
        s = self.re_think.sub("", s)

        # 2. Replace fenced code blocks
        s = self.re_code_fenced.sub("", s)
        s = s.replace("```", "")

        # 3. HELIOS VRM Body and Pose tags (must precede tool call check)
        s = self.re_body_tags.sub("", s)
        s = self.re_pose_tags.sub("", s)

        # 4. System metadata and tool execution tags
        s = self.re_tool_executed.sub("", s)
        s = self.re_system_error.sub("", s)
        s = self.re_system_warning.sub("", s)
        s = self.re_system_note.sub("", s)
        s = self.re_bracket_coords.sub("", s)
        s = self.re_input_req.sub("", s)
        s = self.re_approval_req.sub("", s)
        s = self.re_stream_interrupt.sub("", s)
        s = self.re_vision_enforcement.sub("", s)
        s = self.re_telemetry.sub("", s)
        s = self.re_blank_audio.sub("", s)

        # 5. Markdown links before stripping placeholder tags
        s = self.re_md_images.sub("", s)
        s = self.re_md_links.sub(r"\1", s)

        # 6. Placeholder tags
        s = self.re_code_tag.sub("", s)
        s = self.re_link_tag.sub("", s)

        # 7. Check for leaked raw tool call structures
        if '"name":' in s or '"arguments":' in s or '"question":' in s:
            return ""
        s = self.re_json_object.sub("", s)

        # 8. UI buttons to natural speech
        s = self.re_button.sub(r"Option: \1.", s)

        # 9. Strip bare URLs and HTML tags
        s = self.re_urls.sub("", s)
        s = self.re_html_tags.sub("", s)

        # 10. Markdown headers, blockquotes, bullets, numbering
        s = self.re_md_headers.sub("", s)
        s = self.re_md_blockquotes.sub("", s)
        s = self.re_md_bullets.sub("", s)
        s = self.re_md_numbered.sub("", s)

        # 11. Markdown inline formatting symbols (*, ~, #, `)
        # Preserve snake_case identifiers (e.g. gpio_set_level) by only stripping standalone/boundary underscores
        s = s.replace("`", "")
        s = s.replace("~", "")
        s = s.replace("*", "")
        s = s.replace("#", "")
        s = re.sub(r"(?<!\w)_|_(?!\w)", "", s)

        # Emojis removal
        if emoji is not None:
            s = emoji.replace_emoji(s, replace="")
        else:
            s = self.re_emojis.sub("", s)

        # Math expansions
        s = s.replace("±", " plus or minus ")
        s = s.replace("≈", " approximately equals ")
        s = s.replace("~=", " approximately equals ")
        s = s.replace("!=", " is not equal to ")
        s = s.replace("≠", " is not equal to ")
        s = s.replace("<=", " less than or equal to ")
        s = s.replace("≤", " less than or equal to ")
        s = s.replace(">=", " greater than or equal to ")
        s = s.replace("≥", " greater than or equal to ")

        s = self.re_math_temp_c.sub(r"\1 degrees Celsius", s)
        s = self.re_math_temp_f.sub(r"\1 degrees Fahrenheit", s)
        s = self.re_math_degrees.sub(r"\1 degrees ", s)
        s = self.re_math_pct.sub(r"\1 percent", s)
        s = self.re_math_power.sub(r"\1 to the power of \2", s)
        s = self.re_math_plus.sub(r"\1 plus \2", s)
        s = self.re_math_minus.sub(r"\1 minus \2", s)
        s = self.re_math_times.sub(r"\1 times \2", s)
        s = self.re_math_div.sub(r"\1 divided by \2", s)

        # Units expansion
        for pattern, replacement in self.units:
            s = pattern.sub(replacement, s)

        # Abbreviations expansion
        for pattern, replacement in self.abbreviations:
            s = pattern.sub(replacement, s)

        # Clean multiple spaces and whitespace
        s = re.sub(r"[ \t]+", " ", s)
        s = re.sub(r"\n\s*\n+", "\n", s).strip()

        # If after normalization no alphanumeric remains, mute it
        if not re.search(r"[a-zA-Z0-9]", s):
            return ""

        return s
