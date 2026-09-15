import json
import pytest
from reference_research import validated_research

def result(url='https://example.com/interview'):
 return json.dumps(dict(subject='Artist',scope='A selected era',sources=[dict(title='Interview',url=url,findings='Electric piano')],musical_features='Soul',inference='Use a new motif',uncertainty='BPM unknown'))

def test_search_must_actually_run():
 with pytest.raises(ValueError,match='Web検索'):
  validated_research(result(),[])

def test_research_validates_links_and_keeps_evidence():
 with pytest.raises(ValueError):
  validated_research(result('javascript:alert(1)'),[{'query':'Artist'}])
 data=validated_research(result(),[{'query':'Artist'}])
 assert data['web_search_count']==1
 assert data['sources'][0]['findings']=='Electric piano'
 assert data['inference']=='Use a new motif'
 assert data['searched_at']

def test_empty_sources_not_silently_treated_as_research():
 data=json.loads(result());data['sources']=[]
 with pytest.raises(ValueError):validated_research(json.dumps(data),[{'query':'Artist'}])

from reference_research import validated_auto_research

def test_auto_knowledge_has_no_fake_citations():
 data=json.loads(result());data.update(mode='knowledge',decision_reason='Stable familiar traits',sources=[])
 checked=validated_auto_research(json.dumps(data),[])
 assert checked['mode']=='knowledge' and checked['searched_at'] is None
 data['sources']=json.loads(result())['sources']
 with pytest.raises(ValueError):validated_auto_research(json.dumps(data),[])

def test_auto_web_requires_real_search_and_evidence():
 data=json.loads(result());data.update(mode='web',decision_reason='Unknown work')
 with pytest.raises(ValueError):validated_auto_research(json.dumps(data),[])
 assert validated_auto_research(json.dumps(data),[{'query':'work'}])['mode']=='web'
 data['mode']='knowledge'
 assert validated_auto_research(json.dumps(data),[{'query':'work'}])['mode']=='web'
