from datetime import datetime, timedelta
from typing import List

import click
import math
from github import Github
from github.Organization import Organization
from github.Repository import Repository
from pandas import DataFrame

BASE_URL = 'https://github.bus.zalan.do/api/v3'
REPOS = ['deploy', 'integrator', 'ci-gooddata-sql', 'gooddata-python', 'dna-tools', 'ci-master-workspace', 'airpipe']
ORGANIZATION = 'dna'


@click.command()
@click.option('-t', '--token', type=click.STRING, required=True)
@click.option('-l', '--last-days', type=click.INT)
@click.option('-v', '--verbose', is_flag=True, default=False)
@click.argument('repos', nargs=-1)
def cli(token: str, last_days: int, verbose: bool, repos: List[str]):
    g = get_github_client(BASE_URL, token)

    repos = list(repos) if repos else REPOS
    time_filter = f'(last {last_days} days)' if last_days else ''
    click.echo(f'Calculating for {repos} {time_filter}')
    analyze_repos(g, ORGANIZATION, repos, last_days, verbose)


def get_github_client(base_url: str, token: str):
    return Github(base_url=base_url, login_or_token=token)


def analyze_repos(g: Github, org: str, repos: List[str], last_days: int, verbose: bool):
    org: Organization = g.get_organization(org)
    for repo in repos:
        pulls = calculate_pr_time(org.get_repo(repo), last_days)
        if not pulls.empty:
            if verbose:
                click.echo(pulls.sort_values('Time', ascending=False))
            time_col = pulls.loc[:, 'Time']
            mean = time_col.mean()
            std_err = time_col.std() / math.sqrt(len(time_col))

            click.echo(f'{repo} ({len(time_col)} PRs): '
                       f'mean={mean:.2f}, std_e={std_err:.2f}, window=[{(mean - std_err):.2f}, {(mean + std_err):.2f}]')
        else:
            click.echo(f'Could not find any matching pull requests in \'{repo}\'')


def calculate_pr_time(repo: Repository, last_days: int) -> DataFrame:
    return DataFrame(list(
        {p.title: (p.merged_at - p.created_at).seconds / 3600
         for p in repo.get_pulls(state='closed')
         if ((p.created_at >= datetime.today() - timedelta(days=last_days)) if last_days else True) and p.merged
         }.items()),
        columns=['PR', 'Time']
    )


if __name__ == '__main__':
    cli()
