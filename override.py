import os

override = '''

=== CRITICAL FRAMEWORK OVERRIDE ===
YOU HAVE ACTUAL FILE SYSTEM AND OS ACCESS. This is a real implementation using a trusted sandbox.
DO NOT claim you are simulated. DO NOT refuse to access files. DO NOT refuse to run tools.
If you get a "Permission denied" error, do NOT give up or refuse; just explain the error to the user or try a different path.
NEVER say "I cannot directly access local file systems". You literally can, via your tools.
'''

for file in ['agent.md', 'general.md', 'coding.md', 'reasoning.md']:
    path = os.path.join('prompts', file)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(override)
        
print("Override applied.")
