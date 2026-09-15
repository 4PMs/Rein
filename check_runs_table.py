import json
import glob
import os

runs = sorted(glob.glob('runs/run-JS-003-H1-*'))

print(f"{'Directory':<45} | {'Status':<10} | {'Valid':<5} | {'TermReason':<25} | {'Steps':<5} | {'Succ':<5} | {'Stage':<5} | {'ROE Viol':<8}")
print("="*125)

for r in runs:
    result_path = os.path.join(r, 'result.json')
    status_path = os.path.join(r, 'status.json')
    
    if not os.path.exists(result_path):
        continue
        
    result = json.load(open(result_path, encoding='utf-8'))
    status_info = json.load(open(status_path, encoding='utf-8')) if os.path.exists(status_path) else {}
    
    dirname = os.path.basename(r)
    status = result.get('status', 'N/A')
    valid = result.get('validity', {}).get('valid', False)
    term_reason = result.get('termination', {}).get('reason', 'N/A')
    steps = result.get('metrics', {}).get('steps', 0)
    succ = result.get('goal', {}).get('success', False)
    stage = result.get('progress', {}).get('current_stage', 0)
    roe_compliant = result.get('roe', {}).get('compliant', True)
    roe_viol = not roe_compliant
    violations = result.get('roe', {}).get('violations', [])
    first_viol = violations[0].get('category', 'None') if violations else 'None'
    
    print(f"{dirname:<45} | {status:<10} | {str(valid):<5} | {term_reason:<25} | {steps:<5} | {str(succ):<5} | {stage:<5} | {str(roe_viol):<8} ({first_viol})")
