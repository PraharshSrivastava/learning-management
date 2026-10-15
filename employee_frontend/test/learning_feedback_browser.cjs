/* Real compiled Employee playback; controlled API fixtures, no live writes. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const {chromium} = require(require.resolve('playwright', {paths: [process.env.NODE_PATH || 'C:/Users/LPUSER/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules']}));
const root = path.resolve(__dirname, '../build/web');
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  const file = path.resolve(root, '.' + (pathname === '/' ? '/index.html' : pathname));
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file)) return res.writeHead(404).end();
  res.setHeader('Content-Type', file.endsWith('.js') ? 'application/javascript' : file.endsWith('.wasm') ? 'application/wasm' : file.endsWith('.html') ? 'text/html' : 'application/octet-stream');
  res.end(fs.readFileSync(file));
});
const completed = {video_watched: true, quiz_passed: true, quiz_score: 1, selected_answers: {'0':'A','1':'A','2':'B'}};
const questions = () => [0,1,2].map(i => ({question_id:`q${i}`,question:`Service question ${i+1}`,options:['Listen carefully','Confirm next steps','Escalate appropriately','Ignore concern']}));
function makeCourse() {
  return {course_id:'fixture',course_name:'Customer service review',assignment_status:'started',
    course_description:'Controlled acceptance fixture',
    module_progress:{'1':{...completed},'2':{...completed},'3':{video_watched:true}},
    modules:[1,2,3,4].map(n => ({module_number:n,title:`Lesson ${n}`,video_path:'',quiz:questions()}))};
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];
    page.on('pageerror', error => errors.push(error.message));
    let employeeSocket;
    await page.routeWebSocket('**/api/me/courses/ws**', socket => {employeeSocket=socket;});
    let course = makeCourse(), submissions = [], failFetch = false;
    await page.route('**/assets/.env', r => r.fulfill({body:`API_BASE_URL=${origin}`}));
    await page.route('**/api/**', async route => {
      const req = route.request(), url = new URL(req.url());
      let result = {};
      if (url.pathname.endsWith('/session/employee')) result = {authenticated:true,employee:{employee_id:'fixture_employee',name:'Test Employee',status:'active'}};
      else if (url.pathname === '/api/me/courses') {
        if (failFetch) return route.fulfill({status:503,contentType:'application/json',body:'{}'});
        result = [course];
      } else if (/\/modules\/\d+$/.test(url.pathname) && req.method() === 'PUT') {
        const n = Number(url.pathname.split('/').pop()), body = req.postDataJSON();
        assert.ok(body.selected_answers, 'Opening course must not write progress');
        const answers = body.selected_answers;
        submissions.push(answers);
        const keys = {'0':'A','1':'A','2':'B'};
        const count = Object.keys(keys).filter(k => keys[k] === answers[k]).length;
        const passed = count >= 2;
        result = {quiz_passed:passed,quiz_score:count/3,correct_count:count,total_questions:3,pass_mark:2/3,answer_results:Object.fromEntries(Object.keys(keys).map(k=>[k,keys[k]===answers[k]]))};
        course.module_progress[n] = {video_watched:passed,quiz_passed:passed,quiz_score:count/3,selected_answers:passed?answers:null};
        if (passed) course.modules[n-1].quiz.forEach((q,i) => {q.answer_correct=result.answer_results[i];});
      } else if (url.pathname.includes('/lms/me')) result = {performance_views:[]};
      else if (url.pathname.includes('/employees')) result = [];
      await route.fulfill({contentType:'application/json',body:JSON.stringify(result)});
    });
    const open = async () => {
      await page.goto(`${origin}/?view=course&course_id=fixture`);
      await page.locator('flt-semantics-placeholder').evaluate(e => e.click());
    };
    await open();
    await page.getByRole('button',{name:'Submit Quiz',exact:true}).waitFor();
    assert.equal(submissions.length,0);
    assert.ok((await page.locator('body').innerText()).includes('Lesson 3'));
    const radios = page.getByRole('radio');
    await radios.nth(0).click(); await radios.nth(4).click(); await radios.nth(8).click();
    await page.getByRole('button',{name:'Submit Quiz',exact:true}).click();
    await page.waitForTimeout(1000);
    await page.getByText('2 of 3 correct (66.67%)',{exact:true}).waitFor();
    await page.screenshot({path:path.join(__dirname,'../build/quiz-review-66.png')});
    assert.match(await page.locator('body').innerText(), /Incorrect/);
    assert.equal(await page.getByText(/Correct answer:/).count(),0);
    assert.equal(await page.getByRole('dialog').count(),0,'Results stay on the quiz page');
    assert.equal(submissions.length,1);
    employeeSocket?.send(JSON.stringify([course]));
    await page.waitForTimeout(1000);
    await page.getByText('2 of 3 correct (66.67%)',{exact:true}).waitFor();
    await page.screenshot({path:path.join(__dirname,'../build/quiz-review-66.png')});
    await page.getByRole('button',{name:'Continue to next module'}).click();
    await page.getByText('Lesson 4',{exact:true}).first().waitFor();
    console.log('PASS: resumes Module 3, displays 2/3 review, advances only on Continue');
    await page.getByRole('button',{name:/MODULE 3/}).click();
    await page.getByRole('radio').nth(8).waitFor();
    assert.equal(await page.getByRole('radio').nth(8).getAttribute('aria-checked'),'true');
    assert.equal(await page.getByRole('radio').nth(9).getAttribute('aria-checked'),'false');
    employeeSocket?.send(JSON.stringify([course]));
    await page.waitForTimeout(500);
    assert.equal(await page.getByRole('radio').nth(8).getAttribute('aria-checked'),'true');
    console.log('PASS: revisited passed quiz retains the actual wrong selection across refresh');

    await open();
    await page.getByText('Lesson 4',{exact:true}).first().waitFor();
    assert.equal(submissions.length,1);
    console.log('PASS: reload resumes next incomplete module without progress writes');

    course = makeCourse();
    await open();
    await page.getByRole('button',{name:'Submit Quiz',exact:true}).waitFor();
    await page.getByRole('radio').nth(0).click(); await page.getByRole('radio').nth(4).click(); await page.getByRole('radio').nth(9).click();
    await page.getByRole('button',{name:'Submit Quiz',exact:true}).click();
    await page.getByText('3 of 3 correct (100.00%)',{exact:true}).waitFor();
    await page.setViewportSize({width:420,height:900});
    await page.screenshot({path:path.join(__dirname,'../build/quiz-review-100-mobile.png')});
    console.log('PASS: 3/3 displays 100%, responsive review');

    course = makeCourse();
    course.modules[2].quiz[2].options[1] = course.modules[2].quiz[2].options[0];
    await open();
    await page.getByRole('button',{name:'Submit Quiz',exact:true}).waitFor();
    await page.getByRole('radio').nth(0).click(); await page.getByRole('radio').nth(4).click(); await page.getByRole('radio').nth(9).click();
    await page.getByRole('button',{name:'Submit Quiz',exact:true}).click();
    await page.getByText('3 of 3 correct (100.00%)',{exact:true}).waitFor();
    assert.equal(submissions.at(-1)['2'],'B');
    console.log('PASS: duplicate option text preserves the selected option key');

    course = makeCourse();
    await open();
    await page.getByRole('button',{name:'Submit Quiz',exact:true}).waitFor();
    await page.getByRole('radio').nth(1).click(); await page.getByRole('radio').nth(5).click(); await page.getByRole('radio').nth(10).click();
    await page.getByRole('button',{name:'Submit Quiz',exact:true}).click();
    await page.getByText('0 of 3 correct (0.00%)',{exact:true}).waitFor();
    assert.equal(await page.getByText(/Correct answer:/).count(),0);
    assert.equal((await page.locator('body').innerText()).match(/Incorrect/g)?.length,3);
    await page.getByRole('button',{name:'Rewatch lesson',exact:true}).click();
    assert.equal(await page.getByRole('button',{name:'Submit Quiz',exact:true}).count(),0);
    console.log('PASS: failed quiz displays results and requires rewatch');

    course.modules.forEach(m => course.module_progress[m.module_number] = {...completed});
    await open();
    await page.getByRole('button',{name:'Review course',exact:true}).waitFor();
    await page.getByRole('button',{name:'Review course',exact:true}).click();
    await page.getByText('Lesson 1',{exact:true}).first().waitFor();
    console.log('PASS: fully complete course offers explicit review');

    await page.setViewportSize({width:1440,height:1000});
    await page.getByRole('button',{name:'Back to dashboard',exact:true}).click();
    await page.getByRole('button',{name:'Review',exact:true}).first().waitFor();
    failFetch = true;
    await page.getByRole('button',{name:'Review',exact:true}).first().click();
    await page.getByRole('button',{name:'Retry',exact:true}).waitFor();
    console.log('PASS: failed refresh requires retry instead of opening Module 1');
    assert.deepEqual(errors,[],'Compiled Employee app must not produce uncaught errors');
  } finally {
    await browser.close();
    server.close();
  }
})().catch(error => {console.error(error);process.exitCode=1;});
