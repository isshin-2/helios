import re

with open("core/audio/voice_manager.py", "r", encoding="utf-8") as f:
    vm_content = f.read()

if "import emoji" not in vm_content:
    vm_content = vm_content.replace(
        "import asyncio\nimport logging",
        "import asyncio\nimport logging\ntry:\n    import emoji\nexcept ImportError:\n    emoji = None"
    )

old_init = """        self._text_buffer = ""
        self._tts_queue = asyncio.Queue()
        self._synthesis_task = None
        
        # Regex for sensible sentence boundaries
        self.sentence_pattern = re.compile(r'([.?!]+[\s\n]+|\n\n+)')"""

new_init = """        self._text_buffer = ""
        self._tts_queue = asyncio.Queue()
        self._synthesis_task = None
        
        # State tracking for scrubbing
        self._in_think_block = False
        self._in_code_block = False
        
        # Regex for sensible sentence boundaries
        self.sentence_pattern = re.compile(r'([.?!]+[\s\n]+|\n\n+)')"""

vm_content = vm_content.replace(old_init, new_init)

old_status = """    def _on_status(self, data):
        \"\"\"Reset state if we get a new input request status, just in case.\"\"\"
        if isinstance(data, str) and "Generating" in data:
            # Start fresh for a new response
            self._text_buffer = ""
            if not self._synthesis_task or self._synthesis_task.done():
                try:
                    self._synthesis_task = asyncio.create_task(self._synthesis_worker())
                except RuntimeError:
                    pass"""

new_status = """    def _on_status(self, data):
        \"\"\"Reset state if we get a new input request status, just in case.\"\"\"
        if isinstance(data, str) and "Generating" in data:
            # Start fresh for a new response
            self._text_buffer = ""
            self._in_think_block = False
            self._in_code_block = False
            if not self._synthesis_task or self._synthesis_task.done():
                try:
                    self._synthesis_task = asyncio.create_task(self._synthesis_worker())
                except RuntimeError:
                    pass"""
vm_content = vm_content.replace(old_status, new_status)

old_process = """    def _process_buffer(self, force: bool = False):
        \"\"\"Extracts complete sentences and sends them to the TTS queue.\"\"\"
        while True:
            match = self.sentence_pattern.search(self._text_buffer)
            if match:
                end_pos = match.end()
                sentence = self._text_buffer[:end_pos].strip()
                self._text_buffer = self._text_buffer[end_pos:]
                
                if sentence:
                    # Clean out markdown characters
                    clean_sentence = re.sub(r'[*_#`\[\]]', '', sentence)
                    if clean_sentence.strip():
                        # We use threadsafe methods because EventBus might run on different event loop
                        try:
                            asyncio.get_event_loop().call_soon_threadsafe(
                                self._tts_queue.put_nowait, clean_sentence
                            )
                        except RuntimeError:
                            # Not in an async context, queue directly
                            self._tts_queue.put_nowait(clean_sentence)
            else:
                break
                
        # If force is true, take the remainder
        if force and self._text_buffer.strip():
            clean_sentence = re.sub(r'[*_#`\[\]]', '', self._text_buffer).strip()
            if clean_sentence:
                try:
                    asyncio.get_event_loop().call_soon_threadsafe(
                        self._tts_queue.put_nowait, clean_sentence
                    )
                except RuntimeError:
                    self._tts_queue.put_nowait(clean_sentence)
            self._text_buffer = "" """

new_process = """    def _clean_and_queue(self, sentence: str):
        \"\"\"Handles stateful markdown parsing and queues clean text.\"\"\"
        # State transitions
        if "<think>" in sentence:
            self._in_think_block = True
            sentence = sentence.split("<think>")[0] # Keep anything before the tag
        
        if "</think>" in sentence:
            self._in_think_block = False
            sentence = sentence.split("</think>")[-1] # Keep anything after the tag
            
        # Count code block ticks
        tick_count = sentence.count("```")
        if tick_count % 2 == 1:
            self._in_code_block = not self._in_code_block
            
        # If we are in a block, don't speak!
        if self._in_think_block or self._in_code_block:
            return
            
        # Clean up the sentence
        clean_sentence = re.sub(r'```.*?```', ' [Code] ', sentence, flags=re.DOTALL)
        clean_sentence = re.sub(r'```', '', clean_sentence)
        clean_sentence = re.sub(r'<[^>]+>', '', clean_sentence) # Remove stray HTML tags
        clean_sentence = re.sub(r'[*_#~]', '', clean_sentence)
        clean_sentence = re.sub(r'http[s]?://\\S+', ' [Link] ', clean_sentence)
        if emoji:
            clean_sentence = emoji.replace_emoji(clean_sentence, replace='')
            
        clean_sentence = clean_sentence.strip()
        
        if clean_sentence:
            try:
                asyncio.get_event_loop().call_soon_threadsafe(
                    self._tts_queue.put_nowait, clean_sentence
                )
            except RuntimeError:
                self._tts_queue.put_nowait(clean_sentence)

    def _process_buffer(self, force: bool = False):
        \"\"\"Extracts complete sentences and sends them to the TTS queue.\"\"\"
        while True:
            match = self.sentence_pattern.search(self._text_buffer)
            if match:
                end_pos = match.end()
                sentence = self._text_buffer[:end_pos].strip()
                self._text_buffer = self._text_buffer[end_pos:]
                
                if sentence:
                    self._clean_and_queue(sentence)
            else:
                break
                
        # If force is true, take the remainder
        if force and self._text_buffer.strip():
            self._clean_and_queue(self._text_buffer.strip())
            self._text_buffer = "" """

vm_content = vm_content.replace(old_process, new_process)

with open("core/audio/voice_manager.py", "w", encoding="utf-8") as f:
    f.write(vm_content)
print("Patched VoiceManager scrubber!")
