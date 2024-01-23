
import atexit
import difflib
import glob
from os import chdir, mkdir
import os
from os.path import isdir
import re
from shutil import copytree, rmtree
import subprocess
from sys import argv
from tempfile import mkdtemp

from debian.deb822 import Deb822, Sources
from debian.debian_support import Version
from debian.changelog import Changelog

import requests

from req import installation_token

# https://dep-team.pages.debian.net/deps/dep14/
def mangle(version):
    version = version.replace(':', '%').replace('~', '_')
    version = re.sub(r'\.(?=(\.|$|lock$))', '.#', version)
    return version

def demangle(version):
    version = version.replace('%', ':').replace('_', '~')
    version = version.replace('.#', '.')
    return version

def upstream_version(version):
    return Version(version).upstream_version


def cleanup(_dir: str):
    # check dir is in /tmp
    assert 'dcbot' in _dir
    print(f'Cleaning up {_dir}')
    rmtree(_dir)

# old = '/path/to/GIT.OLD'
# new = '/path/to/GIT.NEW'
def gen_pr_body(old: str, new: str):
    old_control = [item for item in Deb822.iter_paragraphs(open(f'{old}/debian/control'))]
    old_changelog = Changelog(open(f'{old}/debian/changelog'))

    new_control = [item for item in Deb822.iter_paragraphs(open(f'{new}/debian/control'))]
    new_changelog = Changelog(open(f'{new}/debian/changelog'))

    body = ''
    body += '## Basic Information\n'
    body += f'Old Version: {old_changelog.full_version}\n'
    body += f'New Version: {new_changelog.full_version}\n'
    
    old_native = '-' not in old_changelog.full_version
    new_native = '-' not in new_changelog.full_version

    if old_native != new_native:
        body += 'Upstream changed it\'s package formats. Previous: '
        body += 'native' if old_native else 'quilt'
        body += ', New: '
        body += 'native' if new_native else 'quilt'
        body += '\n'

    if 'dde' in old_changelog.full_version or \
        'deepin' in old_changelog.full_version:
        body += 'Old version may contain dde / deepin patches. Please review more precisely.\n'
    
    body += '\n'

    potential_transition = False
    old_package_list = [binary_section['Package'] for binary_section in old_control[1:]]
    new_package_list = [binary_section['Package'] for binary_section in new_control[1:]]
    for package in old_package_list:
        if package == 'template-repository':
            continue
        if package not in new_package_list:
            if not potential_transition:
                potential_transition = True
                body += '## Potential transition\n'
            body += f'- **{package}** is not present in the new package.\n'

    old_series = []
    new_series = []

    if os.path.exists(f'{old}/debian/patches/series'):
        old_series = open(f'{old}/debian/patches/series').readlines()
    if os.path.exists(f'{new}/debian/patches/series'):
        new_series = open(f'{new}/debian/patches/series').readlines()
    
    d = difflib.unified_diff(old_series, new_series, 'a/debian/patches/series', 'b/debian/patches/series')
    d = ''.join(d)
    if d.strip():
        body += '## Patch series\n'
        body += '```diff\n'
        body += d
        body += '```'
    
    return body

# 1a bash
# 1b bash/unstable
# 2 https://ftp.debian.org/debian/pool/main/b/bash/bash_5.2.21-2.dsc
# package_with_suite_or_url = 'sympy'

# 1 '' -> dcbot-version
# 2a 'custom'
# 2b 'topic-topicname'
# branch = ''

# Defaults to packagename
# github_project_name = '' # https://github.com/deepin-community/""blablabla""

# requester = '@UTSweetyfish'

