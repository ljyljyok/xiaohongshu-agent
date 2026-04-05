const puppeteer = require('C:/Users/ljy/AppData/Roaming/npm/node_modules/xhs-mcp/node_modules/puppeteer-core');
const fs = require('fs');
const path = require('path');

async function publish() {
  const logFile = path.join(__dirname, '_xhs_pub.log');
  const log = (msg) => {
    const line = `[${new Date().toISOString()}] ${msg}`;
    console.log(line);
    fs.appendFileSync(logFile, line + '\n', 'utf8');
  };

  try { fs.unlinkSync(logFile); } catch(e) {}
  
  log('=== XHS Publish v4 - FULL FLOW ===');

  let browser;
  try {
    browser = await puppeteer.launch({
      headless: false,
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled'],
      ignoreDefaultArgs: ['--enable-automation']
    });
    log('Chrome launched!');

    const page = await browser.newPage();
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36');
    
    log('Step 1: Set cookies & navigate...');
    const xhsCookiePath = path.join(process.env.USERPROFILE || process.env.HOME, '.xhs-mcp', 'cookies.json');
    const xhsCookies = JSON.parse(fs.readFileSync(xhsCookiePath, 'utf8'));
    
    await page.goto('https://creator.xiaohongshu.com/publish/publish', { waitUntil: 'networkidle2', timeout: 60000 });
    
    await page.setCookie(...xhsCookies.map(c => ({
      name: c.name, value: c.value,
      domain: c.domain || '.xiaohongshu.com', path: c.path || '/',
      secure: c.secure !== false, httpOnly: c.httpOnly !== false, sameSite: c.sameSite || 'Lax'
    })));
    
    await page.goto('https://creator.xiaohongshu.com/publish/publish', { waitUntil: 'networkidle2', timeout: 60000 });
    await new Promise(r => setTimeout(r, 3000));
    
    if (page.url().includes('login')) { log('❌ Login required'); return; }
    log('✅ On publish page');

    log('\nStep 2: Switch to 上传图文 tab...');
    await page.evaluate(() => {
      document.querySelectorAll('.creator-tab').forEach(tab => {
        if (tab.textContent.includes('上传图文')) tab.click();
      });
    });
    await new Promise(r => setTimeout(r, 3000));
    log('✅ Tab switched');

    log('\nStep 3: Upload image...');
    const imgPath = String.raw`C:\Users\ljy\Documents\Gemini\TRAEtest\多智能体推文\xiaohongshu-agent\data\images\original_7a09142a_0.jpg`;
    const fileInput = await page.$('input[type="file"].upload-input');
    if (fileInput) {
      await fileInput.uploadFile(imgPath);
      log('✅ Image uploaded, waiting for form...');
      await new Promise(r => setTimeout(r, 8000));
    }

    log('\nStep 4: Fill title...');
    const postTitle = 'Claude评测超越GPT-4o';
    const titleFilled = await page.evaluate((title) => {
      const els = document.querySelectorAll('input, [contenteditable], textarea, [class*="title"]');
      for (const el of els) {
        if (el.placeholder && el.placeholder.includes('标题')) {
          el.focus(); el.value = title;
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
          return true;
        }
      }
      return false;
    }, postTitle);

    if (!titleFilled) {
      log('Trying alt title selector...');
      try {
        const titleEl = await page.waitForSelector('input[placeholder*="标题"]', { timeout: 5000 });
        await titleEl.click({ clickCount: 3 });
        await titleEl.type(postTitle, { delay: 30 });
        log('✅ Title filled via type()');
      } catch(e) {
        log('⚠️ Title fill issue: ' + e.message);
      }
    } else {
      log('✅ Title filled: ' + postTitle);
    }

    await new Promise(r => setTimeout(r, 1000));

    log('\nStep 5: Fill content...');
    const postContent = `Claude 2026最新评测：全面超越GPT-4o！

长文本理解、代码推理、安全性全面领先。中文处理和多轮对话表现突出。附完整评测数据。

💬 你们觉得怎么样？评论区聊聊吧~`;

    const contentFilled = await page.evaluate((text) => {
      const els = document.querySelectorAll('[contenteditable], textarea, [class*="content"], [class*="editor"] [contenteditable]');
      for (const el of els) {
        if (el.placeholder && (el.placeholder.includes('正文') || el.placeholder.includes('描述') || el.placeholder.includes('分享'))) {
          el.focus();
          document.execCommand('selectAll', false, null);
          document.execCommand('insertText', false, text);
          return true;
        }
      }
      return false;
    }, postContent);

    if (!contentFilled) {
      log('Trying alt content selector...');
      try {
        const ce = await page.waitForSelector('[contenteditable]', { timeout: 5000 });
        await ce.click();
        await page.evaluate((t) => {
          document.execCommand('selectAll', false, null);
          document.execCommand('insertText', false, t);
        }, postContent);
        log('✅ Content filled via fallback');
      } catch(e) {
        log('⚠️ Content fill issue: ' + e.message);
      }
    } else {
      log('✅ Content filled (' + postContent.length + ' chars)');
    }

    await new Promise(r => setTimeout(r, 2000));

    log('\nStep 6: Screenshot before publish...');
    await page.screenshot({ path: path.join(__dirname, '_v4_before_pub.png'), fullPage: true });

    log('\nStep 7: Click PUBLISH button...');
    const pubClicked = await page.evaluate(() => {
      const btns = document.querySelectorAll('button, [role="button"], div[class*="publish"], div[class*="submit"], span[class*="publish"]');
      for (const btn of btns) {
        const t = btn.textContent.trim();
        if (t === '发布' || t === '发 布' || t.includes('发布')) { btn.click(); return true; }
      }
      return false;
    });

    if (pubClicked) {
      log('✅ PUBLISH BUTTON CLICKED!');
      await new Promise(r => setTimeout(r, 10000));
      
      await page.screenshot({ path: path.join(__dirname, '_v4_after_pub.png'), fullPage: true });
      log('📸 After-publish screenshot saved');
      log('URL after publish: ' + page.url());
    } else {
      log('⚠️ Publish button not found, saving pre-state screenshot');
    }

    log('\n=== PUBLISH COMPLETE ===');
    log('User: Lindsay.');
    log('Title: ' + postTitle);
    log('Content length: ' + postContent.length);
    log('Image: original_7a09142a_0.jpg');
    log('Published: ' + pubClicked);

  } catch(e) {
    log('FATAL: ' + e.message);
    log('STACK: ' + e.stack);
  } finally {
    if (browser) {
      await new Promise(r => setTimeout(r, 5000));
      await browser.close();
      log('Browser closed.');
    }
  }
  log('\n=== DONE ===');
}

publish().catch(e => { console.error(e); process.exit(1); });
