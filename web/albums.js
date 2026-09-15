const albumLabels={planning:'Codexがアルバムを構成中',generating:'楽曲を生成中',completed:'全曲完成',paused:'一時停止',failed:'確認が必要'};
let albumSignature='';
const albumFields=['albumBrief','albumEngine','albumCount','albumVocal','albumDuration','albumLanguage','albumFormat'];
try{const saved=JSON.parse(localStorage.getItem('album-draft')||'null');if(saved)for(const k of albumFields)if(saved[k]!==undefined)$(k).value=saved[k];}catch{}
function saveAlbumDraft(){try{localStorage.setItem('album-draft',JSON.stringify(Object.fromEntries(albumFields.map(k=>[k,$(k).value]))));}catch{}}
for(const k of albumFields)$(k).addEventListener('input',saveAlbumDraft);
$('cityAlbum').addEventListener('click',()=>{$('albumBrief').value='80年代シティポップの10曲アルバム。洗練されたバンド演奏、都会で暮らす別々の人物や生活の具体的な出来事を描く日本語のオリジナル曲。ダンス曲、ミドル、バラードなどの起伏。似た題名や歌詞、同じ楽器編成が続かないように。';$('albumEngine').value='yue2';$('albumVocal').value='vocal';$('albumCount').value='10';$('albumDuration').value='auto';$('albumLanguage').value='日本語';saveAlbumDraft();});
$('raceAlbum').addEventListener('click',()=>{$('albumBrief').value='架空のレースゲームのBGM集10曲。R4が好き。90年代末の洗練されたジャズ、ハウス、アシッドジャズ、ドラムンベース、ブレイクビーツの幅広い質感を参考に、既存メロディーや曲名・歌詞を再現しない独自のゲーム世界。タイトル画面、ガレージ、街、海沿い、雨、夜間コース、決勝、リプレイ、エンディングなど役割に変化を。インストと歌声ありが混ざる構成。';$('albumEngine').value='ace-xl-turbo';$('albumVocal').value='mixed';$('albumCount').value='10';$('albumDuration').value='auto';$('albumLanguage').value='English';saveAlbumDraft();});
$('albumForm').addEventListener('submit',async e=>{e.preventDefault();$('makeAlbum').disabled=true;try{await api('/api/albums',{brief:$('albumBrief').value,engine:$('albumEngine').value,track_count:Number($('albumCount').value),duration:$('albumDuration').value==='auto'?180:Number($('albumDuration').value),duration_mode:$('albumDuration').value==='auto'?'auto':'fixed',vocal_mode:$('albumVocal').value,language:$('albumLanguage').value,output_format:$('albumFormat').value,generate_cover:$('albumCover').checked,model:$('aiModel').value});notify('アルバムの構成を開始しました。アルバム一覧で進行を確認できます。');await refreshAlbums();showView('albums');}catch(e){notify(e.message,true);}finally{$('makeAlbum').disabled=false;}});
function albumAction(label,path){const b=node('button',label);b.addEventListener('click',async()=>{b.disabled=true;try{await api(path,{});await refreshAlbums();}catch(e){notify(e.message,true);}finally{b.disabled=false;}});return b;}
async function refreshAlbums(){const albums=await api('/api/albums');syncAlbumPlaylist(albums);const signature=JSON.stringify(albums);if(signature===albumSignature)return;albumSignature=signature;libraryAlbums=albums;renderLibrary();}
async function pollAlbums(){try{await refreshAlbums();}catch{}finally{setTimeout(pollAlbums,4000);}}pollAlbums();

function updateAlbumEngine(){const stable=$('albumEngine').value==='stable-audio-3-medium';$('albumVocal').disabled=stable;$('albumLanguage').disabled=stable;if(stable)$('albumVocal').value='instrumental';}
$('albumEngine').addEventListener('change',()=>{updateAlbumEngine();saveAlbumDraft();});updateAlbumEngine();

for(const id of ['cityAlbum','raceAlbum'])$(id).addEventListener('click',()=>{updateAlbumEngine();saveAlbumDraft();});
