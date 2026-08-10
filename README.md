# App support hub

Public support, privacy, and accessibility pages for apps published by Sebastian Rodriguez.

Production URL: <https://sebastianrodriguez-dev.github.io/>

## Structure

```text
/
├── index.html                  App directory
├── 404.html                    Safe not-found page
├── assets/site.css             Shared, local-only styles
├── apps/
│   └── <app-slug>/
│       ├── index.html          App support landing page
│       ├── support/index.html        Support and contact instructions
│       ├── privacy/index.html        App-specific privacy policy
│       └── accessibility/index.html  Optional accessibility statement
├── scripts/validate_site.py    Link, HTML, placeholder, and security checks
└── .github/workflows/pages.yml Validation and GitHub Pages deployment
```

Each app owns a stable path under `/apps/<app-slug>/`. Shared presentation belongs in `assets/site.css`; app-specific facts belong only in that app's directory. Pages use plain HTML and CSS. The site has no JavaScript, forms, cookies, trackers, remote fonts, or third-party assets.

## Add or update an app

1. Create `apps/<app-slug>/` and add an app landing page, support page, and privacy policy. Add an accessibility statement when the app has verified accessibility information to publish.
2. Use absolute production URLs beginning with `https://sebastianrodriguez-dev.github.io/apps/<app-slug>/` for canonical links and site navigation.
3. Add the app to the root directory in `index.html`.
4. Keep claims limited to the shipping app and dated evidence. Do not copy privacy, purchase, or accessibility claims between apps without checking them.
5. Run `python3 scripts/validate_site.py`. Deployment stays blocked while any required contact value is pending.
6. Open a pull request. Changes to app policies, contact details, security controls, or the publishing workflow require owner review through `CODEOWNERS`.

## Publishing

The Pages workflow runs only for `main` and manual dispatch. It validates the committed files before building a small allow-listed artifact containing only the public HTML, CSS, and `.nojekyll`. The deploy job receives `pages: write` and `id-token: write`; validation receives read-only repository access.

GitHub Pages must be configured to use **GitHub Actions** as its source. Do not bypass the validation job or publish the repository root with a different workflow.

## Local checks

Run the strict release gate:

```sh
python3 scripts/validate_site.py
```

During initial authoring only, the structural and security checks can run while a documented contact placeholder remains:

```sh
python3 scripts/validate_site.py --allow-placeholders
```

The second command is not accepted by the deployment workflow.

## Security

Read [SECURITY.md](SECURITY.md) before reporting sensitive information. Do not put private account, payment, device, or user data in a public repository post or message.
