import subprocess, sys, os

os.environ['PUPPETEER_EXECUTABLE_PATH'] = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

print('Testing Puppeteer + Chrome launch...')
print('PUPPETEER_EXECUTABLE_PATH:', os.environ.get('PUPPETEER_EXECUTABLE_PATH'))

js_code = '''
const puppeteer = require("puppeteer");
(async () => {
  console.log("Launching browser...");
  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"]
  });
  console.log("Browser launched OK");
  const page = await browser.newPage();
  await page.goto("https://www.xiaohongshu.com", {timeout: 30000});
  console.log("Page loaded:", await page.title());
  await browser.close();
  console.log("DONE");
})().catch(e => { console.error("ERROR:", e.message); process.exit(1); });
'''

xhs_mcp_dir = r'C:\Users\ljy\AppData\Roaming\npm\node_modules\xhs-mcp'
result = subprocess.run(
    ['node', '-e', js_code],
    cwd=xhs_mcp_dir,
    capture_output=True, text=True, timeout=60
)

print('\nSTDOUT:', result.stdout)
if result.stderr:
    print('STDERR:', result.stderr)
print('EXIT:', result.returncode)
