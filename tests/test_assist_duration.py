import asyncio
import json
from unittest.mock import AsyncMock
import pytest
from codex_bridge import CodexBridge
from schemas import AssistInput, AssistResult

@pytest.mark.parametrize('mode,expected', [('auto',None),('fixed',120)])
def test_duration_payload_and_shared_research(mode,expected):
    async def scenario():
        bridge=CodexBridge()
        shared={'mode':'knowledge','musical_features':'fast four on the floor'}
        bridge.research_reference=AsyncMock(side_effect=AssertionError('must reuse album research'))
        payloads=[]
        async def rpc(method,params):
            if method=='account/read':return {'account':{'type':'chatgpt'}}
            if method=='thread/start':return {'thread':{'id':'test'}}
            if method=='turn/start':
                payloads.append(json.loads(params['input'][0]['text']))
                result={'title':'Fast circuit','style':'Eurobeat with an outro','lyrics':'[Instrumental]',
                        'melody_plan':'short repeated hook','explanation':'test','tips':[],
                        'duration':136,'duration_reason':'96 bars at 170 BPM','bpm':170}
                result=AssistResult(**result).model_dump()
                await bridge.queues['test'].put({'method':'item/completed','params':{'item':{'type':'agentMessage','text':json.dumps(result)}}})
                await bridge.queues['test'].put({'method':'turn/completed','params':{'turn':{'status':'completed'}}})
                return {'turn':{'id':'turn'}}
            return {}
        bridge.rpc=rpc
        result=await bridge.compose(AssistInput(engine='ace-xl-turbo',brief='Eurobeat',reference_track='reference',duration=120,duration_mode=mode),reference_research=shared)
        assert payloads[0]['duration'] is expected if expected is None else payloads[0]['duration']==expected
        assert result['reference_research']==shared
        assert result['duration_reason']=='96 bars at 170 BPM'
        bridge.research_reference.assert_not_awaited()
    asyncio.run(scenario())
