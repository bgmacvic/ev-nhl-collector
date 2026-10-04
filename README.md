# EV NHL hosted collection setup

Prepared October 4, 2026 UTC (October 3 in Toronto).

## What this release does

This is a deployable, read-only collection stage for the recovered V1c project.
It is not the finished betting engine. It requires no computer left running at
home. Ten offline tests pass. No hosted deployment has been performed yet.

- Fetches the NHL regular-season schedule every five minutes.
- Streams MoneyPuck's published bulk team file, retains current-season regular-season
  rows, and collects official NHL player landing
  pages for goalies in the preserved history once per Toronto calendar day.
- Starts these slow downloads in a separate thread so they do not block odds.
- Attempts a three-book moneyline capture when a scheduled game reaches T−15.
- Records actual request, receipt and provider update timestamps. A capture
  within the 60-second attempt window is NOT automatically a valid T−15 quote.
- Uses FanDuel, DraftKings and Ontario Proline (`proline_ca_on`). bet365 is an
  optional manual check, as authorized by Blake.
- Stores compressed source responses and SHA256 metadata on persistent disk.
- Records missed captures after downtime rather than reconstructing old prices.
- Retains schedule snapshots for seven days, raw odds for 60 days, per-game
  audits without automatic expiry; latest team/goalie snapshots replace prior
  downloads. Final production feature provenance needs immutable per-event
  team/goalie inputs before promotion.
- Does not place bets, send messages or alter the $1 progression.

The included opening state is evidence for later integration. This collector
does not yet merge downloads into model state or produce live probabilities.
There is no public website or mobile notification in this release; results are
available in the private Render logs and on its disk.

## Hosting options and cost

Prices checked against provider pages on October 4, 2026 UTC. All amounts below
are USD, before taxes, FX/card fees and any extra metered usage. Confirm the
checkout estimate before deploying.

| Option | Hosting cost | Fit |
| --- | --- | --- |
| Render paid Starter background worker + 1 GB disk | About $7 + $0.25/month | Recommended for this lightweight collector; supplied Blueprint |
| Railway Hobby + volume | $5/month minimum, includes $5 usage; usage above that costs extra | Alternative; same Python start command, manually attach volume |
| GitHub Actions | Account allowance may cover tests/batch work; overages depend on account | Useful for tests, not the sole precise T−15 trigger because scheduled jobs can be delayed |

The Render figure is a starting collector budget, not a promise that full
historical model replay will fit 512 MB. This service uses the standard library
and small seed state. Future model integration may require more memory/storage.
No additional paid workspace plan is intended; choose the personal/free
workspace option if available and review its current limits at checkout.

The Odds API Starter: $0, 500 credits/month, most books, no historical odds.
Its 20K plan: $30/month, 20,000 credits/month and historical odds. Start free
and verify the required books before upgrading. The collector requests one
market and three explicit bookmakers, batches games due together, and records
the provider's remaining-credit header. The daily cap is 20 attempted calls;
it is NOT a 500-credit monthly cap. Monitor your provider dashboard. If free
credits run out, the collector reports an error; it cannot purchase an upgrade.

Expected starting total: about $7.25/month with free odds, or $37.25/month
with the $30 odds plan. These are not Canadian-dollar quotes. Do not buy a
paid odds plan solely to recover tonight's missing capture: historical snapshots
still require timestamp and event validation.

## Tasks only you need to do

This session successfully downloaded all 222 goalie profiles in the preserved
history. The eight opening-night 2015 comparison rows support investigating
the 2008–09 start date: four shot totals match exactly and four differ by one
or two shots in the current official source. That is evidence requiring
reconciliation, not a full independent career-history replay.

You need accounts, consent to any billing, and to enter your API key privately.
You do not need to calculate statistics or manually upload data every day.
A normal computer is convenient for this one-time setup; it can be turned off
afterward. The archive is small enough for browser-based GitHub upload.

### 1. Create a private GitHub repository

1. Sign in or create an account at https://github.com/.
2. Create a repository named `ev-nhl-collector`, visibility **Private**.
3. Download and unzip this package. Upload its CONTENTS, not the zip and not an
   extra containing directory. `render.yaml`, `worker.py`, `test_worker.py`,
   `team_names.json`, `requirements.txt`, this README, and the `seed` folder
   should be at the repository root. The seed folder must contain
   `opening_state.json`. Include `.gitignore` when your file picker permits it.
   The optional `evidence` folder contains the current session's source archive
   and reports; it is not needed to run the worker and can be left out of GitHub.
4. Use Add file → Upload files, then commit the upload. If using a phone and
   folder upload is awkward, use a computer briefly for this step.
5. Never put the Odds API key in a repository file.

### 2. Get or reuse the Odds API key

1. Open https://the-odds-api.com/ (include the hyphens).
2. If you already have an account, reuse it. Otherwise choose Starter/free.
3. Retrieve the API key from your account/email. Keep it for Render's secret
   field. Do not paste it into this conversation or a GitHub file.

### 3. Deploy on Render

1. Open https://dashboard.render.com/ and sign in/create an account.
2. Connect GitHub and grant access only to `ev-nhl-collector` when possible.
3. Choose New → Blueprint; connect that repository and its main branch.
4. Keep Blueprint Path as `render.yaml` and choose a descriptive Blueprint name.
5. Enter your key when prompted for `ODDS_API_KEY`.
6. Review the proposed resources: exactly ONE Starter background worker named
   `ev-nhl-collector`, ONE 1 GB persistent disk mounted at `/var/data`, and no
   database or web service. Confirm the current estimated charges yourself.
