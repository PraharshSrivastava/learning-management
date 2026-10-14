/* Compiled Trainer UI acceptance with synthetic API fixtures; no live LMS calls. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require(require.resolve('playwright', {paths: [process.env.NODE_PATH || 'C:/Users/LPUSER/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules']}));
const root = path.resolve(process.env.DOCUMENT_BUILDER_WEB_ROOT || path.join(__dirname, '../build/web'));
const drafts = new Map();
const operations = new Map();
let nextId = 0;
let workflowEnabled=true;
let handoffs=0;
let readyBlueprints=[];
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
  const errors=[];page.on('pageerror',error=>errors.push(error.message)); const enter=async(name,text)=>{const el=page.getByRole('textbox',{name:new RegExp(name.replace(/[.*+?^\$\{\}()|[\]\\]/g,'\\\$&')+'$')});await el.click();await page.waitForTimeout(200);await page.keyboard.press('Control+A');await page.waitForTimeout(100);await page.keyboard.insertText(text);await page.keyboard.press('Tab');await page.waitForTimeout(100);};
  await page.route('**/assets/.env',route=>route.fulfill({body:`API_BASE_URL=${origin}`}));
  await page.route('**/api/**',async route=>{
   const request=route.request(), url=new URL(request.url()), parts=url.pathname.split('/').filter(Boolean);
   let result=[]; let body={};try{body=request.postDataJSON()||{};}catch(_){}
   if(url.pathname.endsWith('/session/trainer'))result={authenticated:true,local_dev_mode:false,trainer:{trainer_id:'fixture_owner',name:'Synthetic Trainer',status:'active'}};
   else if(url.pathname.endsWith('/capabilities'))result={workflowEnabled,languages:['English']};
   else if(url.pathname==='/api/upload')result={document_id:'new_owned_upload',file_name:'stored-ready.pdf',message:'Uploaded'};
   else if(url.pathname==='/api/courses/generate') {
    readyBlueprints.push(body.file_name);
    result={course_id:'ready_course',trainer_id:'fixture_owner',status:'draft',course_name:'Ready customer service course',course_description:'Training',course_objective:'Listen and respond',course_difficulty:'Beginner',language:'English',target_audience:'New staff',created_at:'2026-10-14',modules:modules().map((m,i)=>({module_number:i+1,title:m.title,source_text:m.blocks[0].text,num_questions:3}))};
   }
   else if(url.pathname==='/api/files')result=[{document_id:'owned_upload',file_name:'customer-service.pdf',display_name:'Customer service training brief',file_type:'pdf',size:1200,created_at:'2026-10-14'}];
   else if(url.pathname.includes('/assignment/options'))result={departments:[],designations:[],groups:[],employees:[]};
   else if(parts[1]==='document-builder' && parts[2]==='drafts') {
    const id=parts[3], suffix=parts[4];
    if(!id && request.method()==='POST') {
     const newId=`draft_${++nextId}`;result={id:newId,revision:1,content:{schemaVersion:1,entryMode:body.entryMode,metadata:{...metadata},settings:{...settings},modules:[]},approvedOutline:null,createdAt:'2026-10-13',updatedAt:'2026-10-13'};drafts.set(newId,result);
    } else if(!id) result=[...drafts.values()].filter(d=>!d.removed).map(d=>({draft_id:d.id,title:d.content.metadata.courseName,revision:d.revision,module_count:d.content.modules.length,updated_at:d.updatedAt}));
    else {
     const draft=drafts.get(id);
     if(request.method()==='PATCH'){draft.content=body.content;draft.revision++;draft.approvedOutline=null;result=draft;}
     else if(suffix==='remove'){draft.removed=true;result={};}
     else if(suffix==='undo-remove'){draft.removed=false;result=draft;}
     else if(suffix==='sources')result=[];
     else if(suffix==='import'){draft.content.modules=modules();draft.content.metadata.courseName='Customer Service Essentials';draft.revision++;result=draft;}
     else if(suffix==='approve-outline'){draft.approvedOutline='approved';draft.revision++;result=draft;}
     else if(suffix==='operations'){
      if(request.method()==='POST'){
       const opId=`op_${operations.size+1}`;
       result={id:opId,draftId:id,request:body,status:body.task==='outline'?'proposed':'completed',result:body.task==='outline'?{modules:[{title:'Customer needs',objective:'Listen first',sections:['Explanation']},{title:'Follow-up',objective:'Confirm next step',sections:['Practice']}]}:{}};
       if(body.task==='edit') {
        const target=body.target, block=draft.content.modules.find(m=>m.id===target.moduleId).blocks.find(b=>b.id===target.blockId);
        result.status='proposed'; result.result={originalText:Array.from(block.text).slice(target.start,target.end).join(''),replacementText:'Hear',summary:'Simplified the selected words.'};
       }
       if(body.task==='revise') {
        result.status='proposed';result.result={changes:draft.content.modules.filter(m=>body.scope==='document'?m.included!==false:m.id===body.moduleId).flatMap(m=>m.blocks.filter(b=>b.text).map(b=>({moduleId:m.id,blockId:b.id,originalText:b.text,replacementText:b.text+' Revised.'}))),summary:'Review all proposed text replacements before accepting.'};
       }
       if(body.task==='draft'){draft.content.modules=draft.content.modules.map((m,i)=>({...m,blocks:modules()[i%2].blocks.map(b=>({...b,id:'text_'+i}))}));draft.revision++;}
       if(body.task==='import'){draft.content.modules=modules();draft.content.metadata.courseName='Customer Service Essentials';draft.revision++;}
       operations.set(opId,result);
      }else result=parts[5]?operations.get(parts[5]):[...operations.values()].filter(o=>o.draftId===id);
     }else if(suffix==='proposals'){
      const op=operations.get(parts[5]);
      if(parts[6]==='reject'){op.status='rejected';result={};}
      else {
       if(op.request.task==='outline')draft.content.modules=(body.outline?.modules||modules()).map((m,i)=>({...m,id:'module_'+i,included:true,blocks:[],sourceReferences:[],status:'empty'}));
       if(op.request.task==='revise')for(const c of op.result.changes)draft.content.modules.find(m=>m.id===c.moduleId).blocks.find(b=>b.id===c.blockId).text=c.replacementText;
       if(op.request.task==='edit'){const t=op.request.target,b=draft.content.modules.find(m=>m.id===t.moduleId).blocks.find(b=>b.id===t.blockId),chars=Array.from(b.text);b.text=chars.slice(0,t.start).join('')+op.result.replacementText+chars.slice(t.end).join('');}
       draft.revision++;op.status='accepted';result=draft;
      }
     }
     else if(suffix==='create-course'){handoffs++;result={course_id:`course_${id}`,trainer_id:'fixture_owner',status:'draft',course_name:draft.content.metadata.courseName,course_description:draft.content.metadata.courseDescription,course_objective:draft.content.metadata.courseObjective,course_difficulty:'Beginner',language:'English',target_audience:'New staff',created_at:'2026-10-13',modules:draft.content.modules.map((m,i)=>({module_number:i+1,title:m.title,source_text:(m.blocks||[]).map(b=>b.text||'').join('\n'),num_questions:3}))};}
     else result=draft;
    }
   }
   await route.fulfill({contentType:'application/json',body:JSON.stringify(result)});
  });
  await page.goto(origin);await page.locator('flt-semantics-placeholder').waitFor({timeout:45000});
  await page.locator('flt-semantics-placeholder').evaluate(e=>e.click());
  await page.getByText('Create a training document',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Open Document Builder'}).count(),0);
  await page.screenshot({path:path.resolve(__dirname,'../../docs/design/document-builder/implemented-simplified-documents.png')});
  await page.getByRole('button',{name:'Create course',exact:true}).click();
  await page.waitForTimeout(1500);await page.screenshot({path:path.resolve(__dirname,'../../docs/design/document-builder/implemented-ready-document-blueprint.png')});
  assert.deepEqual(readyBlueprints,['customer-service.pdf']);
  assert.equal(drafts.size,0);
  assert.equal(operations.size,0);
  await page.reload();await page.locator('flt-semantics-placeholder').waitFor();await page.locator('flt-semantics-placeholder').evaluate(e=>e.click());await page.getByText('Create a training document',{exact:true}).waitFor();await page.waitForTimeout(300);
  await page.getByRole('button',{name:/Use existing content/}).click();
  assert.equal(drafts.size,0);

  const chooserPromise=page.waitForEvent('filechooser',{timeout:15000});
  await page.getByRole('button',{name:'Upload & open Blueprint',exact:true}).click();
  await (await chooserPromise).setFiles({name:'ready.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4 synthetic upload fixture')});
  await page.waitForTimeout(1500);await page.screenshot({path:path.resolve(__dirname,'../../docs/design/document-builder/implemented-ready-document-blueprint.png')});
  assert.deepEqual(readyBlueprints,['customer-service.pdf','stored-ready.pdf']);
  assert.equal(drafts.size,0);
  assert.equal(operations.size,0);
  await page.reload();await page.locator('flt-semantics-placeholder').waitFor();await page.locator('flt-semantics-placeholder').evaluate(e=>e.click());await page.getByText('Create a training document',{exact:true}).waitFor();await page.waitForTimeout(300);
  await page.getByRole('button',{name:/More actions for/}).click();await page.getByRole('menuitem',{name:'Edit first',exact:true}).click();
  await page.getByRole('button',{name:'Approve outline',exact:true}).waitFor();
  assert.equal([...operations.values()].at(-1).request.sourceImport.documentId,'owned_upload');
  assert.equal(readyBlueprints.length,2);
  await page.getByText('← Documents',{exact:true}).click();await page.getByText('Create a training document',{exact:true}).waitFor();await page.waitForTimeout(300);
  await page.getByRole('button',{name:/Use existing content/}).click();
  await page.getByText('Paste content instead',{exact:true}).click();
  await page.getByRole('textbox',{name:'Existing notes'}).fill('Module 1: Customer needs\nListen first.');
  await page.getByRole('button',{name:'Review outline',exact:true}).click();
  await page.getByRole('button',{name:'Approve outline',exact:true}).click();
  await page.getByRole('button',{name:'Create course',exact:true}).click();
  assert.equal(handoffs,0);
  await enter('Who is this for?','New employees');
  await enter('What should employees be able to do?','Listen and confirm next steps');
  await page.waitForTimeout(1000);
  await page.getByRole('checkbox',{name:'I approve the current outline and included module structure'}).evaluate(e=>e.click());
  await page.waitForTimeout(300);
  assert.equal([...drafts.values()].at(-1).approvedOutline,'approved');
  await page.getByRole('button',{name:'Review in editor',exact:true}).click();
  await page.locator('[aria-label="Training document editor"]').waitFor();
  assert.match(await page.locator('[aria-label="Training document editor"]').textContent(),/Listen before/);
  assert.equal(await page.getByRole('button',{name:'Suggest changes'}).count(),0);
  await page.screenshot({path:path.resolve(__dirname,'../../docs/design/document-builder/implemented-simplified-editor.png')});
  // Real DOM selection remains scoped after focus moves into the assistant.
  const editedDraft=[...drafts.values()].at(-1);
  const firstText=()=>editedDraft.content.modules[0].blocks[0].text;
  await page.locator('[aria-label="Training document editor"] [data-block-id]').first().evaluate(e=>{
   const text=e.firstChild;const range=document.createRange();range.setStart(text,0);range.setEnd(text,6);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);e.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));
  });
  await page.getByRole('button',{name:'AI assistant',exact:true}).click();
  await enter('What would you like to improve?','Simplify these selected words.');
  await page.getByRole('button',{name:'Generate suggestion',exact:true}).click();
  await page.getByRole('dialog').waitFor();
  assert.equal([...operations.values()].at(-1).request.task,'edit');
  assert.equal([...operations.values()].at(-1).request.target.end,6);
  assert.equal(firstText(),'Listen before proposing a solution.');
  await page.waitForTimeout(400);await page.screenshot({path:path.resolve(__dirname,'../../docs/design/document-builder/implemented-ai-assistant-review.png')});
  await page.setViewportSize({width:390,height:850});await page.waitForTimeout(400);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false);
  assert.equal(await page.getByRole('button',{name:'Apply 1 change',exact:true}).isVisible(),true);
  await page.screenshot({path:path.resolve(__dirname,'../../docs/design/document-builder/implemented-ai-assistant-review-mobile.png')});
  await page.setViewportSize({width:1440,height:1000});await page.waitForTimeout(400);
  await page.getByRole('button',{name:'Apply 1 change',exact:true}).click();
  await page.waitForTimeout(300);
  assert.equal(firstText(),'Hear before proposing a solution.');
  assert.equal(editedDraft.content.modules[1].blocks[0].text,'Confirm the next step.');
  await page.getByRole('button',{name:'Apply suggestions to'}).evaluate(e=>e.click());await page.waitForTimeout(400);
  await page.getByRole('menuitem',{name:'Current module',exact:true}).click();
  await page.getByRole('button',{name:'Generate suggestion',exact:true}).click();
  await page.getByRole('dialog').waitFor();
  assert.equal([...operations.values()].at(-1).request.scope,'module');
  await page.getByRole('button',{name:'Discard suggestions',exact:true}).click();
  assert.equal(firstText(),'Hear before proposing a solution.');
  await page.getByRole('button',{name:'Apply suggestions to'}).evaluate(e=>e.click());await page.waitForTimeout(400);
  await page.getByRole('menuitem',{name:'Whole document',exact:true}).click();
  await page.getByRole('button',{name:'Generate suggestion',exact:true}).click();
  await page.getByRole('button',{name:'Cancel',exact:true}).click();
  assert.notEqual([...operations.values()].at(-1).request.scope,'document');
  await page.getByRole('button',{name:'Generate suggestion',exact:true}).click();
  await page.getByRole('button',{name:'Prepare suggestions',exact:true}).click();
  await page.getByRole('dialog').waitFor();
  assert.equal([...operations.values()].at(-1).request.scope,'document');
  await page.getByRole('button',{name:'Apply 2 changes',exact:true}).click();
  await page.waitForTimeout(300);
  assert.equal(firstText(),'Hear before proposing a solution. Revised.');
  assert.equal(editedDraft.content.modules[1].blocks[0].text,'Confirm the next step. Revised.');
  await page.screenshot({path:path.resolve(__dirname,'../../docs/design/document-builder/implemented-ai-assistant-controls.png')});
  await page.getByText('← Documents',{exact:true}).click();await page.getByText('Create a training document',{exact:true}).waitFor();await page.waitForTimeout(300);
  await page.getByRole('button',{name:/Generate with AI/}).click();
  await enter('Topic or title','Customer Service Essentials');
  await enter('Who is this for?','New employees');
  await enter('What should employees be able to do?','Listen and confirm next steps');  await page.waitForTimeout(1000);
  assert.equal(await page.getByRole('textbox',{name:'Description',exact:true}).count(),0);
  await page.screenshot({path:path.resolve(__dirname,'../../docs/design/document-builder/implemented-simplified-ai-setup.png')});
  await page.getByRole('button',{name:'Generate outline',exact:true}).evaluate(e=>e.click()); await page.waitForTimeout(1800);
  await enter('Module 1 title','Reviewed customer needs');
  await page.getByRole('button',{name:'Approve & generate document',exact:true}).click();
  await page.locator('[aria-label="Training document editor"]').waitFor();
  assert.equal([...drafts.values()].at(-1).content.modules[0].title,'Reviewed customer needs');
  assert.match(await page.locator('[aria-label="Training document editor"]').textContent(),/Listen before/);
  assert.equal([...operations.values()].filter(o=>o.request.task==='draft').length,1);
  await page.getByText('← Documents',{exact:true}).click();await page.getByText('Create a training document',{exact:true}).waitFor();await page.waitForTimeout(300);
  await page.getByRole('button',{name:/Start blank/}).evaluate(e=>e.click());await page.waitForTimeout(500);
  await enter('Topic or title','Trainer guide');
  assert.equal(await page.getByRole('textbox').count(),1);
  await page.getByRole('button',{name:'Open editor',exact:true}).click();
  await page.locator('[aria-label="Training document editor"]').waitFor();
  await page.locator('[aria-label="Training document editor"] [data-block-id]').first().fill('A trainer-written paragraph.');
  await page.getByText('← Documents',{exact:true}).click();await page.getByText('Create a training document',{exact:true}).waitFor();await page.waitForTimeout(300);
  assert.equal([...drafts.values()].at(-1).content.modules[0].blocks[0].text,'A trainer-written paragraph.');
  await enter('Search documents','no-match');
  await page.getByRole('group',{name:/Your documents No documents match your search/}).waitFor();
  await enter('Search documents','');
  const beforeRemove=[...drafts.values()].filter(d=>!d.removed).length;
  await page.getByRole('button',{name:'Remove',exact:true}).first().click();
  await page.getByRole('button',{name:'Cancel',exact:true}).click();
  assert.equal([...drafts.values()].filter(d=>!d.removed).length,beforeRemove);
  await page.getByRole('button',{name:'Remove',exact:true}).first().click();
  await page.getByRole('button',{name:'Remove draft',exact:true}).click();
  await page.getByRole('button',{name:'Undo',exact:true}).waitFor();
  assert.equal([...drafts.values()].filter(d=>!d.removed).length,beforeRemove-1);
  await page.getByRole('button',{name:'Undo',exact:true}).click();
  await page.waitForTimeout(400);
  assert.equal([...drafts.values()].filter(d=>!d.removed).length,beforeRemove);
  await page.screenshot({path:path.resolve(__dirname,'../../docs/design/document-builder/implemented-option-a-documents.png')});
  for(const width of [1024,736,390]) {
    await page.setViewportSize({width,height:1000});await page.waitForTimeout(300);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false);
  }
  await page.setViewportSize({width:1440,height:1000});
  workflowEnabled=false;
  await page.reload();
  await page.locator('flt-semantics-placeholder').evaluate(e=>e.click()).catch(()=>{});
  await page.getByRole('button',{name:'Open Document Builder',exact:true}).waitFor();
  assert.deepEqual(errors,[]);
  console.log('Compiled Trainer UI passed: ready document goes directly to legacy Blueprint without builder draft/import; optional editing, AI and blank flows preserved.');
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error.stack);server.close();process.exitCode=1;});
