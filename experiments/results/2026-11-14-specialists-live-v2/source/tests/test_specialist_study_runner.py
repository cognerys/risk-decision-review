"""Offline validation of the preregistered pilot runner, not model performance."""
import importlib.util
from pathlib import Path
import json
import os
import pytest


def runner():
    path=Path(__file__).resolve().parents[1]/'experiments/run_specialist_study.py'
    spec=importlib.util.spec_from_file_location('specialist_runner',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_full_offline_plan_retains_provenance_stages_and_planned_denominators(tmp_path,monkeypatch):
    m=runner()
    monkeypatch.setenv('RISK_DESK_LIVE','1')
    result=m.run_study(tmp_path/'study')
    assert result['completed_jobs']==result['planned_jobs']==24
    assert result['calls']==84
    assert result['live_api_calls']==0
    assert len(result['summary']['paired'])==18
    assert all(x['primary_contract_pass']==0 and x['fallbacks']==6 for x in result['summary']['arms'].values())
    assert all(len(row['stages'])==row['calls'] for row in result['rows'])
    assert os.environ['RISK_DESK_LIVE']=='1'
    assert (tmp_path/'study/source/src/risk_desk/graphs/specialists.py').exists()
    assert not list((tmp_path/'study/source').rglob('.env*'))
    manifest=json.loads((tmp_path/'study/manifest.json').read_text())
    assert manifest['max_generated_units']==1800
    with pytest.raises(FileExistsError):m.run_study(tmp_path/'study')


def test_errors_are_not_retried_and_stop_after_two_consecutive_jobs(tmp_path):
    m=runner()
    class Fails:
        def invoke(self,*args,**kwargs):raise RuntimeError('simulated provider error')
    result=m.run_study(tmp_path/'errors',model_override=Fails())
    assert result['calls']==2
    assert result['completed_jobs']==0
    assert len(result['unattempted_jobs'])==22
    assert result['stop_reason']=='two_consecutive_job_errors'
    assert all(x['planned']==6 for x in result['summary']['arms'].values())
    assert all(x['contract_delta'] is None for x in result['summary']['paired'])


def test_call_budget_blocks_before_provider_invocation(tmp_path):
    m=runner()
    class Never:
        def invoke(self,*args,**kwargs):raise AssertionError('must not invoke')
    counted=m.AuditedModel(Never(),tmp_path,{'calls':90},{})
    with pytest.raises(m.CallLimit):counted.invoke([])
    assert not list(tmp_path.iterdir())


def test_grounded_but_unnecessary_abstention_is_not_a_reference_match():
    m=runner()
    from risk_desk.graphs.specialists import build_evidence_bundle
    bundle=build_evidence_bundle('ordinary_inside')
    ids=['ordinary_inside:action:hold:stress_loss','ordinary_inside:action:hold:utility']
    proposal={'action_or_abstain':'abstain','reason':'fixture','procedural':'','economic':'','evidential':'',
              'evidence_ids':ids,'numeric_claims':[{'evidence_id':key,'value':bundle['evidence'][key]} for key in ids]}
    measured=m.metrics(proposal,bundle)
    assert measured['primary_contract_pass'] is True
    assert measured['grounded_reference_match'] is False
    assert measured['synthetic_utility_regret'] is None


def test_usage_and_canonical_prompt_roles_survive_secret_filter(tmp_path):
    from langchain_core.messages import AIMessage
    m=runner()
    class Fake:
        def invoke(self,*args,**kwargs):
            return AIMessage(content='{}',usage_metadata={'input_tokens':12,'output_tokens':4,'total_tokens':16,
                             'output_token_details':{'reasoning':2}})
    model=m.AuditedModel(Fake(),tmp_path,{'calls':0},{'job_id':'test'})
    model.invoke([('system','instructions'),('user','evidence')])
    saved=json.loads((tmp_path/'responses.jsonl').read_text())
    assert saved['usage']['total_units']==16
    assert saved['usage']['output_details']['reasoning']==2
    request=json.loads((tmp_path/'requests.jsonl').read_text())
    assert request['messages'][0]=={'role':'system','content':'instructions'}
