#!/usr/bin/env python3
"""
从 GitHub 获取仓库信息并构建 Hexo 站点
"""

import json
import re
import urllib.request
import urllib.error
import subprocess
import os
from pathlib import Path


def get_git_remote_url():
    """获取 git 远程仓库 URL"""
    try:
        result = subprocess.run(
            ['git', 'config', '--get', 'remote.origin.url'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def parse_github_repo(remote_url):
    """解析 GitHub 仓库 URL，返回 owner 和 repo"""
    # 处理多种 git remote URL 格式
    # https://github.com/owner/repo.git
    # git@github.com:owner/repo.git
    # https://github.com/owner/repo

    patterns = [
        r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
        r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?$'
    ]

    for pattern in patterns:
        match = re.match(pattern, remote_url)
        if match:
            owner = match.group(1)
            repo = match.group(2)
            return owner, repo

    return None, None


def fetch_github_api(url):
    """获取 GitHub API 数据"""
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        return None
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        return None


def update_yaml_config(file_path, updates):
    """更新 YAML 配置文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for key, value in updates.items():
        # 匹配 key: value 的格式
        pattern = rf'^{key}:\s*.*$'
        replacement = f'{key}: {value}'
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def update_yaml_config_nested(file_path, key_path, value):
    """更新嵌套的 YAML 配置文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 构建正则表达式来匹配嵌套键
    # 例如: utterances:\n  repo: xxx
    pattern = rf'^{key_path}:\s*.*$'
    replacement = f'{key_path}: {value}'
    content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def create_markdown_file(file_path, title, date, categories, tags, content):
    """创建 Markdown 文件"""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(f'title: {title}\n')
        f.write(f'date: {date}\n')
        
        if categories:
            f.write('categories:\n')
            for cat in categories:
                f.write(f'  - {cat}\n')
        
        if tags:
            f.write('tags:\n')
            for tag in tags:
                f.write(f'  - {tag}\n')
        
        f.write('---\n\n')
        f.write(content)


def fetch_issues(owner, repo):
    """获取仓库的所有 Issues"""
    issues = []
    page = 1
    per_page = 100
    
    while True:
        url = f'https://api.github.com/repos/{owner}/{repo}/issues?state=all&page={page}&per_page={per_page}'
        data = fetch_github_api(url)
        
        if not data or len(data) == 0:
            break
        
        issues.extend(data)
        page += 1
    
    return issues


def process_labels(labels):
    """处理 labels，返回 categories 和 tags"""
    categories = []
    tags = []
    
    for label in labels:
        label_name = label['name']
        if label_name.startswith('cg_'):
            categories.append(label_name[3:])
        elif label_name.startswith('tg_'):
            tags.append(label_name[3:])
    
    return categories, tags


def main():
    # 1. 获取 git 远程仓库 URL
    remote_url = get_git_remote_url()
    
    if not remote_url:
        print("错误：无法获取 git 远程仓库 URL")
        return
    
    # 2. 解析 GitHub 仓库信息
    owner, repo = parse_github_repo(remote_url)
    
    if not owner or not repo:
        print("错误：仓库 URL 不是 GitHub 格式")
        return
    
    print(f"检测到 GitHub 仓库: {owner}/{repo}")
    
    # 3. 获取用户信息
    user_info = fetch_github_api(f'https://api.github.com/users/{owner}')
    
    if not user_info:
        print("错误：无法获取用户信息")
        return
    
    # 获取用户信息
    avatar_url = user_info.get('avatar_url', '')
    name = user_info.get('name') or owner  # 如果没有 name，使用 owner
    bio = user_info.get('bio') or ''
    
    print(f"用户名: {name}")
    print(f"头像: {avatar_url}")
    print(f"简介: {bio}")
    
    # 4. 更新 _config.next.yml
    # 更新头像
    if avatar_url:
        update_yaml_config_nested(
            '_config.next.yml',
            '  url',
            avatar_url
        )
        print("已更新头像链接")
    
    # 更新 utterances 仓库
    utterances_repo = f'{owner}/{repo}'
    update_yaml_config_nested(
        '_config.next.yml',
        '  repo',
        utterances_repo
    )
    print(f"已更新 utterances 仓库为: {utterances_repo}")
    
    # 5. 更新 _config.yml
    updates = {
        'author': name,
        'title': f'{name}的精神花园',
        'subtitle': '是生活，是思考，是体验',
        'description': bio
    }
    
    # 设置 URL
    if repo.endswith('.github.io'):
        url = f'https://{repo}'
    else:
        url = f'https://{owner}.github.io/{repo}'
    updates['url'] = url
    
    update_yaml_config('_config.yml', updates)
    print("已更新站点配置")
    
    # 6. 获取 Issues 并创建文章
    print("正在获取 Issues...")
    issues = fetch_issues(owner, repo)
    print(f"共获取到 {len(issues)} 个 Issues")
    
    # 创建 source/_posts 目录
    posts_dir = Path('source/_posts')
    posts_dir.mkdir(parents=True, exist_ok=True)
    
    # 处理每个 Issue
    for issue in issues:
        title = issue['title']
        body = issue.get('body') or ''
        created_at = issue['created_at']
        
        # 处理 labels
        categories, tags = process_labels(issue.get('labels', []))
        
        # 生成文件名（使用标题作为文件名，替换特殊字符）
        safe_title = re.sub(r'[^\w\u4e00-\u9fa5\-_]', '_', title)
        filename = f'{created_at[:10]}-{safe_title}.md'
        file_path = posts_dir / filename
        
        # 创建 Markdown 文件
        create_markdown_file(
            file_path,
            title,
            created_at,
            categories,
            tags,
            body
        )
        print(f"已创建文章: {filename}")
    
    print("所有文章创建完成！")


if __name__ == '__main__':
    main()