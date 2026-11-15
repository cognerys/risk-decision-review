"""Run the four review configurations over the four study cases. Offline (scripted model) unless --live."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from risk_desk.config import Settings
from risk_desk.data.study_cases import CASE_IDS, case_package
from risk_desk.engine.score import scorecard, apply_action
from risk_desk.llm import ScriptedChatModel
from risk_desk.tracing import redact
from risk_desk import tracing

CARDS = list(CASE_IDS)
ARMS = ['single', 'specialists', 'challenged', 'self_review']
CALL_CAP = 60
OUTPUT_TOKENS = 1800
PROTOCOL = ROOT / 'experiments/protocol.md'


def write_json(path, value):
    path.write_text(json.dumps(redact(value), indent=2, allow_nan=False) + '\n')


def append_json(path, value):
    with path.open('a') as handle:
        handle.write(json.dumps(redact(value), allow_nan=False) + '\n')


def jobs():
    result = []
    for index, card in enumerate(CARDS):
        offset = index % len(ARMS)
        arms = ARMS[offset:] + ARMS[:offset]
        result.extend({'card_id': card, 'arm': arm, 'job_id': f'{card}--{arm}'} for arm in arms)
    return result


class CallLimit(RuntimeError):
    pass


class AuditedModel:
    def __init__(self, inner, output, counter, identity):
        self.inner, self.output, self.counter, self.identity = inner, output, counter, identity

    def invoke(self, messages, *args, **kwargs):
        if self.counter['calls'] >= CALL_CAP:
            raise CallLimit('Prespecified global call cap reached')
        self.counter['calls'] += 1
        call_id = self.counter['calls']
        request = [{'role': m[0], 'content': m[1]} if isinstance(m, (tuple, list)) and len(m)==2
                   else {'role': getattr(m, 'type', 'message'), 'content': getattr(m, 'content', m)} for m in messages]
        append_json(self.output / 'requests.jsonl', {**self.identity, 'call_id': call_id, 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'messages': request})
        started = time.monotonic()
        try:
            response = self.inner.invoke(messages, *args, **kwargs)
        except Exception as exc:
            append_json(self.output / 'responses.jsonl', {**self.identity, 'call_id': call_id,
                        'status': 'error', 'finished_at_utc': datetime.now(timezone.utc).isoformat(), 'error_type': type(exc).__name__, 'error': str(exc),
                        'latency_seconds': time.monotonic() - started})
            raise
        usage = getattr(response, 'usage_metadata', None) or {}
        # The shared secret filter removes token-named keys. Keep numeric usage
        # under unambiguous non-secret names, rather than weakening that filter.
        retained_usage = {'input_units': usage.get('input_tokens'), 'output_units': usage.get('output_tokens'),
                          'total_units': usage.get('total_tokens'), 'unit': 'tokens',
                          'input_details': usage.get('input_token_details'),
                          'output_details': usage.get('output_token_details')}
        append_json(self.output / 'responses.jsonl', {**self.identity, 'call_id': call_id,
                    'status': 'complete', 'finished_at_utc': datetime.now(timezone.utc).isoformat(), 'raw_content': response.content,
                    'usage': retained_usage,
                    'metadata': getattr(response, 'response_metadata', {}),
                    'latency_seconds': time.monotonic() - started})
        return response


def provenance(output):
    paths = sorted([*ROOT.glob('src/**/*.py'), *ROOT.glob('src/**/*.json'),
                    *ROOT.glob('tests/*.py'), ROOT / 'pyproject.toml', Path(__file__).resolve(), PROTOCOL])
    hashes = {}
    for source in paths:
        relative = source.relative_to(ROOT)
        target = output / 'source' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        hashes[str(relative)] = hashlib.sha256(source.read_bytes()).hexdigest()
    packages = sorted({dist.metadata['Name']: dist.version for dist in importlib.metadata.distributions()}.items())
    (output / 'requirements-frozen.txt').write_text(''.join(f'{name}=={version}\n' for name, version in packages))
    return {'python': sys.version, 'platform': sys.platform, 'source_sha256': hashes,
            'head': subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip(),
            'worktree_status': subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain=v1'], capture_output=True, text=True).stdout.splitlines()}


def metrics(proposal, bundle, reference, reference_basis):
    from risk_desk.graphs.review import assess_proposal
    measured=assess_proposal(proposal or {},bundle)
    action=(proposal or {}).get('action_or_abstain')
    basis=(proposal or {}).get('decision_basis')
    match=action==reference['action_or_abstain']
    return {**measured,'action':action,'reference_action':reference['action_or_abstain'],
            'decision_basis':basis,'reference_basis':reference_basis,'basis_match':basis==reference_basis,
            'reference_match':match,'grounded_reference_match':bool(measured['primary_contract_pass'] and match),
            'grounded_policy_match':bool(measured['primary_contract_pass'] and match and basis==reference_basis),
            'abstain':action=='abstain'}


def summarise(rows):
    by_job = {(row['card_id'], row['arm']): row for row in rows}
    summaries = {}
    for arm in ARMS:
        items = [row for row in rows if row['arm'] == arm]
        complete = [row for row in items if row['status'] == 'complete']
        summaries[arm] = {'planned': len(CARDS), 'attempted': len(items), 'completed': len(complete),
            'primary_contract_pass': sum(row['proposal_metrics']['primary_contract_pass'] for row in complete),
            'grounded_reference_match': sum(row['proposal_metrics']['grounded_reference_match'] for row in complete),
            'grounded_policy_match': sum(row['proposal_metrics']['grounded_policy_match'] for row in complete),
            'basis_match': sum(row['proposal_metrics']['basis_match'] for row in complete),
            'reference_match': sum(row['proposal_metrics']['reference_match'] for row in complete),
            'final_reference_match': sum(row['final_reference_match'] for row in complete),
            'abstentions': sum(row['proposal_metrics']['abstain'] for row in complete),
            'fallbacks': sum(bool(row['verification'].get('fallback')) for row in complete),
            'calls': sum(row['calls'] for row in items),
            'latency_seconds': sum(row['latency_seconds'] for row in items)}
    paired = []
    for left, right in [('single','specialists'),('specialists','challenged'),('self_review','challenged')]:
        for card in CARDS:
            a,b = by_job.get((card,left)),by_job.get((card,right))
            evaluable=bool(a and b and a['status']==b['status']=='complete')
            paired.append({'card_id':card,'left':left,'right':right,'evaluable':evaluable,
                'contract_delta': int(b['proposal_metrics']['primary_contract_pass'])-int(a['proposal_metrics']['primary_contract_pass']) if evaluable else None,
                'grounded_policy_delta': int(b['proposal_metrics']['grounded_policy_match'])-int(a['proposal_metrics']['grounded_policy_match']) if evaluable else None,
                'grounded_reference_delta': int(b['proposal_metrics']['grounded_reference_match'])-int(a['proposal_metrics']['grounded_reference_match']) if evaluable else None})
    return {'arms':summaries,'paired':paired,
            'interpretation':'Single exploratory pass on four composed cases in two correlated contrast pairs. No significance, generalisation or causal role-benefit claim.'}


def run_study(output: Path, *, live=False, model_override=None, experiment='EXP-008'):
    from risk_desk.graphs.review import build_research_graph, evaluation_bundle_for, PROMPT_VERSION
    if output.exists():
        raise FileExistsError('Choose a fresh output directory; retained studies are immutable')
    if not PROTOCOL.exists():
        raise FileNotFoundError('Write the protocol before running the study')
    if live and not os.environ.get('OPENAI_API_KEY','').strip():
        raise RuntimeError('Existing OPENAI_API_KEY must be loaded in the process environment')
    output.mkdir(parents=True)
    run_id=f'{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}'
    env_keys=['RISK_DESK_LIVE','LANGSMITH_TRACING','LANGCHAIN_TRACING_V2']
    old_env={key:os.environ.get(key) for key in env_keys}
    old_mirror = tracing.MIRROR_PATH
    counter={'calls':0}; rows=[]; stop_reason=None
    try:
        os.environ['RISK_DESK_LIVE']='1' if live else '0'
        os.environ['LANGSMITH_TRACING']='false'; os.environ['LANGCHAIN_TRACING_V2']='false'
        tracing.MIRROR_PATH = output/'trace.jsonl'
        settings=Settings.from_env()
        plan={'run_id':run_id,'mode':'live' if live else 'offline-scripted','experiment':experiment,
              'prompt_version':PROMPT_VERSION,'settings':asdict(settings),'jobs':jobs(),
              'call_cap':CALL_CAP,'max_generated_units':OUTPUT_TOKENS,'generated_unit':'tokens',
              'timeout_seconds':60,'sdk_retries':0,
              'source':provenance(output)}
        write_json(output/'manifest.json',plan)
        # Store all inputs and reference targets before making any calls. Targets are not model inputs.
        packages={card:case_package(card) for card in CARDS}
        bundles={card:pack['visible_bundle'] for card,pack in packages.items()}
        write_json(output/'evidence-bundles.json',bundles)
        write_json(output/'evaluation-packages.json',packages)
        write_json(output/'reference-targets.json',{card:{'recommendation':p['reference'],'decision_basis':p['reference_basis']} for card,p in packages.items()})
        if model_override is not None:
            inner=model_override
        elif live:
            from langchain_openai import ChatOpenAI
            inner=ChatOpenAI(model=settings.model, reasoning_effort=settings.reasoning_effort,
                             max_retries=0, timeout=60, max_completion_tokens=OUTPUT_TOKENS)
        else:
            inner=ScriptedChatModel()
        consecutive_errors=0
        for job in plan['jobs']:
            identity={**job,'run_id':run_id}
            model=AuditedModel(inner,output,counter,identity)
            package=packages[job['card_id']]
            graph=build_research_graph(arm=job['arm'],model_factory=lambda settings:model,checkpointer=None,
                bundle_override=package['visible_bundle'],evaluation_bundle_override=package['evaluation_bundle'],reference_override=package['reference'])
            started=time.monotonic(); before=counter['calls']; row={**identity,'started_at_utc':datetime.now(timezone.utc).isoformat()}
            try:
                result=graph.invoke({**identity,'auto_committee':True},config={'recursion_limit':30})
                bundle=evaluation_bundle_for(result['evidence_bundle'],package['evaluation_bundle'])
                row.update(status='complete',workflow_evidence=bundle['workflow_evidence'],initial_proposal=result.get('initial_proposal'),
                           proposal=result.get('proposal'),response=result.get('response'),
                           initial_response=result.get('initial_response'),stages=result.get('stages',[]),
                           specialist_reports=result.get('specialist_reports',[]),challenge=result.get('challenge'),
                           revision_count=result.get('revision_count',0),verification=result['verification'],
                           recommendation=result['recommendation'],
                           initial_metrics=metrics(result.get('initial_proposal'),bundle,package['reference'],package['reference_basis']),
                           proposal_metrics=metrics(result.get('proposal'),bundle,package['reference'],package['reference_basis']),
                           final_action=result['recommendation'].get('action_or_abstain'),
                           final_reference_match=result['recommendation'].get('action_or_abstain') == package['reference']['action_or_abstain'],
                           proposal_stage_metrics=[{'role':stage['role'], **metrics(stage.get('parsed'),bundle,package['reference'],package['reference_basis'])}
                             for stage in result.get('stages',[]) if stage['role'] in {'proposer','revision','self_review'}])
                consecutive_errors=0
            except Exception as exc:
                row.update(status='error',error_type=type(exc).__name__,error=redact(str(exc)))
                consecutive_errors+=1
                if isinstance(exc,CallLimit) or counter['calls']>=CALL_CAP:stop_reason='global_call_cap'
                elif consecutive_errors>=2:stop_reason='two_consecutive_job_errors'
            row.update(calls=counter['calls']-before,latency_seconds=time.monotonic()-started,finished_at_utc=datetime.now(timezone.utc).isoformat())
            rows.append(row); append_json(output/'rows.jsonl',row)
            print(json.dumps({'job':job['job_id'],'status':row['status'],'calls':counter['calls'],
                              'completed':len(rows),'planned':16}),flush=True)
            if stop_reason:break
        payload={'run_id':run_id,'mode':plan['mode'],'calls':counter['calls'],
                 'live_api_calls':counter['calls'] if live else 0,
                 'completed_jobs':sum(x['status']=='complete' for x in rows),'planned_jobs':16,
                 'unattempted_jobs':plan['jobs'][len(rows):],
                 'stop_reason':stop_reason,'rows':rows,'summary':summarise(rows)}
        write_json(output/'results.json',payload)
        return payload
    finally:
        tracing.MIRROR_PATH = old_mirror
        for key,value in old_env.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--experiment',default='EXP-008',help='Label recorded in the manifest; give a replication its own label')
    args=parser.parse_args()
    output=args.output_dir or ROOT/'experiments/results'/f'run-{uuid4().hex[:8]}'
    result=run_study(output,live=args.live,experiment=args.experiment)
    print(json.dumps({'output':str(output),'mode':result['mode'],'calls':result['calls'],
                      'completed_jobs':result['completed_jobs'],'stop_reason':result['stop_reason']}))
    return 0 if result['completed_jobs']==16 else 2


if __name__=='__main__':
    raise SystemExit(main())
