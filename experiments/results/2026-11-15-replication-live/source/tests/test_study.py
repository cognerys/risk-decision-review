"""Offline checks of fixed follow-up cases, information boundaries and pilot runner."""
from pathlib import Path
import importlib.util
import json
import pytest
from risk_desk.data.study_cases import CASE_IDS,case_package,make_card
from risk_desk.graphs.review import evaluation_bundle_for


def runner():
    p=Path(__file__).resolve().parents[1]/'experiments/run_study.py'
    spec=importlib.util.spec_from_file_location('followup_runner',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def test_fixed_contrast_references_and_visible_utility_boundary():
    observed=[]
    for key in CASE_IDS:
        pack=case_package(key);visible=pack['visible_bundle'];evaluation=pack['evaluation_bundle']
        observed.append((pack['reference']['action_or_abstain'],pack['reference_basis']))
        for action in visible['actions']:
            prefix=action['evidence_prefix']
            assert isinstance(visible['evidence'][prefix+':utility'],dict)
            assert 'utility' not in visible['evidence'][prefix]
            d=visible['derived_quantities'][prefix+':utility']
            if action['feasible']:
                e=evaluation['evidence'];c=d['components']
                derived=-.5*e[c['stress_loss']]-d['desk_lambda']*e[c['cvar_95']]-sum(e[c[f]] for f in ['liquidity_cost','governance_penalty','tenor_penalty'])
                assert derived==pytest.approx(e[prefix+':utility'],abs=1e-5)
        assert 'reference_basis' not in visible
    assert observed==[('hedge_25','highest_utility'),('abstain','missing_credit'),('abstain','near_tie'),('hedge_25','highest_utility')]


def test_actor_contrast_changes_only_identity_and_mandate():
    a=make_card('case_01').model_dump();b=make_card('case_02').model_dump()
    a.pop('card_id');b.pop('card_id')
    a['mandate']['may_trade_books'].append('B3')
    assert a==b


def test_policy_metric_does_not_reward_wrong_abstention_basis():
    m=runner();p=case_package('case_02');bundle=evaluation_bundle_for(p['visible_bundle'],p['evaluation_bundle'])
    ids=['case_02:action:hold:stress_loss','case_02:action:hold:utility']
    citations=list(dict.fromkeys(ids+list(p['visible_bundle']['derived_quantities'][ids[1]]['components'].values())))
    proposal={'action_or_abstain':'abstain','decision_basis':'near_tie','reason':'fixture','procedural':'','economic':'','evidential':'',
              'evidence_ids':citations,'numeric_claims':[{'evidence_id':key,'value':bundle['evidence'][key]} for key in ids]}
    result=m.metrics(proposal,bundle,p['reference'],p['reference_basis'])
    assert result['primary_contract_pass'] and result['grounded_reference_match']
    assert not result['grounded_policy_match']
    proposal['decision_basis']='missing_credit';proposal['evidence_ids']=ids
    result=m.metrics(proposal,bundle,p['reference'],p['reference_basis'])
    assert not result['primary_contract_pass']


def test_offline_followup_retains_full_plan_and_private_evaluator(tmp_path):
    m=runner();out=tmp_path/'run';result=m.run_study(out)
    assert result['completed_jobs']==result['planned_jobs']==16
    assert result['calls']==56 and result['live_api_calls']==0
    assert len(result['summary']['paired'])==12
    assert all(x['grounded_policy_match']==0 and x['fallbacks']==4 for x in result['summary']['arms'].values())
    assert all(row['started_at_utc'] and row['finished_at_utc'] for row in result['rows'])
    requests=[json.loads(line) for line in (out/'requests.jsonl').read_text().splitlines()]
    assert all(row['started_at_utc'] for row in requests)
    for row in requests:
        payload=json.loads(row['messages'][1]['content'])
        assert 'reference' not in payload and 'evaluation_bundle' not in payload
        assert 'output_schema' in payload
    with pytest.raises(FileExistsError):m.run_study(out)
