const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const content = `🔥 今天给大家分享一个超棒的AI助手！\n\nClaude 2026年最新评测：能力全面超越GPT-4o的真相 Anthropic的Claude模型在今年迎来了史诗级更新！我在20个真实场景下对比了Claude和GPT-4o，结果令人震惊。Claude在长文本理解、代码推理、安全性方面全面领先。特别是在中文处理和多轮对话中表现突出。附完整评测数据和实际使用案例。\n\n💬 你们觉得怎么样？评论区聊聊吧~`;

const tmpContent = path.join(__dirname, '_tmp_content.txt');
fs.writeFileSync(tmpContent, content, 'utf8');

const title = 'Claude 2026评测：超越GPT-4o真相';
const media = String.raw`C:\Users\ljy\Documents\Gemini\TRAEtest\多智能体推文\xiaohongshu-agent\data\images\original_7a09142a_0.jpg`;
const tags = 'AIGC,人工智能,实用工具,Claude,GPT-4o';
const xhsMcp = String.raw`C:\Users\ljy\AppData\Roaming\npm\node_modules\xhs-mcp\dist\xhs-mcp.cjs`;

console.log('Publishing to Xiaohongshu...');
console.log('Title:', title);
console.log('Media:', media);
console.log('Tags:', tags);

try {
  const result = execSync(
    `"${process.execPath}" "${xhsMcp}" publish --type image --title "${title}" --content "$(cat ${tmpContent})" -m "${media}" --tags "${tags}"`,
    { encoding: 'utf8', timeout: 180000, shell: true, stdio: ['pipe', 'pipe', 'pipe'] }
  );
  console.log('\n=== RESULT ===');
  console.log(result);
} catch (e) {
  console.log('\n=== ERROR ===');
  console.log('Message:', e.message);
  if (e.stdout) console.log('Stdout:', e.stdout.slice(-2000));
  if (e.stderr) console.log('Stderr:', e.stderr.slice(-1000));
}

try { fs.unlinkSync(tmpContent); } catch(e) {}
