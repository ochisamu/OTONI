const $ = id => document.getElementById(id);
const labels = {queued:'生成待ち',preparing:'Codexでメロディー・構成を調整中',running:'生成中',completed:'完成',failed:'失敗',cancelled:'キャンセル済み',interrupted:'中断'};
let draft = null, selectedJob = null, listSignature = '', accountReady = false, loginPending = false;
const songCards = new Map();
const draftFields = ['title','style','lyrics','brief','language','cot','seed','cfg','maxTokens','abc','genre','tempo','bpm','vocal','mood','melodyFocus','referenceTrack','engine','duration','outputFormat','sourceSongId','sourceTitle','derivationMode','referenceStrength','controlMode'];
let draftEpoch=0,resetUndo=null;
const emptyDraft=Object.fromEntries(draftFields.map(k=>{const el=$(k);return [k,el.tagName==='SELECT'?(Array.from(el.options).find(o=>o.defaultSelected)||el.options[0]).value:el.defaultValue];}));
const sample = {
  title:'After the Rain',
  style:'City pop, 104 BPM, warm expressive female lead vocal, groovy electric bass, clean syncopated rhythm guitar, Rhodes electric piano, tight live drums and soft analog synth pads. Bittersweet but hopeful, walking through neon reflections after rain. Intimate verses build into a bright, open chorus with gentle backing harmonies. Clear vocal-forward mix, warm low end, natural dynamics.',
  lyrics:'[Intro]\n\n[Verse]\nThe rain has left a silver line\nAcross the streets we used to know\nI find a little borrowed light\nIn every window walking home\n\n[Pre-Chorus]\nThe clouds are moving out of view\nAnd I am learning something new\n\n[Chorus]\nAfter the rain, I start again\nOne little step into the blue\nAfter the rain, I breathe your name\nAnd let the morning carry through\n\n[Verse]\nThe coffee shop is closing down\nA bicycle goes drifting by\nI used to fear this quiet town\nNow every road becomes the sky\n\n[Chorus]\nAfter the rain, I start again\nOne little step into the blue\nAfter the rain, I breathe your name\nAnd let the morning carry through\n\n[Outro]\nAfter the rain\nI start again',
  cot:'full',seed:831001,max_tokens:9000,cfg_scale:null,abc:''
};

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json','X-Yue-Request':'studio'},body:JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) {
    const detail = result.detail;
    throw new Error(Array.isArray(detail) ? detail.map(e=>`${e.loc?.at(-1)}: ${e.msg}`).join('\n') : detail || `HTTP ${response.status}`);
  }
  return result;
}
function notify(message, error=false) {
  $('notice').textContent=message; $('notice').classList.toggle('error',error); $('notice').hidden=false;
}
function node(tag, text, cls) {const el=document.createElement(tag); if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;}
function link(label,url){const a=node('a',label);a.href=url;return a;}
function duration(seconds){return `${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;}
function countLyrics(){$('lyricsCount').textContent=`${$('lyrics').value.length.toLocaleString()}文字`;}
function saveDraft(){try{localStorage.setItem('yue2-draft',JSON.stringify({...Object.fromEntries(draftFields.map(k=>[k,$(k).value])),autoAssist:$('autoAssist').checked}));}catch{}countLyrics();}
function fillSong(input){$('controlMode').value=input.control_mode||'native';$('sourceSongId').value=input.source_song_id||'';$('sourceTitle').value=input.source_title||input.source_song_id||'';$('derivationMode').value=input.derivation_mode||'none';$('referenceStrength').value=input.reference_strength??0.8;$('brief').value=input.brief||'';$('outputFormat').value=input.output_format||'m4a';$('engine').value=input.engine||'yue2';$('duration').value=input.duration_mode==='auto'?'auto':String(input.duration||60);if(!$('duration').value){const o=node('option',`${input.duration}秒`);o.value=String(input.duration);$('duration').append(o);$('duration').value=o.value;}$('referenceTrack').value=input.reference_track||'';for(const k of ['title','style','lyrics','cot','seed','abc'])if(input[k]!==undefined)$(k).value=input[k];$('maxTokens').value=input.max_tokens??9000;$('cfg').value=input.cfg_scale??'';for(const k of ['genre','tempo','vocal','mood'])$(k).value=input.choices?.[k]||'auto';$('bpm').value=input.choices?.bpm??'';$('melodyFocus').value=input.choices?.melody||'catchy';$('autoAssist').checked=input.auto_assist??false;if(input.language)$('language').value=input.language;updateMode();saveDraft();}
try{const saved=JSON.parse(localStorage.getItem('yue2-draft')||'null');if(saved){if(saved.duration&&!Array.from($('duration').options).some(o=>o.value===String(saved.duration))){const opt=node('option',`${saved.duration}秒`);opt.value=String(saved.duration);$('duration').append(opt);}for(const k of draftFields)if(saved[k]!==undefined)$(k).value=saved[k];if(typeof saved.autoAssist==='boolean')$('autoAssist').checked=saved.autoAssist;}}catch{}
for(const k of draftFields)$(k).addEventListener('input',saveDraft);
countLyrics();
function musicChoices(){return {genre:$('genre').value,tempo:$('tempo').value,bpm:$('bpm').value?Number($('bpm').value):null,vocal:$('vocal').value,mood:$('mood').value,melody:$('melodyFocus').value};}
function validateChoices(){if(!$('bpm').checkValidity()){$('bpm').reportValidity();return false;}return true;}
function isTimedEngine(){return $('engine').value!=='yue2';}
function engineLabel(engine){return {'mixed':'モデル混在','yue2':'YuE2','ace-xl-turbo':'ACE-Step','stable-audio-3-medium':'Stable Audio 3','diffsynth-music':'DiffSynth Music','mulacover':'MuLaCover'}[engine]||engine;}
function engineFields(){const auto=$('engine').value!=='mulacover'&&isTimedEngine()&&$('duration').value==='auto'&&$('derivationMode').value!=='cover';return {engine:$('engine').value,duration:auto?180:Number($('duration').value)||60,duration_mode:auto?'auto':'fixed'};}
function updateMode(){
  const stable=$('engine').value==='stable-audio-3-medium';
  updateControlModels();
  $('vocal').disabled=stable;
  if(stable)$('vocal').value='instrumental';
  updateDerivative();
  const automaticDuration=$('engine').value!=='mulacover'&&isTimedEngine()&&$('duration').value==='auto'&&$('derivationMode').value!=='cover';
  if(automaticDuration)$('autoAssist').checked=true;
  $('autoAssist').disabled=automaticDuration;
  const inst=$('vocal').value==='instrumental',ace=isTimedEngine();
  $('tempoHint').textContent=ace?'BPMはACE-Stepの数値条件に渡します。完成音声のテンポ一致は保証されず、現在は音声からのBPM測定を行っていません。':'BPM指定時は自動生成したABC譜面のテンポを設定してから音声化します。ABCを自分で指定した場合はその譜面を優先、CoT offでは文章による希望のみです。譜面のBPMと完成音声の一致は別途確認が必要です。';
  $('lyrics').disabled=inst||$('derivationMode').value==='score'||($('engine').value==='diffsynth-music'&&$('controlMode').value==='vocals');$('lyrics').required=!inst&&!$('autoAssist').checked;$('style').required=!inst&&!$('autoAssist').checked;
  $('lyrics').maxLength=ace?4096:12000;$('lyrics').rows=inst?4:13;document.querySelector('.lyric-tools').hidden=inst;$('instrumentalHint').hidden=!inst;$('language').disabled=inst;
  $('instrumentalHint').textContent=ace?'歌詞を送らず、ACE-Stepのインスト指定と楽器の主旋律で生成します。':'歌詞欄に [Instrumental] を送り、歌なし・楽器の主旋律を指定します。完全に声が入らない保証はありません。';
  $('aceControls').hidden=!ace;$('aceSettingsHint').hidden=!ace;
  for(const el of document.querySelectorAll('[data-yue-only]')){el.hidden=ace;for(const input of el.querySelectorAll('input,select,textarea'))input.disabled=ace;}
  $('engineHint').textContent=ace?'ACE-Step 1.5 XL Turbo · インストにも対応。曲の長さを指定できます。':'YuE2-3B · メロディー・和音のABC譜面を経由して生成します。';
  $('modelLanguageHint').textContent=ace?'インストではピアノやギターなど主旋律の楽器を指定すると、イメージを伝えやすくなります。歌声ありは日本語・英語・中国語を選べます。':'具体的な楽器・声・展開がよい出発点。日本語の歌唱は発音を聴いて調整しましょう。YuE2の主な対応言語は英語・中国語です。';
  $('guideLink').href=ace?'https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/docs/en/Tutorial.md':'https://github.com/multimodal-art-projection/YuE/blob/88da114a67df892af0329472073b96a5ef700b93/docs/generation.md';
  $('guideLink').textContent=ace?'参照する公式ACE-Stepガイド ↗':'参照する公式YuE2ガイド ↗';if(stable){$('tempoHint').textContent='BPMは文章で指定します。完成音声のテンポ一致は保証されません。';$('engineHint').textContent='Stable Audio 3 Medium · ローカルのインスト専用生成。';$('instrumentalHint').textContent='歌詞や構成タグを渡さず、楽器・主旋律・展開を英語の文章で指定します。';$('modelLanguageHint').textContent='Codexがインスト向けの英語プロンプトを提案します。';$('aceSettingsHint').hidden=true;$('guideLink').href='https://kb.stability.ai/knowledge-base/stable-audio-3-prompt-guide';$('guideLink').textContent='Stable Audio 3 公式プロンプトガイド ↗';} if($('derivationMode').value==='score'){$('cot').disabled=true;$('abc').disabled=true;}$('applyAll').disabled=$('derivationMode').value==='score';finishControlHints();
}
for(const name of ['vocal','autoAssist','engine','duration'])$(name).addEventListener('change',()=>{updateMode();saveDraft();});
updateMode();
$('preset').addEventListener('click',async()=>{if(!validateChoices())return;const epoch=draftEpoch;try{const result=await api('/api/preset',{...engineFields(),brief:'選択からスタイルを作成',language:$('language').value,choices:musicChoices()});if(epoch!==draftEpoch)return;if($('style').value.trim()&&!confirm('現在のスタイルを選択内容から作り直しますか？'))return;$('style').value=result.style;saveDraft();notify('選択内容からスタイルを作成しました。自動支援OFFならこのまま使用、ONならCodexがさらに整えます。');}catch(e){notify(e.message,true);}});
$('sample').addEventListener('click',()=>{if(($('lyrics').value.trim()||$('style').value.trim())&&!confirm('現在のスタイルと歌詞をサンプルに置き換えますか？'))return;fillSong(sample);notify('英語のオリジナル歌詞サンプルを入力しました。スタイルや歌詞を自由に変更できます。');});
for(const button of document.querySelectorAll('[data-idea]'))button.addEventListener('click',()=>{$('brief').value=button.dataset.idea;saveDraft();});
for(const button of document.querySelectorAll('[data-section]'))button.addEventListener('click',()=>{const el=$('lyrics'),start=el.selectionStart,end=el.selectionEnd;el.setRangeText(`\n\n[${button.dataset.section}]\n`,start,end,'end');el.focus();saveDraft();});
$('randomSeed').addEventListener('click',()=>{$('seed').value=crypto.getRandomValues(new Uint32Array(1))[0]%2147483648;saveDraft();});

async function refreshAccount(){
  const result=await api('/api/account');const account=result.account;
  accountReady=!!account&&['chatgpt','chatgptAuthTokens'].includes(account.type);
  $('login').textContent=accountReady?`● ChatGPT · ${account.planType||'接続済み'}`:'ChatGPTでログイン';
  $('login').title=result.error||'Codex App ServerのChatGPTログイン';
  if(accountReady&&loginPending){loginPending=false;notify('ChatGPTに接続しました。入力支援を利用できます。');}
  if(!result.available)$('assistStatus').textContent=result.error;
}
$('login').addEventListener('click',async()=>{
  try{if(accountReady){await refreshAccount();notify('Codex App ServerのChatGPTログインを利用中です。');return;}
    const result=await api('/api/login',{});loginPending=true;
    notify('ブラウザでChatGPTにログインしてください。完了すると自動で接続状態が更新されます。');
    const a=link('ログイン画面を開く ↗',result.authUrl);a.target='_blank';a.rel='noopener noreferrer';$('notice').append(document.createTextNode(' '),a);window.open(result.authUrl,'_blank','noopener,noreferrer');
  }catch(e){notify(e.message,true);}
});
async function loadModels(){try{const result=await api('/api/models');for(const m of result.data||[]){const opt=node('option',m.displayName||m.model);opt.value=m.model;$('aiModel').append(opt);}}catch{}}

$('assist').addEventListener('click',async()=>{
  if(!validateChoices())return;
  const epoch=draftEpoch;const button=$('assist');button.disabled=true;button.textContent='✧ 下書きを考えています…';$('assistStatus').textContent=$('referenceTrack').value.trim()?'参考名を確認し、必要ならWebで調べてから提案します。':'曲の構成・歌いやすさ・音の具体性を整えています。';
  try{
    const job=await api('/api/assist',{...engineFields(),brief:$('brief').value.trim()||'選択内容に合う曲を作ってください。',language:$('language').value,reference_track:$('referenceTrack').value,choices:musicChoices(),current_abc:isTimedEngine()?'':$('abc').value,current_style:$('style').value,current_lyrics:$('lyrics').value,preserve_lyrics:$('preserve').checked,model:$('aiModel').value});
    let result;
    do{await new Promise(resolve=>setTimeout(resolve,1800));result=await api(`/api/assist/${job.id}`);}while(result.status==='running');
    if(result.status!=='completed')throw new Error(result.error||'入力支援に失敗しました');
    if(epoch!==draftEpoch)return;draft=result.result;renderReferenceResearch($('draftResearch'),draft.reference_research);$('draft').hidden=false;$('draftTitle').textContent=draft.title;$('draftMelody').textContent=(draft.bpm?`提案BPM: ${draft.bpm}\n`:'')+(draft.melody_plan||'');$('draftExplanation').textContent=(isTimedEngine()?`提案した長さ: ${draft.duration}秒\n${draft.duration_reason||''}\n`:'')+draft.explanation;$('draftReference').hidden=!draft.reference_analysis&&!draft.originality_note;$('referenceAnalysis').textContent=draft.reference_analysis||'';$('originalityNote').textContent=draft.originality_note||'';$('draftStyle').textContent=draft.style;$('draftLyrics').textContent=draft.lyrics;$('draftTips').replaceChildren(...draft.tips.map(t=>node('li',t)));$('assistStatus').textContent='提案を確認して、入力欄へ反映してください。';
  }catch(e){if(epoch!==draftEpoch)return;notify(e.message,true);$('assistStatus').textContent='入力支援を完了できませんでした。接続状態や利用枠を確認してください。';}
  finally{button.disabled=false;button.textContent='✧ スタイル・歌詞を提案';}
});
$('applyStyle').addEventListener('click',()=>{if(!draft)return;if(draft.engine&&draft.engine!==$('engine').value){notify('提案時の音楽モデルに戻すか、選択中のモデルで提案を作り直してください。',true);return;}$('style').value=draft.style;applyDraftBpm();applyDraftDuration();$('autoAssist').checked=false;updateMode();saveDraft();notify('スタイル案を反映しました。歌詞はそのままです。');});
$('applyAll').addEventListener('click',()=>{if(!draft)return;if(draft.engine&&draft.engine!==$('engine').value){notify('提案時の音楽モデルに戻すか、選択中のモデルで提案を作り直してください。',true);return;}if($('lyrics').value.trim()&&$('lyrics').value!==draft.lyrics&&!confirm('入力済みの歌詞をこの提案に置き換えますか？'))return;$('title').value=draft.title;$('style').value=draft.style;$('lyrics').value=draft.lyrics;applyDraftBpm();applyDraftDuration();$('autoAssist').checked=false;updateMode();saveDraft();notify('タイトル・スタイル・歌詞を反映しました。確認して曲を生成してください。');});

$('songForm').addEventListener('submit',async e=>{
  e.preventDefault();if(!validateChoices())return;const button=$('generate');button.disabled=true;
  try{const job=await api('/api/songs',{...engineFields(),output_format:$('outputFormat').value,control_mode:['diffsynth-music','mulacover'].includes($('engine').value)?$('controlMode').value:'native',source_song_id:$('sourceSongId').value,derivation_mode:$('derivationMode').value,reference_strength:Number($('referenceStrength').value),title:$('title').value||'Untitled',style:$('style').value,lyrics:$('vocal').value==='instrumental'?'':$('lyrics').value,cot:isTimedEngine()?'off':$('cot').value,seed:Number($('seed').value),cfg_scale:!isTimedEngine()&&$('cfg').value?Number($('cfg').value):null,max_tokens:isTimedEngine()?9000:Number($('maxTokens').value),abc:isTimedEngine()?'':$('abc').value,auto_assist:$('autoAssist').checked,brief:$('brief').value,language:$('language').value,choices:musicChoices(),assist_model:$('aiModel').value,reference_track:$('referenceTrack').value});notify('生成を開始しました。曲は1曲ずつ処理されます。画面を閉じてもサーバーが動いていれば生成は続きます。');await refreshSongs();await showDetail(job.id);$('jobDetail').scrollIntoView({behavior:'smooth',block:'nearest'});}catch(err){notify(err.message,true);}finally{button.disabled=false;}
});

let librarySongs=[];
async function refreshSongs(){const songs=await api('/api/songs'),signature=JSON.stringify(songs);if(signature===listSignature)return;listSignature=signature;librarySongs=songs;refreshControlSources();if(typeof renderLibrary==='function')renderLibrary();}
async function showDetail(id){if(selectedJob!==id)documentSignature='';selectedJob=id;if(!$('jobDetail').open)$('jobDetail').showModal();await refreshDetail();}
async function refreshDetail(){if(!selectedJob)return;const id=selectedJob;const job=await api(`/api/songs/${id}`);if(id!==selectedJob)return;$('detailTitle').textContent=job.title;$('detailStatus').textContent=`${labels[job.status]}${job.error?' — '+job.error:''}${job.summary?` · 最大VRAM ${job.summary.peak_vram_gib} GiB（PyTorch計測）`:''}`;$('detailLog').textContent=job.log||'処理の開始を待っています。';const links=[link('生成条件 JSON ↓',`/api/songs/${id}/file/input.json`)];if(job.status==='completed'){if(job.engine!=='ace-xl-turbo'&&job.cot!=='off')links.push(link('ABC譜面 ↓',`/api/songs/${id}/file/score.abc`));links.push(link('生成結果 JSON ↓',`/api/songs/${id}/file/result.json`));}if(job.assistance){links.push(link('Codexの調整内容 ↓',`/api/songs/${id}/file/assistance.json`));links.push(link('調整前の入力 ↓',`/api/songs/${id}/file/submitted.json`));$('detailAssistance').hidden=false;$('detailAssistance').replaceChildren(node('h3','Codexのメロディー・構成提案'),node('p',job.assistance.melody_plan||''),node('p',job.assistance.explanation||''),node('p',job.assistance.reference_analysis||''),node('p',job.assistance.originality_note||''),node('p',job.input.style),...job.assistance.tips.map(t=>node('p','• '+t)));}else $('detailAssistance').hidden=true;$('detailActions').replaceChildren(...links);updateDocumentChoices(job);renderDetailLyrics(job);renderReferenceResearch($('detailResearch'),job.assistance?.reference_research);}
$('closeDetail').addEventListener('click',()=>{selectedJob=null;$('jobDetail').close();});
async function refreshStatus(){const result=await api('/api/status');$('gpuStatus').textContent=result.gpu?`${result.gpu.name.replace('NVIDIA GeForce ','')} · ${(result.gpu.used_mib/1024).toFixed(1)} / ${(result.gpu.total_mib/1024).toFixed(0)} GB`:'GPUを確認できません';const ready=result.engines?.[$('engine').value]?.ready??result.models_ready;if(!ready)notify('選択モデルを準備しています。セットアップ完了後に生成できます。');}
async function poll(){try{await Promise.all([refreshSongs(),refreshDetail(),refreshStatus()]);if(loginPending)await refreshAccount();}catch(e){$('gpuStatus').textContent='サーバーとの接続を確認中';}finally{setTimeout(poll,3000);}}
refreshAccount().then(loadModels).catch(e=>notify(e.message,true));poll();

$('instrumentalSample').addEventListener('click',()=>{
  if(($('lyrics').value.trim()||$('style').value.trim())&&!confirm('現在の入力をインストのサンプルに置き換えますか？'))return;
  fillSong({engine:'ace-xl-turbo',duration:60,title:'Glass Harbor',style:'Instrumental city pop and jazz funk, 104 BPM. Warm Rhodes electric piano carries an original lyrical theme, supported by supple syncopated bass, clean muted rhythm guitar and tight live drums. Restrained brass answers the piano phrases. A short groove intro opens into the main theme, a contrasting bridge gives space to guitar, and the piano theme returns with gentle variation before a resolved ending. Warm analog texture, clear stereo image, no vocals, no humming, no speech.',lyrics:'',choices:{genre:'citypop',vocal:'instrumental',bpm:104,mood:'calm',melody:'catchy'},auto_assist:false,seed:831015,abc:'',cfg_scale:null});
  $('referenceTrack').value='';$('brief').value='港の夜景が浮かぶ、ピアノが主旋律のシティポップ・インスト。オリジナルのテーマを発展させる。';saveDraft();notify('1分のインストを入力しました。「曲を生成」で試せます。Codexの自動支援も利用できます。');
});

$('compactLibrary').addEventListener('click',async()=>{const button=$('compactLibrary');button.disabled=true;try{const songs=(await api('/api/songs')).filter(j=>j.status==='completed'&&j.audio_format!=='m4a');let saved=0;for(let i=0;i<songs.length;i++){notify(`M4Aに整理中 ${i+1}/${songs.length}曲`);const result=await api(`/api/songs/${songs[i].id}/storage`,{format:'m4a'});saved+=result.saved_bytes;}await refreshSongs();notify(`M4Aへの整理が完了しました。約${(saved/1024/1024).toFixed(1)}MB削減。`);}catch(e){notify(e.message,true);}finally{button.disabled=false;}});

async function startDerivative(id,mode,keepEdits=false){const epoch=draftEpoch;const edits=keepEdits?{title:$('title').value,style:$('style').value,brief:$('brief').value}:{};try{const d=await api(`/api/songs/${id}`);const selected=mode||(d.engine==='ace-xl-turbo'?'cover':d.cot==='off'?'timbre':'score');const result=await api(`/api/songs/${id}/derive`,{mode:selected});if(epoch!==draftEpoch)return;fillSong({...result.input,...edits,source_title:result.source_title});showView('create');$('derivativeBox').scrollIntoView({behavior:'smooth',block:'center'});notify('元曲を引き継ぐ下書きを用意しました。「どんな曲にしたい？」に変更点を書き、曲を生成してください。');}catch(e){notify(e.message,true);}}
function updateDerivative(){const mode=$('derivationMode').value,active=!!$('sourceSongId').value&&mode!=='none';$('derivativeBox').hidden=!active;$('engine').disabled=active&&mode!=='control';$('sourceSongTitle').textContent=active?`元曲：${$('sourceTitle').value}`:'';$('referenceStrengthBox').hidden=mode!=='cover';$('duration').disabled=active&&mode==='cover';$('bpm').disabled=active&&['score','cover'].includes(mode);$('tempo').disabled=$('bpm').disabled;$('derivativeHint').textContent=mode==='score'?'元の譜面と歌詞を引き継ぎ、音色・編成・歌い方を変えます。完成音声の声や演奏が完全に同一になる保証はありません。':mode==='cover'?'元音源のメロディーと構成を足場に別テイクを生成します。長さは元音源に従います。保持の強さは再現率ではありません。':'元音源の音色やミックスの雰囲気を参照します。旋律・コード・構成は新しく生成されます。';}
$('derivationMode').addEventListener('change',()=>{const mode=$('derivationMode').value;if(mode==='none'){clearDerivative();return}if(mode==='control')return;const id=$('sourceSongId').value;startDerivative(id,mode,true);});
function clearDerivative(){$('sourceSongId').value='';$('sourceTitle').value='';$('derivationMode').value='none';$('controlMode').value='native';$('controlSource').value='';$('abc').value='';updateMode();saveDraft();}
$('clearDerivative').addEventListener('click',clearDerivative);

$('jobDetail').addEventListener('close',()=>{selectedJob=null;});

let documentJob='',documentSignature='',documentRequest=0;
function updateDocumentChoices(job){const files=[['input.json','生成条件']];if(job.status==='completed')files.push(['result.json','生成結果']);if(job.assistance)files.push(['assistance.json','Codexの調整内容'],['submitted.json','調整前の入力']);const signature=JSON.stringify([job.id,files]);if(signature===documentSignature)return;documentSignature=signature;const previous=documentJob===job.id?$('detailDocument').value:'input.json';documentJob=job.id;$('detailDocument').replaceChildren(...files.map(([value,label])=>{const o=node('option',label);o.value=value;return o;}));$('detailDocument').value=files.some(([v])=>v===previous)?previous:'input.json';loadDetailDocument();}
async function loadDetailDocument(){const id=documentJob,name=$('detailDocument').value,request=++documentRequest;$('documentStatus').textContent='読み込み中…';$('documentPreview').textContent='';try{const response=await fetch(`/api/songs/${id}/file/${name}`);if(!response.ok)throw Error('データを読み込めませんでした。選び直して再試行できます。');const data=await response.json();if(request!==documentRequest||selectedJob!==id)return;$('documentPreview').textContent=JSON.stringify(data,null,2);$('documentStatus').textContent='';}catch(e){if(request===documentRequest)$('documentStatus').textContent=e.message;}}
$('detailDocument').addEventListener('change',loadDetailDocument);

let detailLyricsSignature='';
function renderDetailLyrics(job){
  const lyrics=String(job.input?.lyrics||'').replace(/\r\n?/g,'\n');
  const signature=JSON.stringify([job.id,lyrics,job.input?.choices?.vocal]);
  if(signature===detailLyricsSignature)return;
  detailLyricsSignature=signature;
  const body=$('detailLyricsBody');
  body.replaceChildren();
  if(!lyrics.replace(/\[[^\]\n]*\]/g,'').trim()){
    body.append(node('p',job.input?.choices?.vocal==='instrumental'||/\[instrumental\]/i.test(lyrics)?'インストゥルメンタルのため、歌詞はありません。':'歌詞はまだ登録されていません。','lyrics-empty'));
    return;
  }
  let stanza=[];
  function flush(){if(stanza.length){body.append(node('p',stanza.join('\n'),'lyrics-stanza'));stanza=[];}}
  for(const line of lyrics.split('\n')){
    const section=line.trim().match(/^\[([^\]]+)\]$/);
    if(section){flush();body.append(node('h4',section[1].toLowerCase()==='instrumental'?'間奏 · Instrumental':section[1],'lyrics-section'));}
    else if(!line.trim())flush();
    else stanza.push(line);
  }
  flush();
}

function captureDraftState(){return {values:Object.fromEntries(draftFields.map(k=>[k,$(k).value])),autoAssist:$('autoAssist').checked,preserve:$('preserve').checked,proposal:draft};}
function restoreDraftState(state){for(const [k,value] of Object.entries(state.values))$(k).value=value;$('autoAssist').checked=state.autoAssist;$('preserve').checked=state.preserve;draft=state.proposal;$('draft').hidden=!draft;updateMode();saveDraft();}
$('resetDraft').addEventListener('click',()=>{resetUndo=captureDraftState();draftEpoch++;restoreDraftState({values:emptyDraft,autoAssist:true,preserve:true,proposal:null});$('undoResetDraft').hidden=false;$('assistStatus').textContent='新しい入力から提案を作れます。';notify('入力と保存済みの下書きをリセットしました。生成済みの曲は残っています。');});
$('undoResetDraft').addEventListener('click',()=>{if(!resetUndo)return;draftEpoch++;restoreDraftState(resetUndo);resetUndo=null;$('undoResetDraft').hidden=true;notify('リセット前の入力を戻しました。');});
for(const k of draftFields)$(k).addEventListener('input',()=>{resetUndo=null;$('undoResetDraft').hidden=true;});

function renderReferenceResearch(container,research){
  const signature=JSON.stringify(research||null);if(container.dataset.signature===signature)return;
  container.dataset.signature=signature;container.hidden=!research;container.replaceChildren();if(!research)return;
  const searched=research.mode!=='knowledge';
  container.append(node('h3',searched?'参考にした音楽の調査':'参考にした音楽の特徴'),node('p',searched?'Web検索を使用':'既存知識で提案（Web検索なし）','small'),node('p',research.decision_reason||''),node('p',research.subject),node('h4','参考にした時期・作品'),node('p',research.scope),node('h4',searched?'出典に基づく特徴':'既知の音楽的な特徴'),node('p',research.musical_features));
  if(research.inference)container.append(node('h4','今回の曲への解釈・提案'),node('p',research.inference));
  if(research.uncertainty)container.append(node('h4','確認できなかったこと'),node('p',research.uncertainty));
  if(searched)container.append(node('h4','出典'));const list=node('ul');
  for(const source of research.sources||[]){const item=node('li');try{const url=new URL(source.url);if(!['http:','https:'].includes(url.protocol))continue;const a=link(source.title,url.href);a.target='_blank';a.rel='noopener noreferrer';item.append(a,node('p',source.findings));list.append(item);}catch{}}
  container.append(list,node('p',`${searched?'Web調査':'特徴の整理'} · ${new Date(research.searched_at||research.evaluated_at).toLocaleString('ja-JP')}`,'small'));
}

function applyDraftDuration(){/* Keep the user's automatic mode; final duration is resolved at generation. */}

function applyDraftBpm(){if(!$('bpm').disabled&&!$('bpm').value&&Number.isInteger(draft?.bpm))$('bpm').value=String(draft.bpm);}

function refreshControlSources(){const chosen=$('sourceSongId').value;const options=[new Option('元曲を選択','')];for(const j of librarySongs)if(j.status==='completed'&&j.audio_url)options.push(new Option(j.title,j.id));$('controlSource').replaceChildren(...options);$('controlSource').value=chosen;}
function updateControlModels(){const engine=$('engine').value,active=['diffsynth-music','mulacover'].includes(engine),mula=engine==='mulacover';$('controlModels').hidden=!active;const autoOption=$('duration').querySelector('option[value="auto"]');if(autoOption)autoOption.disabled=mula;if(!active){if($('derivationMode').value==='control'){$('sourceSongId').value='';$('sourceTitle').value='';$('derivationMode').value='none';}return;}
$('controlMode').disabled=mula;if(mula)$('controlMode').value='reference';const sourceNeeded=mula||!['native','beats'].includes($('controlMode').value);$('controlSource').disabled=!sourceNeeded;$('controlSource').required=sourceNeeded;if(!sourceNeeded){$('sourceSongId').value='';$('sourceTitle').value='';$('derivationMode').value='none';}else if($('sourceSongId').value)$('derivationMode').value='control';$('controlSource').value=$('sourceSongId').value;
if(mula&&$('duration').value==='auto')$('duration').value='120';const automatic=$('duration').querySelector('option[value="auto"]');if(automatic)automatic.disabled=mula;
$('controlModelHint').textContent=mula?'MuLaCoverは完成曲をメロディー・コードへ解析してカバーを作ります。長さは生成上限です。公式の重み・生成物は非商用条件です。':'元曲はライブラリの完成曲から選択。通常・ビート制御は元曲不要です。音声制御では指定した長さまでを参照します。';}
function finishControlHints(){const e=$('engine').value;if(!['diffsynth-music','mulacover'].includes(e))return;$('engineHint').textContent=e==='mulacover'?'MuLaCover · 参照音声から新しい編成・歌詞のカバーを作成。':'DiffSynth Music · 通常生成と音声条件による制御。';$('tempoHint').textContent=e==='mulacover'?'BPMは元音源を解析する際の指定値です。出力テンポの保証ではありません。':'BPMは数値条件へ渡します。ビート制御では指定BPMのクリック音を条件に使います。';$('aceSettingsHint').hidden=true;$('instrumentalHint').textContent='歌なしを指定します。モデルによって声が混ざる可能性があります。';$('modelLanguageHint').textContent='専用ガイドに沿ってCodexが入力を整理します。';$('guideLink').href=e==='mulacover'?'https://github.com/HeartMuLa/MuLaCover/blob/main/examples/cover_song_generation.md':'https://github.com/modelscope/DiffSynth-Studio/tree/main/examples/diffsynth_music';$('guideLink').textContent='公式の生成ガイド・利用条件 ↗';}
$('controlMode').addEventListener('change',()=>{updateMode();saveDraft();});
$('controlSource').addEventListener('change',()=>{const id=$('controlSource').value;$('sourceSongId').value=id;$('sourceTitle').value=$('controlSource').selectedOptions[0]?.textContent||'';$('derivationMode').value=id?'control':'none';updateMode();saveDraft();});
