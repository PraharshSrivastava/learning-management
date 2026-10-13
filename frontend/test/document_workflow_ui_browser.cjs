/* Compiled Trainer UI acceptance with synthetic API fixtures; no live LMS calls. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require(require.resolve('playwright', {paths: [process.env.NODE_PATH || 'C:/Users/LPUSER/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules']}));
const root = path.resolve(__dirname, '../../tmp/document-builder-web');
const drafts = new Map();
const operations = new Map();
let nextId = 0;
const metadata = {courseName:'',courseDescription:'',courseObjective:'',courseDifficulty:'Beginner',language:'English',targetAudience:'',courseType:'Training guide'};
const settings = {moduleCount:4,detailLevel:'standard',tone:'Clear and professional',writingFocus:'balanced',includeScenarios:true,includeBadGood:true,includeTakeaways:true,includeMistakes:true};
const modules = () => [{id:'module_a',title:'Customer needs',objective:'Listen first',included:true,sections:['Explanation'],blocks:[{id:'text_a',type:'paragraph',text:'Listen before proposing a solution.',marks:[]}],sourceReferences:[],status:'ready'}, {id:'module_b',title:'Follow-up',objective:'Confirm the next step',included:true,sections:['Practice'],blocks:[{id:'text_b',type:'paragraph',text:'Confirm the next step.',marks:[]}],sourceReferences:[],status:'ready'}];
const server = http.createServer((request,response) => {
 const pathname = decodeURIComponent(new URL(request.url,'http://localhost').pathname);
 const target = path.resolve(root, '.' + (pathname === '/' ? '/index.html' : pathname));
 if(!target.startsWith(root+path.sep) || !fs.existsSync(target)){response.writeHead(404).end();return;}
 response.setHeader('Content-Type',target.endsWith('.js')?'application/javascript':target.endsWith('.wasm')?'application/wasm':target.endsWith('.html')?'text/html':'application/octet-stream');
 response.end(fs.readFileSync(target));
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin=`http://127.0.0.1:${server.address().port}`;
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/assets/.env',route=>route.fulfill({body:`API_BASE_URL=${origin}`}));
  await page.route('**/api/**',async route=>{
   const request=route.request(), url=new URL(request.url()), parts=url.pathname.split('/').filter(Boolean);
   let result=[]; let body={};try{body=request.postDataJSON()||{};}catch(_){}
   if(url.pathname.endsWith('/session/trainer'))result={authenticated:true,local_dev_mode:false,trainer:{trainer_id:'fixture_owner',name:'Synthetic Trainer',status:'active'}};
   else if(url.pathname.endsWith('/capabilities'))result={workflowEnabled:true,languages:['English']};
   else if(url.pathname.includes('/assignment/options'))result={departments:[],designations:[],groups:[],employees:[]};
   else if(parts[1]==='document-builder' && parts[2]==='drafts') {
    const id=parts[3], suffix=parts[4];
    if(!id && request.method()==='POST') {
     const newId=`draft_${++nextId}`;result={id:newId,revision:1,content:{schemaVersion:1,entryMode:body.entryMode,metadata:{...metadata},settings:{...settings},modules:[]},approvedOutline:null,createdAt:'2026-10-13',updatedAt:'2026-10-13'};drafts.set(newId,result);
    } else if(!id) result=[...drafts.values()].map(d=>({draft_id:d.id,title:d.content.metadata.courseName,revision:d.revision}));
    else {
     const draft=drafts.get(id);
     if(request.method()==='PATCH'){draft.content=body.content;draft.revision++;draft.approvedOutline=null;result=draft;}
     else if(suffix==='sources')result=[];
     else if(suffix==='import'){draft.content.modules=modules();draft.content.metadata.courseName='Customer Service Essentials';draft.revision++;result=draft;}
     else if(suffix==='approve-outline'){draft.approvedOutline='approved';draft.revision++;result=draft;}
     else if(suffix==='operations'){
      if(request.method()==='POST'){
       const opId=`op_${operations.size+1}`;
       result={id:opId,draftId:id,request:body,status:body.task==='outline'?'proposed':'completed',result:body.task==='outline'?{modules:[{title:'Customer needs',objective:'Listen first',sections:['Explanation']},{title:'Follow-up',objective:'Confirm next step',sections:['Practice']}]}:{}};
       if(body.task==='draft'){draft.content.modules=modules();draft.revision++;}
       operations.set(opId,result);
      }else result=parts[5]?operations.get(parts[5]):[...operations.values()].filter(o=>o.draftId===id);
     }else if(suffix==='proposals'){draft.content.modules=modules().map(m=>({...m,blocks:[]}));draft.revision++;operations.get(parts[5]).status='accepted';result=draft;}
     else if(suffix==='create-course')result={course_id:`course_${id}`,trainer_id:'fixture_owner',status:'draft',course_name:draft.content.metadata.courseName,course_description:draft.content.metadata.courseDescription,course_objective:draft.content.metadata.courseObjective,course_difficulty:'Beginner',language:'English',target_audience:'New staff',created_at:'2026-10-13',modules:draft.content.modules.map((m,i)=>({module_number:i+1,title:m.title,source_text:(m.blocks||[]).map(b=>b.text||'').join('\n'),num_questions:3}))};
     else result=draft;
    }
   }
   await route.fulfill({contentType:'application/json',body:JSON.stringify(result)});
  });
  await page.goto(origin);await page.locator('flt-semantics-placeholder').waitFor({timeout:45000});
  await page.locator('flt-semantics-placeholder').evaluate(e=>e.click());
  await page.getByRole('button',{name:'Open Document Builder'}).click({timeout:30000});
  await page.getByText('What would you like to create?',{exact:true}).waitFor();
  await page.getByRole('button',{name:/Use Existing Content/}).click();
  await page.getByRole('textbox',{name:'Or paste existing content'}).fill('Module 1: Customer needs\nListen first.');
  await page.getByRole('button',{name:'Review pasted content'}).click();
  await page.getByRole('button',{name:'Review in editor first'}).waitFor();
  await page.getByRole('button',{name:'Review in editor first'}).click();
  await page.locator('[aria-label="Training document editor"]').waitFor();
  assert.match(await page.locator('[aria-label="Training document editor"]').textContent(),/Listen before/);
  await page.screenshot({path:path.resolve(__dirname,'../../docs/design/document-builder/implemented-editor-preview.png')});
  await page.getByRole('button',{name:'Saved drafts',exact:true}).click();
  await page.getByRole('button',{name:/Generate with AI/}).click();
  await page.getByRole('textbox',{name:'Course name',exact:true}).fill('Customer Service Essentials');
  await page.getByRole('textbox',{name:'Description',exact:true}).fill('Practical service training');
  await page.getByRole('textbox',{name:'Learning objective',exact:true}).fill('Listen and confirm next steps');
  await page.getByRole('textbox',{name:'Audience',exact:true}).fill('New employees');
  await page.getByRole('button',{name:'Generate outline',exact:true}).click();
  await page.getByRole('button',{name:'Use this outline',exact:true}).click();
  await page.getByRole('button',{name:'Approve outline',exact:true}).click();
  await page.getByRole('button',{name:'Write modules & open editor',exact:true}).click();
  await page.locator('[aria-label="Training document editor"]').waitFor();
  assert.match(await page.locator('[aria-label="Training document editor"]').textContent(),/Listen before/);
  assert.equal([...operations.values()].filter(o=>o.request.task==='draft').length,1);
  await page.getByRole('button',{name:'Saved drafts',exact:true}).click();
  await page.getByRole('button',{name:/Start blank/}).click();
  await page.getByRole('button',{name:'Open blank editor',exact:true}).click();
  await page.locator('[aria-label="Training document editor"]').waitFor();
  await page.locator('[aria-label="Training document editor"] [data-block-id]').first().fill('A trainer-written paragraph.');
  await page.getByRole('button',{name:'Saved drafts',exact:true}).click();
  assert.equal([...drafts.values()].at(-1).content.modules[0].blocks[0].text,'A trainer-written paragraph.');
  assert.deepEqual(errors,[]);
  console.log('Compiled Trainer UI passed: all three entry paths, source review, optional editor, approved AI outline/module generation, blank draft autosave.');
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error.message);server.close();process.exitCode=1;});
