/* Run with NODE_PATH pointing to a Playwright installation. No LMS services required. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {createHash}=require('node:crypto');

(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 try {
 const page=await browser.newPage({viewport:{width:800,height:600}});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 const vtt='WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nSave the completed file.\n\n00:00:03.000 --> 00:00:05.000\nUpload into the PhillipX system.\n';
 const fingerprint=createHash('sha256').update(vtt).digest('hex');
 const metadata={version:1,fingerprint,vtt_sha256:fingerprint,duration:10,cue_count:2,video_size:1234,video_mtime:1700000000};
 let invalid=false;
 await page.route('http://localhost/**',async route=>{
  const url=new URL(route.request().url());
  if(url.pathname==='/test')return route.fulfill({contentType:'text/html',body:'<div id="host" style="width:100%;height:450px;border-radius:16px;overflow:hidden"></div>'});
  if(url.pathname.endsWith('.captions.json'))return route.fulfill({contentType:'application/json',body:JSON.stringify({...metadata,...(invalid?{video_size:999}:{})})});
  if(url.pathname.endsWith('.vtt'))return route.fulfill({contentType:'text/vtt',body:vtt});
  return route.fulfill({headers:{'Content-Length':'1234','Last-Modified':new Date(1700000000000).toUTCString()},body:''});
 });
 await page.goto('http://localhost/test');
 await page.addScriptTag({path:path.resolve(__dirname,'../web/caption-player.js')});
 await page.evaluate(()=>{
  const video=document.createElement('video');Object.defineProperty(video,'duration',{get:()=>10});
  window.heights=[];window.seekRequests=[];
  const root=LmsCaptionPlayer.create(video,h=>heights.push(h),t=>{seekRequests.push(t);return Math.min(t,1);});
  document.getElementById('host').append(root);window.player=root;window.video=video;root.loadCaptions('/lesson.mp4');
 });
 await page.waitForFunction(()=>!document.querySelector('.lms-cc').disabled);
 assert.equal(await page.locator('.lms-captions').isVisible(),false,'default CC off');
 await page.getByRole('button',{name:'Turn captions on',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('.lms-captions').textContent==='Save the completed file.');
 await page.getByRole('button',{name:'More video options'}).click();
 await page.getByRole('button',{name:'Caption settings'}).click();
 for(const [name, pixels] of [['Small','14px'],['Medium','16px']]){
  await page.getByRole('button',{name:name+' caption font'}).click();
  assert.equal(await page.locator('.lms-captions').evaluate(el=>getComputedStyle(el).fontSize),pixels);
 }
 await page.getByRole('button',{name:'Large caption font'}).click();
 assert.equal(await page.locator('.lms-captions').evaluate(el=>getComputedStyle(el).fontSize),'20px');
 await page.getByRole('checkbox',{name:'Enable captions'}).uncheck();
 assert.equal(await page.locator('.lms-captions').isVisible(),false);
 await page.getByRole('checkbox',{name:'Enable captions'}).check();
 await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'Enter fullscreen'}).click();
 await page.waitForFunction(()=>document.fullscreenElement===player);
 assert.equal(await page.locator('.lms-captions').isVisible(),true,'fullscreen keeps captions');
 await page.getByRole('button',{name:'Exit fullscreen'}).click();
 await page.waitForFunction(()=>!document.fullscreenElement);
 await page.locator('.lms-seek').fill('8');
 await page.evaluate(()=>document.querySelector('.lms-seek').dispatchEvent(new Event('input')));
 assert.equal(await page.evaluate(()=>video.currentTime),1,'forward seek is constrained');
 await page.evaluate(()=>{video.currentTime=2.5;video.dispatchEvent(new Event('timeupdate'));});
 assert.equal(await page.locator('.lms-captions').textContent(),'','silent gap');
 await page.evaluate(()=>{video.currentTime=3;video.dispatchEvent(new Event('timeupdate'));});
 assert.equal(await page.locator('.lms-captions').textContent(),'Upload into the PhillipX system.');
 await page.setViewportSize({width:390,height:500});
 await page.getByRole('button',{name:'More video options'}).click();
 await page.getByRole('button',{name:'Caption settings'}).click();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'mobile no horizontal overflow');
 if(process.env.PLAYER_SCREENSHOT)await page.screenshot({path:process.env.PLAYER_SCREENSHOT});
 invalid=true;await page.evaluate(()=>player.loadCaptions('/stale.mp4'));
 assert.equal(await page.locator('.lms-cc').isDisabled(),true,'stale captions unavailable');
 assert.equal(await page.locator('.lms-captions').isVisible(),false,'stale captions do not display');
 assert.deepEqual(errors,[]);
 await page.evaluate(()=>player.disposePlayer());
 console.log('PASS: caption enable/disable, sizes, seeking guard, silence, mobile, stale assets, cleanup');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
