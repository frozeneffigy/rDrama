from files.cli import g, app, db_session
import click
import files.helpers.const as const

import files.helpers.lottery as lottery
import files.helpers.offsitementions as offsitementions
import files.helpers.stats as stats
import files.helpers.awards as awards
import files.routes.static as route_static
from files.routes.subs import sub_inactive_purge_task
from files.routes.admin import give_monthly_marseybux_task

from sys import stdout

@app.cli.command('cron', help='Run scheduled tasks.')
@click.option('--every-5m', is_flag=True, help='Call every 5 minutes.')
@click.option('--every-1h', is_flag=True, help='Call every 1 hour.')
@click.option('--every-1d', is_flag=True, help='Call every 1 day.')
@click.option('--every-1mo', is_flag=True, help='Call every 1 month.')
def cron(every_5m, every_1h, every_1d, every_1mo):
	g.db = db_session()

	if every_5m:
		lottery.check_if_end_lottery_task()
		offsitementions.offsite_mentions_task()

	if every_1h:
		awards.award_timers_bots_task()

	if every_1d:
		stats.generate_charts_task(const.SITE)
		route_static.stats_cached()
		sub_inactive_purge_task()

	if every_1mo:
		give_monthly_marseybux_task()

	g.db.commit()
	g.db.close()
	stdout.flush()