def update(
    package_with_suite_or_url: str,
    branch: str,
    github_project_name: str,
    requester: str
    ):

    m_url = re.search(r"^https?://.*/(.*?\.dsc)$", package_with_suite_or_url)
    m_p_with_s = re.search(r"^([a-z0-9][a-z0-9+\-.]+)(?:/([a-z]+))?$", package_with_suite_or_url)

    # Should at least match one
    assert m_url or m_p_with_s
    # Shouldn't match both
    assert not (m_url and m_p_with_s)

    suite = ''

    if m_p_with_s:
        suite = m_p_with_s.group(2)
        if not suite:
            suite = 'unstable'
        if suite == 'sid':
            suite = 'unstable'
        elif suite == 'rc-buggy':
            suite = 'experimental'

        assert suite in ['unstable', 'experimental']

    # pylint: disable=W0603
    workdir = mkdtemp(prefix='dcbot.')
    print(f'Working directory: {workdir}')
    # clean workdir atexit
    atexit.register(cleanup, workdir)

    chdir(workdir)

    mkdir('SOURCE')
    chdir('SOURCE')

    # 1. Infer github_project_name
    # 2. Infer branch

    if m_url:
        url = m_url.group(0)
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        s = Sources(r.text)
        package_name = s['Source']
        if not github_project_name:
            github_project_name = s['Source']
        if not branch:
            branch = mangle(upstream_version(s['Version']))
    elif m_p_with_s:
        # apt source --download-only bash/sid
        package_name = m_p_with_s.group(1)
        if not github_project_name:
            github_project_name = m_p_with_s.group(1)

        # Thanks DonKult!
        filename = subprocess.check_output(
            # f'apt-get indextargets "MetaKey: main/source/Sources" "Codename: sid"
            f'apt-get indextargets "MetaKey: main/source/Sources" | grep-dctrl -XF Suite: {suite} -o -XF Codename: {suite} -ns Filename',

            text=True, shell=True
        )
        filename = filename.strip()
        filename = filename.split()
        assert len(filename) == 1
        filename = filename[0]

        assert os.path.exists(filename)

        # Donkult: The files might be compressed, so better put them through apt-helper
        sources = subprocess.check_output(
            f'/usr/lib/apt/apt-helper cat-file {filename} | grep-dctrl -XP {package_name}',
            shell=True, text=True
        )

        s = Sources(sources)

        if not branch:
            branch = mangle(f'dcbot/debian/{upstream_version(s["Version"])}')
    else:
        # Should not reach here
        assert False


    assert branch
    assert github_project_name
    assert package_name
    # Avoid writing to master
    assert branch != 'master'
    assert branch != 'main'
    # load github token here

    chdir('..')


    # TODO: Use GitHub API to check repo exists
    # check_github_project_exist()
    # TODO: Use GitHub API to check if branch exists
    # check_branch_already_exist()

    # clone repo
    subprocess.check_output([
        'git', 'clone',
        f'https://x-access-token:{installation_token()}@github.com/deepin-community/{github_project_name}.git',
        'GIT.OLD'
    ])

    chdir('SOURCE')
    if m_url:
        subprocess.check_output([
            'dget', '--download-only', '--allow-unauthenticated', m_url.group(0)
        ])
    elif m_p_with_s:
        subprocess.check_output(
            [
                'apt', 'source', '--download-only', m_p_with_s.group(0)
            ]
        )

    dsc = glob.glob('*.dsc')
    assert len(dsc) == 1
    dsc = dsc[0]
    # 'dpkg-source --skip-patches --extract filename.dsc outdir'
    subprocess.check_output([
        'dpkg-source', '--skip-patches', '--extract', dsc,
        '../GIT.NEW'
    ])
    chdir('..')
    chdir('GIT.NEW')
    # delete .github in NEW
    # delete .pc in NEW
    subprocess.check_output([
        'rm', '-rf',
        '.git/',
        '.github/',
        '.pc/'
    ])
    # assert no debian/deepin in NEW
    assert not isdir('debian/deepin')
    copytree('../GIT.OLD/.git', '.git')

    subprocess.check_output([
        'git', 'checkout', '--',
        'debian/deepin',
        '.github/'
    ])
    try:
        subprocess.check_output(['git', 'branch', '-D', branch])
    except subprocess.CalledProcessError:
        pass

    subprocess.check_output([
        'git', 'checkout', '-b', branch
    ])
    # git commit

    subprocess.check_output([
        'git', 'add', '-f', '.'
    ])
    subprocess.check_output(
        'git config user.name deepin-community-bot[bot]',
        shell=True
    )
    subprocess.check_output(
        'git config user.email 156989552+deepin-community-bot[bot]@users.noreply.github.com',
        shell=True
    )
    commit_message = f'feat: update {package_name} to {s["Version"]}'

    subprocess.check_output([
        'git', 'commit', '-m', commit_message

    ])

    # input(f'Will push to origin:{branch}. Continue?')

    # FIXME: DO NOT FORCE PUSH IN PRODUCTION
    subprocess.check_output([
        'git', 'push', '-uf', 'origin', branch
    ])

    chdir('..')

    pr_title = '[DCBOT-TEST] ' + commit_message
    # pr_title = 'update'

    pr_body = gen_pr_body('GIT.OLD', 'GIT.NEW')

    pr_body = f'This pull request is requested by {requester}\n' + pr_body

    print(f'Will create a pull request from {branch} to master')
    print(pr_title)
    print(pr_body)
    # input('Press Enter to create pull request...')

    r = requests.post(f'https://api.github.com/repos/deepin-community/{github_project_name}/pulls',
        headers={
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Authorization': f'Bearer {installation_token()}',
        },
        json={
            'base': 'master',
            'head': branch,
            'title': pr_title,
            'body': pr_body,
        }, timeout=5
    )
    # print(r.request)
    # print(r.text)
    r.raise_for_status()

def main():
    package = argv[1]
    branch = argv[2]
    github_project_name = argv[3]
    requester = argv[4]
    if branch == '-': branch = ''
    if github_project_name == '-': github_project_name = ''

    if branch:
        assert branch.startswith('topic-')
    if requester and requester[0] != '@':
        requester = '@' + requester
    # assert requester in [
    #     '@UTSweetyfish'
    # ]
    
    update(package, branch, github_project_name, requester)
if __name__ == '__main__':
    main()
