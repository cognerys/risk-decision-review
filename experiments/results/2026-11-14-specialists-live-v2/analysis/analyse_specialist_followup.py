"""Recount EXP-008 decisions, computed utility, granular handoffs and revisions."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def analyse(run, output=None):
    data=json.loads((run/'results.json').read_text())
    manifest=json.loads((run/'manifest.json').read_text())
    # Re-evaluate with the source snapshot used for this run, not a later checkout.
    import sys
    sys.path.insert(0,str(run/'source/src'))
    spec=importlib.util.spec_from_file_location('frozen_runner',run/'source/experiments/run_specialist_followup.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    bundles=json.loads((run/'evidence-bundles.json').read_text())
    packages=json.loads((run/'evaluation-packages.json').read_text())
    from risk_desk.graphs.specialists_v2 import evaluation_bundle_for
    mismatches=[]
    for name,expected in manifest['source']['source_sha256'].items():
        if hashlib.sha256((run/'source'/name).read_bytes()).hexdigest()!=expected:mismatches.append(name)
    assert not mismatches, f'Frozen source changed: {mismatches}'
    for row in data['rows']:
        if row['status']=='complete':
            pack=packages[row['card_id']]
            visible={**bundles[row['card_id']],'workflow_evidence':row.get('workflow_evidence',{})}
            bundle=evaluation_bundle_for(visible,pack['evaluation_bundle'])
            assert module.metrics(row['proposal'],bundle,pack['reference'],pack['reference_basis'])==row['proposal_metrics']
            assert module.metrics(row['initial_proposal'],bundle,pack['reference'],pack['reference_basis'])==row['initial_metrics']
    rebuilt=module.summarise(data['rows'])
    assert rebuilt==data['summary']
    responses=[json.loads(line) for line in (run/'responses.jsonl').read_text().splitlines()]
    usage={}
    for arm in module.ARMS:
        selected=[r for r in responses if r['arm']==arm]
        complete=[r for r in selected if r['status']=='complete']
        counts={}
        for key in ['input_units','output_units','total_units']:
            values=[r.get('usage',{}).get(key) for r in complete]
            counts[key]=sum(v for v in values if isinstance(v,(int,float))) if values and all(isinstance(v,(int,float)) for v in values) else None
        for output_key,details,key in [('reasoning_units','output_details','reasoning'),('cached_input_units','input_details','cache_read')]:
            values=[(r.get('usage',{}).get(details) or {}).get(key) for r in complete]
            counts[output_key]=sum(values) if values and all(isinstance(v,(int,float)) for v in values) else None
        counts['completed_calls']=len(complete)
        counts['failed_calls']=len(selected)-len(complete)
        counts['finish_reasons']=dict(Counter(r.get('metadata',{}).get('finish_reason','unknown') for r in complete))
        usage[arm]=counts
    paired={}
    for a,b in [('single','specialists'),('specialists','challenged'),('self_review','challenged')]:
        items=[p for p in rebuilt['paired'] if p['left']==a and p['right']==b]
        pair={}
        for field in ['contract_delta','grounded_reference_delta','grounded_policy_delta']:
            pair[field]={'wins':sum(p[field]==1 for p in items),'losses':sum(p[field]==-1 for p in items),
                         'ties':sum(p[field]==0 for p in items),'incomplete':sum(p[field] is None for p in items)}
        paired[f'{b}-minus-{a}']=pair
    revisions=[]
    for row in data['rows']:
        if row['status']=='complete' and row['arm']=='challenged':
            revisions.append({'card_id':row['card_id'],'initial_action':row['initial_metrics']['action'],
              'revised_action':row['proposal_metrics']['action'],
              'contract_delta':int(row['proposal_metrics']['primary_contract_pass'])-int(row['initial_metrics']['primary_contract_pass']),
              'grounded_policy_delta':int(row['proposal_metrics']['grounded_policy_match'])-int(row['initial_metrics']['grounded_policy_match']),
              'grounded_reference_delta':int(row['proposal_metrics']['grounded_reference_match'])-int(row['initial_metrics']['grounded_reference_match']),
              'challenge_usable':row['challenge'].get('usable'),
              'challenge':row['challenge'].get('report'),
              'initial_errors':row['initial_metrics'].get('numeric_errors'),
              'revised_errors':row['proposal_metrics'].get('numeric_errors')})
    result={'run_id':data['run_id'],'mode':data['mode'],'recount_matches':True,
            'analysis_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'source_artifact_sha256':{name:hashlib.sha256((run/name).read_bytes()).hexdigest() for name in ['manifest.json','results.json','requests.jsonl','responses.jsonl','rows.jsonl','evidence-bundles.json','evaluation-packages.json','reference-targets.json']},
            'summary':rebuilt,'usage':usage,'paired_counts':paired,'revisions':revisions}
    reports=[r for row in data['rows'] for r in row.get('specialist_reports',[])]
    by_arm={};by_role={}
    for field,values,destination in [('arm',['specialists','challenged'],by_arm),('role',['market_physical','credit_governance'],by_role)]:
        for value in values:
            selected=[report for row in data['rows'] for report in row.get('specialist_reports',[])
                      if (row['arm'] if field=='arm' else report['role'])==value]
            destination[value]={'planned':8,'recorded':len(selected),'usable':sum(bool(r['usable']) for r in selected),
                                'fully_valid':sum(bool(r['fully_valid']) for r in selected)}
    findings=[f for r in reports for f in r['validation']['findings']]
    process={'planned_reports':16,'recorded_reports':len(reports),'usable_reports':sum(bool(r['usable']) for r in reports),
       'fully_valid_reports':sum(bool(r['fully_valid']) for r in reports),
       'statuses':dict(Counter(r['status'] for r in reports)),
       'by_arm':by_arm,'by_role':by_role,'recorded_findings':len(findings),
       'accepted_findings':sum(bool(f['accepted']) for f in findings),
       'unreliable_finding_count_reports':sum(any(e['code'] in {'report_not_object','required_list'} for e in r['validation']['envelope_errors']) for r in reports),
       'rejection_codes':dict(Counter(e['code'] for f in findings for e in f['rejection_reasons'])),
       'reports_per_job':dict(Counter(sum(bool(r['usable']) for r in row.get('specialist_reports',[])) for row in data['rows'] if row['arm'] in {'specialists','challenged'})),
       'stage_parse_status':{role:dict(Counter(s['parse_status'] for row in data['rows'] for s in row.get('stages',[]) if s['role']==role))
                             for role in sorted({s['role'] for row in data['rows'] for s in row.get('stages',[])})},
       'challenges_requesting_revision':sum(bool((row.get('challenge') or {}).get('requires_revision')) for row in data['rows'])}
    result['handoff']=process
    regret=[]
    for row in data['rows']:
        if row['status']!='complete':continue
        m=row['proposal_metrics'];pack=packages[row['card_id']];e=pack['evaluation_bundle']['evidence']
        feasible={a['action'] for a in pack['evaluation_bundle']['actions'] if a['feasible']}
        action,reference=m['action'],m['reference_action'];gap=None
        if isinstance(action,str) and action in feasible and reference in feasible:
            gap=e[f"{row['card_id']}:action:{reference}:utility"]-e[f"{row['card_id']}:action:{action}:utility"]
        regret.append({'job_id':row['job_id'],'regret_eur':gap})
    result['conditional_synthetic_regret']=regret
    target=Path(output) if output is not None else run/'analysis'
    if target.exists():raise FileExistsError('Existing analysis is retained; choose a new analysis revision')
    target.mkdir(parents=True)
    (target/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    (target/'analyse_specialist_followup.py').write_text(Path(__file__).read_text())
    lines=['# Specialist-role pilot: results and recount','',f"Run `{data['run_id']}`. {data['mode']}; {data['completed_jobs']}/{data['planned_jobs']} jobs completed; {data['calls']} calls. No planned metric was changed after observing results.",'',
      'The source snapshot and all recorded initial/final proposal metrics reproduce. Counts below use all four planned jobs per arm. Grounding is the specified structural/numeric contract; reference agreement is authored scorecard consistency.','',
      '| Arm | Grounded proposals / 4 | Grounded policy matches / 4 | Raw reference matches / 4 | Fallbacks | Calls | Input / output units | Job time (s) |',
      '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for arm,s in rebuilt['arms'].items():
        u=usage[arm]
        lines.append(f"| {arm} | {s['primary_contract_pass']} | {s['grounded_policy_match']} | {s['reference_match']} | {s['fallbacks']} | {s['calls']} | {u['input_units']} / {u['output_units']} | {s['latency_seconds']:.1f} |")
    lines+=['','Usage units are provider-reported tokens, including any reasoning output accounted for by the provider. Time is summed observed job latency, not a controlled speed benchmark. No monetary cost is inferred. Missing usage remains null in the analysis JSON.','',
      '## Case-level proposed actions','', '| Card | Reference | Single | Specialists | Challenged | Self-review |','| --- | --- | --- | --- | --- | --- |']
    by={(r['card_id'],r['arm']):r for r in data['rows']}
    for card in module.CARDS:
        cells=[];reference='unknown'
        for arm in module.ARMS:
            row=by.get((card,arm))
            if not row or row['status']!='complete':cells.append('error/not attempted');continue
            m=row['proposal_metrics'];reference=m['reference_action']
            cells.append(f"{m['action']} / {m['decision_basis']} ({'contract pass' if m['primary_contract_pass'] else 'contract fail'})")
        lines.append('| '+' | '.join([card,reference,*cells])+' |')
    lines+=['','## Paired results','', '| Comparison | Contract wins / losses / ties | Grounded-policy wins / losses / ties | Incomplete pairs |','| --- | --- | --- | --- |']
    for name,p in paired.items():
        a=p['contract_delta'];b=p['grounded_policy_delta']
        lines.append(f"| {name} | {a['wins']} / {a['losses']} / {a['ties']} | {b['wins']} / {b['losses']} / {b['ties']} | {a['incomplete']} |")
    lines+=['','## Within-job challenger revisions','']
    for r in revisions:
        lines.append(f"- `{r['card_id']}`: {r['initial_action']} → {r['revised_action']}; contract change {r['contract_delta']:+d}; grounded-reference change {r['grounded_reference_delta']:+d}. Usable critique: {r['challenge_usable']}.")
    lines+=['','## Handoff outcomes','',f"Usable reports: {process['usable_reports']}/16 planned; fully valid: {process['fully_valid_reports']}/16. Accepted findings: {process['accepted_findings']}/{process['recorded_findings']} parsed emitted findings. Reports with unreliable finding counts: {process['unreliable_finding_count_reports']}.",'', '## Interpretation boundaries','',
      'One stochastic pass on four composed cases from two contrast pairs does not establish general benefit, statistical significance, explanation faithfulness or real-desk usefulness. The two five-call workflows differ in context, tokens and intermediate paths. The pilot compares configurations with full precomputed evidence; it is not a test of autonomous tool discovery or human approval. Structured numeric checks cover the emitted claim fields, not every factual statement in prose. Full traces retain the detail needed for separately labelled qualitative review.','',
      'EXP-007 and this follow-up change cases, evidence presentation, schema and handoff policy. Their scores do not isolate a causal repair effect; use matched arms within EXP-008.']
    (target/'analysis.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'analysis':str(target),'summary':rebuilt['arms'],'usage':usage,'paired_counts':paired,'handoff':process},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path)
    parser.add_argument('--output-dir',type=Path,help='Fresh analysis destination for a retained run')
    args=parser.parse_args()
    analyse(args.run.resolve(),args.output_dir)
