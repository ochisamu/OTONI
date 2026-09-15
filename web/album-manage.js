$('albumManageClose').addEventListener('click',()=>$('albumManage').close());
function manageField(form,label,value,kind='input'){
 const id=`manage-${form.children.length}`;const l=node('label',label);l.htmlFor=id;const input=document.createElement(kind);input.id=id;input.value=value||'';form.append(l,input);return input;
}
function manageAlbum(album,mode){
 const body=$('albumManageBody');body.replaceChildren();$('albumManageStatus').textContent='';
 $('albumManageTitle').textContent={rename:'アルバム名を変更',cover:'ジャケットを再生成',video:'動画・YouTube投稿'}[mode];
 const form=document.createElement('form');body.append(form);
 const run=async(button,path,data,done)=>{button.disabled=true;$('albumManageStatus').textContent='処理しています…';try{await api(path,data);await refreshAlbums();$('albumManageStatus').textContent=done;}catch(e){$('albumManageStatus').textContent=e.message;}finally{button.disabled=false;}};
 if(mode==='rename'){
  const title=manageField(form,'アルバム名',album.title);title.required=true;title.maxLength=120;
  form.append(node('p','画像に描かれた文字は、ジャケットを再生成すると変更できます。','small'));
  const save=node('button','名前を保存','primary');save.type='submit';form.append(save);
  form.onsubmit=e=>{e.preventDefault();run(save,`/api/albums/${album.id}/rename`,{title:title.value},'名前を変更しました。');};
 }else if(mode==='cover'){
  form.append(artwork(album,'manage-art'),node('p','完成するまで現在の画像を表示します。Codexの画像生成を使用します。','small'));
  const direction=manageField(form,'変更したい雰囲気（任意）',album.cover_direction,'textarea');direction.rows=3;direction.maxLength=2000;direction.placeholder='色合い、風景、構図など';
  const generate=node('button',album.cover_status==='generating'?'生成中…':'新しいジャケットを生成','primary');generate.type='submit';generate.disabled=album.cover_status==='generating';form.append(generate);
  form.onsubmit=e=>{e.preventDefault();run(generate,`/api/albums/${album.id}/cover`,{direction:direction.value},'ジャケットの生成を開始しました。完成後に切り替わります。');};
 }else{
  form.append(node('p','ジャケットと再生中の曲名・トラック番号を表示し、曲順に切り替わる動画へ。720p MP4とタイムスタンプ付き説明文を書き出します。以前の動画にも曲名を入れるには、もう一度書き出してください。','small'));
  const exportButton=action(album.video_status==='generating'?'書き出し中…':'投稿用の動画を書き出す',()=>run(exportButton,`/api/albums/${album.id}/video`,{},'書き出しを開始しました。閉じても続行します。'),'primary');exportButton.disabled=album.video_status==='generating'||album.status!=='completed'||!album.cover_file;form.append(exportButton,action('進行状況を更新',async()=>{await refreshAlbums();manageAlbum(libraryAlbums.find(a=>a.id===album.id),'video');}));
  if(album.video_error)form.append(node('p',album.video_error,'song-error'));
  if(album.video_status==='completed'){
   const links=node('div',undefined,'album-actions');links.append(link('動画をダウンロード',`/api/albums/${album.id}/video/youtube.mp4`),link('説明文をダウンロード',`/api/albums/${album.id}/video/youtube-description.txt`));form.append(links);
   const video=document.createElement('video');video.controls=true;video.preload='none';video.src=`/api/albums/${album.id}/video/youtube.mp4`;video.setAttribute('playsinline','');video.style.width='100%';video.addEventListener('play',()=>$('albumPlayer').pause());form.append(video);
  }
  const studio=link('YouTube Studioを開く ↗','https://studio.youtube.com');studio.target='_blank';studio.rel='noreferrer';form.append(studio,node('p','Studioでは、ダウンロードした動画を選び、説明文を貼り付けて公開できます。','small'));
  const section=node('section',undefined,'youtube-settings');form.append(section);loadYouTube(section,album);
 }
 if(!$('albumManage').open)$('albumManage').showModal();
}
async function loadYouTube(section,album){
 try{
  const status=await api('/api/youtube/status');section.append(node('h3','アプリから直接投稿'));
  section.append(node('p','未監査のGoogle APIプロジェクトでは投稿が非公開に制限されます。公開・限定公開にはAPI監査が必要です。','small'));
  const guide=link('接続設定の手順','/static/youtube-setup.html');guide.target='_blank';section.append(guide);
  if(location.hostname!=='localhost'){
   section.append(node('p','接続・直接投稿は、アプリを動かしているPCで http://localhost:7860 を開いて操作してください。'));return;
  }
  if(!status.configured){
   const file=manageField(section,'Google OAuth設定（JSON）','','input');file.type='file';file.accept='.json,application/json';
   file.onchange=async()=>{try{await api('/api/youtube/configure',JSON.parse(await file.files[0].text()));section.replaceChildren();await loadYouTube(section,album);}catch(e){$('albumManageStatus').textContent=e.message;}};return;
  }
  if(!status.authorized_browser){
   section.append(action('GoogleでYouTubeに接続',async()=>{try{const r=await api('/api/youtube/connect',{});location.href=r.url;}catch(e){$('albumManageStatus').textContent=e.message;}}));return;
  }
  section.append(node('p',`投稿先: ${status.channel}`));
  section.append(action('接続を解除',async()=>{try{await api('/api/youtube/disconnect',{});section.replaceChildren();loadYouTube(section,album);}catch(e){$('albumManageStatus').textContent=e.message;}}));
  const sent=album.youtube;
  if(sent?.status==='completed'){
   section.append(link('投稿した動画を開く ↗',`https://www.youtube.com/watch?v=${encodeURIComponent(sent.video_id)}`),node('p',`YouTubeの公開設定: ${{public:'公開',unlisted:'限定公開',private:'非公開'}[sent.privacy]||'確認できません'}`));return;
  }
  if(sent?.status==='uploading'){section.append(node('p',`送信中… ${sent.progress||0}%`));return;}
  if(album.video_status!=='completed'){section.append(node('p','動画を書き出すと、投稿内容を確認できます。','small'));return;}
  if(sent?.error)section.append(node('p',sent.error,'song-error'));
  const previous=sent?.options;
  const title=manageField(section,'投稿タイトル',previous?.title||album.title);title.maxLength=100;title.required=true;
  const description=manageField(section,'説明文',previous?.description??await (await fetch(`/api/albums/${album.id}/video/youtube-description.txt`)).text(),'textarea');description.rows=8;description.maxLength=5000;
  const privacy=manageField(section,'公開範囲','','select');for(const [value,label]of Object.entries({private:'非公開',unlisted:'限定公開',public:'公開'})){const o=node('option',label);o.value=value;privacy.append(o);}privacy.value=previous?.privacy||'private';
  const kids=manageField(section,'子ども向けに制作した動画ですか？','','select');for(const [value,label]of [['','選択してください'],['no','いいえ'],['yes','はい']]){const o=node('option',label);o.value=value;kids.append(o);}kids.value=previous?(previous.made_for_kids?'yes':'no'):'';
  const label=node('label','投稿先・タイトル・説明文・公開範囲を確認しました。','check');const consent=document.createElement('input');consent.type='checkbox';label.prepend(consent);section.append(label);
  section.append(node('p','AI生成音楽として「改変または合成されたコンテンツ」を申告します。','small'));
  if(previous){for(const el of [title,description,privacy,kids])el.disabled=true;}
  const submit=action(previous?'中断した投稿を再開':'確認した内容でYouTubeに投稿',async()=>{
   if(!consent.checked||!kids.value||!title.reportValidity()||!description.reportValidity()){$('albumManageStatus').textContent='投稿内容と子ども向け設定を確認してください。';return;}
   submit.disabled=true;try{await api(`/api/youtube/albums/${album.id}/publish`,{title:title.value,description:description.value,privacy:privacy.value,made_for_kids:kids.value==='yes',contains_synthetic_media:true,confirmed:true});$('albumManageStatus').textContent='YouTubeへの送信を開始しました。';await refreshAlbums();}catch(e){$('albumManageStatus').textContent=e.message;submit.disabled=false;}
  },'primary');section.append(submit);
 }catch(e){section.append(node('p',e.message,'song-error'));}
}
