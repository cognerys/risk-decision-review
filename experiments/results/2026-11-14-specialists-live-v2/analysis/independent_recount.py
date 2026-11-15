"""Read completed EXP-008 JSON directly; never import the study evaluators."""
from pathlib import Path
import json,math,hashlib,collections

RUN=Path(__file__).resolve().parents[1]

def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)

def proposal_check(p,package,workflow):
    visible=package['visible_bundle']; evaluation=package['evaluation_bundle']
    known={**evaluation['evidence'],**workflow}; action=p.get('action_or_abstain')
    fields={'action_or_abstain','decision_basis','reason','procedural','economic','evidential','evidence_ids','numeric_claims'}
    strings=fields-{'evidence_ids','numeric_claims'}; ids=p.get('evidence_ids'); claims=p.get('numeric_claims')
    shape=set(p)==fields and all(isinstance(p[k],str) for k in strings)
    shape=shape and p.get('decision_basis') in {'missing_credit','unreducible_breach','near_tie','highest_utility'}
    shape=shape and isinstance(ids,list) and all(isinstance(x,str) for x in ids)
    shape=shape and isinstance(claims,list) and all(isinstance(c,dict) and set(c)=={'evidence_id','value'} and isinstance(c['evidence_id'],str) and finite(c['value']) for c in claims)
    feasible={a['action'] for a in visible['actions'] if a['feasible']}
    legal=isinstance(action,str) and action in feasible|{'abstain'}
    citation_valid=isinstance(ids,list) and bool(ids) and all(isinstance(x,str) and x in known for x in ids)
    claims=claims if isinstance(claims,list) else []; claim_ids=set(); numeric_ok=bool(claims); component_ok=True; component_errors=[]
    for c in claims:
        if not isinstance(c,dict):numeric_ok=False;continue
        key=c.get('evidence_id'); value=c.get('value')
        if not isinstance(key,str):numeric_ok=False;continue
        claim_ids.add(key); expected=known.get(key)
        numeric_ok=numeric_ok and finite(value) and finite(expected) and math.isclose(value,expected,abs_tol=.01,rel_tol=1e-6)
        numeric_ok=numeric_ok and isinstance(ids,list) and key in ids
        definition=visible.get('derived_quantities',{}).get(key)
        if isinstance(definition,dict):
            missing=[k for k in definition['components'].values() if not isinstance(ids,list) or k not in ids]
            component_errors.extend({'derived':key,'missing':k} for k in missing)
            component_ok=component_ok and not missing
    cid=visible['card']['card_id']; use='hold' if action=='abstain' else action
    required={f'{cid}:action:hold:stress_loss',f'{cid}:action:{use}:utility'}
    required_ok=required<=claim_ids
    contract=bool(shape and legal and citation_valid and required_ok and numeric_ok and component_ok)
    reference=package['reference']['action_or_abstain']; basis=package['reference_basis']
    action_match=action==reference; basis_match=p.get('decision_basis')==basis
    regret=None
    if isinstance(action,str) and action in feasible and reference in feasible:
        selected=known[f'{cid}:action:{action}:utility']; best=known[f'{cid}:action:{reference}:utility']
        if selected is not None and best is not None:regret=best-selected
    return {'contract':contract,'shape':bool(shape),'legal':legal,'citations':citation_valid,'numeric_correct':numeric_ok,
            'required_claims':required_ok,'components_complete':component_ok,'component_errors':component_errors,
            'action':action,'basis':p.get('decision_basis'),'reference':reference,'reference_basis':basis,
            'action_match':action_match,'basis_match':basis_match,'grounded_policy_match':contract and action_match and basis_match,
            'regret':regret,'unnecessary_abstention':action=='abstain' and reference!='abstain'}

def report_check(candidate,known):
    envelope=isinstance(candidate,dict) and set(candidate)=={'summary','findings'} and isinstance(candidate.get('summary'),str)
    findings=candidate.get('findings') if isinstance(candidate,dict) else None
    known_count=isinstance(findings,list)
    findings=findings if known_count else []
    envelope=envelope and 1<=len(findings)<=4
    accepted=[]; rejected=[]
    for index,f in enumerate(findings):
        valid=isinstance(f,dict) and set(f)=={'issue','evidence_ids','implication','uncertainty'}
        valid=valid and all(isinstance(f[k],str) for k in ['issue','implication','uncertainty'])
        valid=valid and isinstance(f['evidence_ids'],list) and bool(f['evidence_ids']) and all(isinstance(k,str) and k in known for k in f['evidence_ids'])
        valid=valid and index<4
        (accepted if valid else rejected).append(index)
    return {'usable':bool(accepted),'fully_valid':bool(accepted and envelope and not rejected),
            'findings_count_known':known_count,'accepted':len(accepted),'rejected':len(rejected),'accepted_indices':accepted,'rejected_indices':rejected}

