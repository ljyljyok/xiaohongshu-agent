import sys, os
sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from crawl_latest_aigc import generate_keyword_posts

year, month, day = 2026, 4, 4
today = '2026-04-04'

posts = generate_keyword_posts(
    ['Vibe Coding', 'Claude', 'OpenClaw', 'Harness Engineering'],
    year, month, day, today,
    max_count=15
)

print('=== generate_keyword_posts 测试 (max_count=15) ===')
print('生成帖子数: {}'.format(len(posts)))
print()
for i, p in enumerate(posts):
    print('[{}] {}'.format(i+1, p['title'][:60]))
    print('    内容长度: {}字 | 来源: {} | 赞: {}'.format(
        len(p['content']), p.get('source','?'), p.get('likes','?')))
print()
print('总计: {} 篇'.format(len(posts)))
print('达到目标: {}'.format('✅ 是' if len(posts) == 15 else '❌ 否 (只有{}篇)'.format(len(posts))))
