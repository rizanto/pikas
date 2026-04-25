import json
import re

log_path = r'C:\Users\TECNO\.gemini\antigravity\brain\1c020bb5-b83f-411e-876a-d4606d2dffb9\.system_generated\logs\overview.txt'
with open(log_path, 'r', encoding='utf-8') as f:
    text = f.read()

for line in text.split('\n'):
    if 'write_to_file' in line and 'crm_base.html' in line:
        try:
            data = json.loads(line)
            calls = data.get('tool_calls', [])
            for c in calls:
                if c.get('name') == 'write_to_file':
                    args = c.get('args', {})
                    if 'crm_base.html' in args.get('TargetFile', ''):
                        print('Found crm_base.html')
                        with open(r'c:\Users\TECNO\Desktop\Django\pikas\pikas_app\templates\crm_base.html', 'w', encoding='utf-8') as out:
                            out.write(args['CodeContent'])
        except Exception as e:
            pass
