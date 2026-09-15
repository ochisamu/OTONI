import asyncio
import json
import pytest
from codex_bridge import CodexBridge
from schemas import AssistInput, AssistResult, MusicChoices
from prompting import preset_style
from language_policy import LANGUAGE_INSTRUCTIONS, VOCAL_LANGUAGE_CODES
from albums import PLAN_INSTRUCTIONS


@pytest.mark.parametrize('engine', ['yue2', 'ace-xl-turbo', 'diffsynth-music', 'mulacover'])
def test_mixed_language_reaches_composer_and_preserves_existing_lyrics(engine):
    async def scenario():
        bridge = CodexBridge()
        original = '[Chorus]\nここから歩こう\nTake one more step'
        async def rpc(method, params):
            if method == 'account/read':
                return {'account': {'type': 'chatgpt'}}
            if method == 'thread/start':
                assert LANGUAGE_INSTRUCTIONS in params['baseInstructions']
                return {'thread': {'id': 'test'}}
            if method == 'turn/start':
                payload = json.loads(params['input'][0]['text'])
                assert payload['language'] == '日本語＋英語フレーズ'
                assert 'short English hooks' in payload['selection_reference']
                draft = AssistResult(title='One More Step', style='Japanese pop with English hooks',
                                     lyrics='unwanted rewrite', explanation='test', tips=[]).model_dump()
                await bridge.queues['test'].put({'method':'item/completed','params':{'item':{'type':'agentMessage','text':json.dumps(draft)}}})
                await bridge.queues['test'].put({'method':'turn/completed','params':{'turn':{'status':'completed'}}})
                return {'turn': {'id': 'turn'}}
            return {}
        bridge.rpc = rpc
        result = await bridge.compose(AssistInput(engine=engine, brief='前向きな曲', language='日本語＋英語フレーズ',
            current_lyrics=original, preserve_lyrics=True, choices=MusicChoices(genre='pop')))
        assert result['lyrics'] == original
    asyncio.run(scenario())


def test_language_conditioning_and_album_policy():
    assert LANGUAGE_INSTRUCTIONS in PLAN_INSTRUCTIONS
    assert VOCAL_LANGUAGE_CODES['日本語＋英語フレーズ'] == 'ja'
    assert 'English hooks' in preset_style(MusicChoices(vocal='female'), '日本語＋英語フレーズ')
    assert AssistInput(brief='新しい曲').language == '日本語'
