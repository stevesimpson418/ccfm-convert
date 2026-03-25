# Troubleshooting

## Authentication failed

Verify the token is correct and the email matches your Atlassian account. Ensure you have
create/edit permissions in the target space.

## Space not found

Use the space **key** (e.g., `DOCS`), not the display name. The key appears in the URL:
`/wiki/spaces/DOCS/`.

## "Run `ccfm init` first"

The management page was not found in your space. Run `ccfm init` to create the `_ccfm`
container and state management page.

## Apply blocked by lock

Another apply is in progress (or a previous apply crashed without releasing the lock).
Check the lock status and force-release if the lock is stale:

```bash
ccfm lock status
ccfm lock release
```

## Image not rendering after redeploy

The Confluence v1 attachment update endpoint returns a different response shape than the create
endpoint. CCFM normalises this automatically — ensure you are running the latest version.

## Page hierarchy issues

Ensure markdown files are under your `docs_root` directory. Directories without
`.page_content.md` get an auto-generated placeholder page. Add one to control the container
page's title and content.

## Debugging ADF output

Use `--debug-file` to convert a single markdown file to ADF JSON and print it to stdout.
No credentials or API calls needed:

```bash
ccfm plan --debug-file path/to/problem-page.md
ccfm plan --debug-file path/to/problem-page.md | jq '.content'
```
