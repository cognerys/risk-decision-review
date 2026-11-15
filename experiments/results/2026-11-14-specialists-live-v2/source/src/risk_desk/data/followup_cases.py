"""Fixed EXP-008 contrast recipes, set before inspecting live responses."""
from __future__ import annotations
from copy import deepcopy
from risk_desk.data.cards import load_card
from risk_desk.schemas import DecisionCardVisible, Position
from risk_desk.engine.score import scorecard
from risk_desk.policy import DESK_LAMBDAS

CASE_IDS = ('case_01', 'case_02', 'case_03', 'case_04')
RECIPES = {
    'case_01': 'Thin-liquidity B13 plus foreign B3 physical/financial quantities x30; CP-RETAIL missing; authority B13 only.',
    'case_02': 'Same state as case_01; authority additionally includes B3.',
    'case_03': 'Thin-liquidity B13 financial quantities and stress limit x0.91; add B13 physical obligation of6000; credit known.',
    'case_04': 'Same construction as case_03 with scale1.07 instead of0.91.',
}


def make_card(case_id: str) -> DecisionCardVisible:
    if case_id not in CASE_IDS:
        raise KeyError(case_id)
    data=load_card('stress_thin_hedge_capped').model_dump()
    data.update(card_id=case_id,logged_action=None)
    if case_id in {'case_01','case_02'}:
        foreign=load_card('physical_obligation').model_dump()['positions']
        for p in foreign:p['quantity']*=30
        data['positions'].extend(foreign)
        for line in data['credit']:
            if line['counterparty_id']=='CP-RETAIL':
                line.update(status='missing',limit_eur=None,utilisation_eur=None)
        if case_id=='case_02':data['mandate']['may_trade_books'].append('B3')
    else:
        scale=.91 if case_id=='case_03' else 1.07
        for p in data['positions']:p['quantity']*=scale
        data['limits']['stress_limit_eur']*=scale
        physical=load_card('physical_obligation').model_dump()['positions'][0]
        assert physical['instrument']=='physical_supply_obligation'
        physical.update(position_id='B13-physical',book_id='B13',desk='power_hedge',
                        quantity=6000.,counterparty_id='CP-POWER')
        data['positions'].append(physical)
    return DecisionCardVisible.model_validate(data)


def decision_basis(card):
    reason=scorecard(card).reason
    return {'missing_credit':'missing_credit','near_tie':'near_tie',
            'breach_without_a_feasible_reducer':'unreducible_breach'}.get(reason,'highest_utility')


def case_package(case_id):
    from risk_desk.graphs.specialists_v2 import build_evidence_bundle
    card=make_card(case_id)
    evaluation=build_evidence_bundle(card)
    visible=deepcopy(evaluation)
    lam=DESK_LAMBDAS[card.mandate.desk]
    formula='-0.5*stress_loss - desk_lambda*cvar_95 - liquidity_cost - governance_penalty - tenor_penalty'
    derived={}
    for action in visible['actions']:
        prefix=action['evidence_prefix'];key=f'{prefix}:utility'
        definition={'derived':True,'formula':formula,'desk_lambda':lam,
                    'components':{field:f'{prefix}:{field}' for field in ['stress_loss','cvar_95','liquidity_cost','governance_penalty','tenor_penalty']},
                    'defined_when':'The action is feasible; infeasible actions have no utility.'}
        visible['evidence'][key]=definition
        derived[key]=definition
        # Do not leak derived values through aggregate action evidence added in v2.
        aggregate=visible['evidence'].get(prefix)
        if isinstance(aggregate,dict):aggregate.pop('utility',None)
    visible['derived_quantities']=derived
    visible['decision_rules']['utility_formula']=formula
    visible['decision_rules']['desk_lambda']=lam
    visible['decision_rules']['derived_claims']='Utility values are deliberately withheld. Calculate them from the cited components and formula; cite the declared utility ID plus each component ID. Do not treat a derived definition as missing credit or an unknown measured value.'
    reference=scorecard(card).model_dump()
    return {'card':card.model_dump(),'visible_bundle':visible,'evaluation_bundle':evaluation,
            'reference':reference,'reference_basis':decision_basis(card),'recipe':RECIPES[case_id]}