def main():
    assert (RUN/'results.json').exists() and (RUN/'analysis').is_dir(), 'Wait for complete run and main analysis directory'
    payload=json.loads((RUN/'results.json').read_text()); manifest=json.loads((RUN/'manifest.json').read_text())
    packages=json.loads((RUN/'evaluation-packages.json').read_text())
    rows=payload['rows']; measures=[]; handoffs=[]; changes=[]; mismatches=[]
    for row in rows:
        package=packages[row['card_id']]; workflow=row.get('workflow_evidence',{})
        if row['status']!='complete':
            measures.append({'job':row['job_id'],'arm':row['arm'],'case':row['card_id'],'status':row['status'],'contract':False,'grounded_policy_match':False});continue
        m=proposal_check(row.get('proposal') or {},package,workflow)
        measures.append({'job':row['job_id'],'arm':row['arm'],'case':row['card_id'],'status':row['status'],**m,'fallback':row['verification']['fallback']})
        for a,b in [('contract','primary_contract_pass'),('action_match','reference_match'),('basis_match','basis_match'),('grounded_policy_match','grounded_policy_match'),('components_complete','derivation_citations_valid')]:
            if m[a]!=row['proposal_metrics'][b]:mismatches.append({'job':row['job_id'],'metric':a,'independent':m[a],'saved':row['proposal_metrics'][b]})
        for report in row.get('specialist_reports',[]):
            stage=next(s for s in row['stages'] if s['role']==report['role'])
            h=report_check(stage.get('json_candidate'),package['visible_bundle']['evidence'])
            handoffs.append({'job':row['job_id'],'arm':row['arm'],'case':row['card_id'],'role':report['role'],**h})
            for a,b in [('usable','usable'),('fully_valid','fully_valid')]:
                if h[a]!=report[b]:mismatches.append({'job':row['job_id'],'role':report['role'],'metric':a})
            if h['accepted']!=report['validation']['accepted_finding_count'] or h['rejected']!=report['validation']['rejected_finding_count']:
                mismatches.append({'job':row['job_id'],'role':report['role'],'metric':'finding_counts'})
        if row['arm'] in {'challenged','self_review'}:
            trajectory=[{'role':stage['role'],**proposal_check(stage.get('parsed') or {},package,workflow)} for stage in row['stages'] if stage['role'] in {'proposer','revision','self_review'}]
            changes.append({'job':row['job_id'],'trajectory':trajectory,'challenge':row.get('challenge'),'initial_proposal':row['initial_proposal'],'final_proposal':row['proposal']})
    summaries={}; arms=['single','specialists','challenged','self_review']
    responses=[json.loads(x) for x in (RUN/'responses.jsonl').read_text().splitlines()]
    for arm in arms:
        selected=[x for x in measures if x['arm']==arm]; rs=[x for x in responses if x['arm']==arm]
        summaries[arm]={'planned':4,'completed':sum(x['status']=='complete' for x in selected),'contract':sum(x['contract'] for x in selected),
            'grounded_policy_match':sum(x['grounded_policy_match'] for x in selected),
            **{k:sum(x.get(k,False) for x in selected) for k in ['action_match','basis_match','numeric_correct','components_complete','fallback','unnecessary_abstention']},
            'calls':len(rs),'usage':{k:sum((x.get('usage') or {}).get(k) or 0 for x in rs) for k in ['input_units','output_units','total_units']},
            'usage_missing':sum(not x.get('usage') for x in rs)}
    pair_results=[]; index={(x['case'],x['arm']):x for x in measures}
    for left,right in [('single','specialists'),('specialists','challenged'),('self_review','challenged')]:
        cases=[]
        for cid in packages:
            a=index.get((cid,left));b=index.get((cid,right));valid=bool(a and b and a['status']==b['status']=='complete')
            cases.append({'case':cid,'complete':valid,'contract_delta':int(b['contract'])-int(a['contract']) if valid else None,
                          'policy_delta':int(b['grounded_policy_match'])-int(a['grounded_policy_match']) if valid else None})
        pair_results.append({'comparison':right+' minus '+left,'cases':cases,
            'policy_counts':{str(k):sum(c['policy_delta']==k for c in cases) for k in [-1,0,1,None]}})
    requests=[json.loads(x) for x in (RUN/'requests.jsonl').read_text().splitlines()]; leak_errors=[]
    for request in requests:
        content=json.loads(request['messages'][1]['content']);visible=content['evidence_bundle'];base=packages[request['card_id']]['visible_bundle']
        for key in ['card','actions','evidence','decision_rules','derived_quantities']:
            if visible[key]!=base[key]:leak_errors.append({'call':request['call_id'],'kind':'bundle_diff','field':key})
        for forbidden in ['evaluation_bundle','reference_basis','reference_action','reference_override','reference']:
            if forbidden in content:leak_errors.append({'call':request['call_id'],'kind':'private_payload_field','field':forbidden})
        for k,v in visible['evidence'].items():
            if k.endswith(':utility') and not isinstance(v,dict):leak_errors.append({'call':request['call_id'],'kind':'numeric_utility_supplied','field':k})
    source_mismatches=[]
    for rel,digest in manifest['source']['source_sha256'].items():
        if hashlib.sha256((RUN/'source'/rel).read_bytes()).hexdigest()!=digest:source_mismatches.append(rel)
    report_summary={'planned_reports':16,'observed_reports':len(handoffs),'usable':sum(x['usable'] for x in handoffs),'fully_valid':sum(x['fully_valid'] for x in handoffs),
                    'findings_accepted':sum(x['accepted'] for x in handoffs),'findings_rejected':sum(x['rejected'] for x in handoffs),'report_finding_count_unknown':sum(not x['findings_count_known'] for x in handoffs)}
    result={'run_id':payload['run_id'],'method':'Independent JSON/schema/arithmetic recount; no study evaluator imported.',
            'planned_jobs':16,'completed_jobs':payload['completed_jobs'],'calls':payload['calls'],
            'metric_mismatches':mismatches,'source_hash_mismatches':source_mismatches,'request_bundle_or_private_value_errors':leak_errors,
            'arms':summaries,'pairs':pair_results,'cases':measures,'handoff_summary':report_summary,'handoffs':handoffs,'changes':changes}
    (RUN/'analysis/independent-recount.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['completed_jobs','calls','metric_mismatches','source_hash_mismatches','request_bundle_or_private_value_errors','arms','handoff_summary','pairs']},indent=2))

if __name__=='__main__':main()