7. Click Deploy Blueprint after reviewing the cost. The build runs the tests,
   then starts `python -u worker.py run`.
8. Open the worker's Logs page. Look for `worker_started`, then a schedule
   `FETCHED` result and eventually `daily_refresh`. A running process alone is
   not proof of successful data collection.
9. Check the Environment page: `DATA_DIR=/var/data`, `NHL_SEASON=2026`,
   `MAX_ODDS_CALLS_PER_DAY=20`. Keep exactly one worker instance.

Render displays Blueprint errors before deployment if its schema/plan names
change. Send the non-secret error text rather than improvising a different
service type. Do not select a free web service: this program exposes no port.

### 4. Check the first hosted results

In the Render worker's Shell, run the following read-only commands:

```sh
cat /var/data/maintenance.json
cat /var/data/team_refresh.json
cat /var/data/goalie_refresh.json
```

These files appear after the first maintenance pass. If absent, wait for
`daily_refresh` or inspect logs for `maintenance_error`. New games trigger odds
captures automatically; no manual command is needed for each gameday.

Optional immediate provider test, outside any game's T−15 minute:

```sh
python worker.py odds-test
```

This consumes an odds request and saves a raw response. Avoid simultaneous
manual tests and scheduled captures: this initial version assumes one writer
to collector state. A successful response still does not prove all three books
were present; that requires inspecting the saved response or event audit.

Send me the non-secret `daily_refresh` summary and any capture errors. Do not
send Environment screenshots containing the API key. I can diagnose those
results and continue the integration; access to your private Render files is
not automatically granted by deploying the worker.

### 5. Optional Railway setup instead

1. Create a Railway account and project; choose deployment from the same
   private GitHub repository.
2. Set the start command to `python -u worker.py run` and Python 3.12.
3. Attach a volume mounted at `/var/data`.
4. Set the same four environment variables listed above, including the API key.
5. Choose Hobby only after reviewing its minimum and usage charges. Configure
   usage alerts in the billing controls. Keep one continuously running instance;
   do not configure a cron schedule or sleeping/serverless behavior.
6. Inspect deployment logs as with Render. The supplied Render Blueprint is
   not used by Railway; Railway configuration must be entered separately.

## Work I will complete after hosted access is verified

1. Check downloaded schemas, season coverage, game completeness and updates.
2. Use fetched goalie evidence to reconstruct the precise preserved history
   contract. Player landing career totals are candidates for comparison, not
   automatic substitutes. New goalies not in the seed need discovery. A future
   daily production path needs game-level updates, not just career snapshots.
3. Verify a timestamped confirmed-starter source. Schedule goalie listings
   alone are not confirmation. This feed remains unresolved.
4. Merge fresh data into the frozen team/Elo state, prevent duplicate updates,
   verify before-game cutoffs, then integrate model evaluation.
5. Verify provider team names (especially renamed clubs), Ontario availability,
   and prices against the sportsbooks you actually use. Names in the collector
   are explicit mappings that must match real provider responses.
6. Validate a prospective T−15 run, including scheduling delay and quote age.
   Scheduler timing is not guaranteed; later quotes cannot be labeled T−15.
7. Select and configure delivery of results before unattended operational use.

Do not call this system operational until those checks pass. The collector
never outputs an actionable BET. Your bet365 comparison should record the
team, price and observation time; a later manual price is not the frozen
automated T−15 snapshot.

## Troubleshooting and stopping costs

- HTTP_403: the host could not fetch that source. Send the service/source status;
  no paid upgrade is justified merely by this error.
- HTTP_401: check the Odds API secret. Never paste it into logs or chat.
- HTTP_422: check sportsbook keys/provider plan; do not silently drop books.
- HTTP_429 or exhausted credits: stop manual tests and inspect quota.
- Missing current-season CSV: may be unavailable or not yet updated; collector
  records BLOCKED rather than using an earlier season.
- MISSED_OR_NOT_PREGAME: no retroactive odds substitution; next event can run.
- To stop running: use the host's suspend controls. Check billing separately:
  retained persistent disks can still be charged. To remove all resources,
  export wanted data, remove the worker from the Blueprint/sync, then delete
  the unmanaged service/disk. Deletion loses data. Removing the repository
  alone does not stop hosting charges. Cancel any paid odds plan separately.

## Sources

- Render pricing: https://render.com/pricing
- Render disks: https://render.com/docs/disks
- Render Blueprint setup: https://render.com/docs/infrastructure-as-code
- Render Blueprint specification: https://render.com/docs/blueprint-spec
- Railway pricing: https://railway.com/pricing
- GitHub upload instructions: https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository
- GitHub scheduling limitations: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Odds plans: https://the-odds-api.com/
- Odds documentation: https://the-odds-api.com/liveapi/guides/v4/
- Bookmaker coverage: https://the-odds-api.com/sports-odds-data/bookmaker-apis.html
- MoneyPuck data (credit for underlying team data): https://www.moneypuck.com/data.htm

The hosted HTTP calls have not been verified from Render or Railway. The new
local collector successfully fetched the NHL schedule and 210 MoneyPuck rows
through October 2, 2026 after correcting the inherited MoneyPuck download path.
Ten unit tests use controlled fixtures; they establish software behavior,
not production readiness. See evidence for this session's actual fetch results.
