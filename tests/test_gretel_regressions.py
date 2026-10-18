from unittest.mock import Mock
from supplier_app.core import Assistant, catalog
from research_agent.run_chat import grounded_chat
import pytest

@pytest.fixture(scope='module')
def data():
    return catalog()

def test_real_company_research_overrides_stale_selection(data):
    service = Mock()
    service.start.return_value = 'new-run'
    reply = Assistant(service, data).answer({'message':'What are the risks of Siemens AG?', 'mode':'deep', 'selected_ids':['SUPP_00012']})
    assert reply['kind'] == 'research'
    assert service.start.call_args.args[0]['company'] == 'Siemens AG'
    assert service.start.call_args.args[0]['scope'] == 'What are the risks of Siemens AG?'

def test_same_company_followup_does_not_restart_deep_research(data):
    service = Mock()
    service.store.get.return_value = {'company':'Siemens AG','status':'completed'}
    service.chat.return_value = {'answer':'Saved evidence','citations':[]}
    reply = Assistant(service,data).answer({'message':'Why is Siemens AG risky?', 'mode':'deep', 'run_id':'run', 'selected_ids':[]})
    assert reply['answer'] == 'Saved evidence'
    service.start.assert_not_called()

def test_grounded_chat_returns_only_valid_citations():
    llm = Mock()
    llm.structured.side_effect = lambda **kw: kw['schema'](answer='A recorded issue [1]',citation_numbers=[1])
    run = {'status':'completed','citations':[{'n':1,'quote':'issue'}]}
    assert grounded_chat(run,'What should we ask?',llm)['citations'] == run['citations']
    llm.structured.side_effect = lambda **kw: kw['schema'](answer='Invented [9]',citation_numbers=[9])
    with pytest.raises(ValueError, match='invalid report citations'):
        grounded_chat(run,'What should we ask?',llm)

def test_traction_count_uses_full_csv_even_with_selected_row_and_report(data):
    service=Mock()
    reply=Assistant(service,data).answer({'message':'How many companies do we have under traction?', 'selected_ids':['SUPP_00012'], 'run_id':'old-report'})
    assert '1,200' in reply['answer']
    assert reply['citations'][0]['filter'] == {'train_region_id':'traction'}
    assert reply['chart']['points'][0]['value'] == 1200
    service.start.assert_not_called()
    service.chat.assert_not_called()

def test_norbremse_deep_research_routes_even_with_selection(data):
    service=Mock();service.start.return_value='new-run'
    reply=Assistant(service,data).answer({'message':'Tell me about Norbremse', 'mode':'deep', 'selected_ids':['SUPP_00012']})
    assert reply['kind']=='research'
    assert service.start.call_args.args[0]['company']=='Norbremse'

def test_grouped_citations_are_validated_and_normalized():
    llm=Mock()
    llm.structured.side_effect=lambda **kw: kw['schema'](answer='Evidence [7, 8].',citation_numbers=[7,8])
    result=grounded_chat({'status':'completed','citations':[{'n':7},{'n':8}]},'short tldr',llm)
    assert result['answer']=='Evidence [7][8].'
    assert len(result['citations'])==2
    assert 'at most 80 words' in llm.structured.call_args.kwargs['system']

def test_short_summary_fallback_is_brief_and_not_a_qualification():
    from research_agent.run_chat import chat
    run={'status':'completed','schema_version':'research-run-v2','flags':[], 'verdict':'No red flags found in the sources checked'}
    reply=chat(run,'give me another short tldr on if the company is good for me or not?')
    assert len(reply['answer'].split())<80
    assert 'does not establish suitability' in reply['answer']
