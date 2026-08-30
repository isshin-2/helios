with open("core/audio/stt/google.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
in_else = False
for i, line in enumerate(lines):
    if line.startswith("                else:"):
        new_lines.append(line)
        in_else = True
    elif line.startswith("                    if is_recording:"):
        new_lines.append(line)
    elif line.startswith("                        audio_buffer.append(raw_data)"):
        new_lines.append(line)
        if in_else:
            # We are in the else block of is_speech
            new_lines.append("                        silence_counter += 1\n")
            new_lines.append("                        \n")
            new_lines.append("                        if silence_counter > max_silence_chunks:\n")
            new_lines.append("                            # Speech ended\n")
            new_lines.append("                            is_recording = False\n")
            new_lines.append("                            \n")
            new_lines.append("                            # We have enough audio? (At least 1 second total)\n")
            new_lines.append("                            if len(audio_buffer) > int((sample_rate / chunk_size) * 0.5):\n")
            new_lines.append("                                self._current_barge_in = was_barge_in\n")
            new_lines.append("                                self._process_audio(b\"\".join(audio_buffer), sample_rate)\n")
            new_lines.append("                                was_barge_in = False\n")
            new_lines.append("                                \n")
            new_lines.append("                            audio_buffer = []\n")
            new_lines.append("                            silence_counter = 0\n")
            in_else = False
    elif "silence_counter += 1" in line and not line.startswith("                        silence_counter = 0"):
        pass # Skip the misplaced one
    elif "if silence_counter > max_silence_chunks:" in line:
        pass
    elif "# Speech ended" in line:
        pass
    elif "is_recording = False" in line and "is_recording =" in line:
        # We need to be careful not to delete the init `is_recording = False`
        if i > 100:
            pass
        else:
            new_lines.append(line)
    elif "# We have enough audio" in line:
        pass
    elif "if len(audio_buffer) > int(" in line:
        pass
    elif "self._current_barge_in = was_barge_in" in line:
        pass
    elif "self._process_audio" in line and "join" in line:
        pass
    elif "was_barge_in = False" in line and i > 132:
        pass
    elif "audio_buffer = []" in line and i > 100:
        pass
    elif "silence_counter = 0" in line and i > 132:
        pass
    else:
        new_lines.append(line)

with open("core/audio/stt/google.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
